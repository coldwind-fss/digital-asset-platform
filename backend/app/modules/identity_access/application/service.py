from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.modules.identity_access.api.schemas import AccountCreateRequest, AccountPatchRequest, AccountView, ScopeInput
from app.modules.identity_access.application.passwords import csrf_token, opaque_token, password_hash, password_matches, token_hash
from app.modules.identity_access.domain.policy import PolicySubject
from app.platform.db.models import AuthAccount, AuthActionToken, AuthScope, AuthSession, AuthThrottle, AuditEvent, Department, Person, Resource
from app.platform.http.errors import ApiException

BASE_CAPABILITIES = frozenset({"resource.read", "resource.write", "directory.read", "binding.read", "materials.read", "materials.write", "governance.read", "governance.write"})
MANAGER_CAPABILITIES = BASE_CAPABILITIES | {"binding.write", "governance.confirm", "credential.write", "credential.grant", "materials.restricted", "catalog.write", "finance.read", "finance.write", "integration.manage"}
ADMIN_CAPABILITIES = MANAGER_CAPABILITIES | {"identity.manage", "directory.manage"}
ROLE_CAPABILITIES = {"admin": ADMIN_CAPABILITIES, "resource_manager": MANAGER_CAPABILITIES, "member": BASE_CAPABILITIES}


@dataclass(frozen=True)
class LocalPrincipal:
    account_id: UUID
    person_id: UUID
    username: str
    display_name: str
    department_id: UUID | None
    role: str
    session_id: UUID
    expires_at: datetime
    authenticated_at: datetime
    must_change_password: bool
    capabilities: frozenset[str]

    def policy_subject(self) -> PolicySubject:
        # Business audit APIs use a Person UUID. Authentication identity remains
        # the separate account_id and is never guessed from a name/email.
        return PolicySubject(subject_id=str(self.person_id), authenticated=True, capabilities=self.capabilities)


def now() -> datetime:
    return datetime.now(UTC)


def audit(session: Session, event: str, actor: UUID | None, request_id: UUID, data: dict | None = None) -> None:
    session.add(AuditEvent(actor_person_id=actor, actor_kind="person" if actor else "system", event_type=event, request_id=request_id, safe_after=data or {}))


def identity_lock(session: Session) -> None:
    # Serializes bootstrap and last-administrator changes across processes.
    session.execute(text("SELECT pg_advisory_xact_lock(731004210)"))


def initialized(session: Session) -> bool:
    return bool(session.scalar(select(func.count()).select_from(AuthAccount)))


def require_department(session: Session, department_id: UUID | None) -> None:
    if department_id is not None:
        department = session.get(Department, department_id)
        if department is None or department.status != "active":
            raise ApiException(422, "REFERENCE_NOT_FOUND", "部门不存在或已停用")


def account_view(session: Session, account: AuthAccount) -> AccountView:
    person = session.get(Person, account.person_id)
    if person is None:
        raise ApiException(409, "IDENTITY_MAPPING_INVALID", "账号的人员映射不可用")
    scopes = session.scalars(select(AuthScope).where(AuthScope.account_id == account.id)).all()
    return AccountView(id=account.id, person_id=person.id, username=account.username, display_name=person.display_name, department_id=person.department_id, role=account.role, status=account.status, version=account.version,
                       scopes=[ScopeInput(kind=s.kind, target_id=s.target_id, permission=s.permission) for s in scopes])


def bootstrap(session: Session, settings: Settings, username: str, display_name: str, password: str, token: str, request_id: UUID) -> AuthAccount:
    identity_lock(session)
    if initialized(session):
        raise ApiException(409, "ALREADY_INITIALIZED", "管理员已初始化，请使用登录或恢复流程")
    expected = settings.auth_bootstrap_token
    if not expected or not hmac.compare_digest(token.encode("utf-8"), expected.encode("utf-8")):
        raise ApiException(403, "BOOTSTRAP_DENIED", "初始化口令无效或初始化未启用")
    person = Person(id=uuid4(), display_name=display_name, status="active")
    account = AuthAccount(id=uuid4(), person_id=person.id, username=username, password_hash=password_hash(password), role="admin", status="active")
    session.add(person)
    session.flush()
    session.add(account)
    audit(session, "auth.bootstrap", person.id, request_id, {"account_id": str(account.id)})
    session.commit()
    return account


def _throttles(session: Session, username: str, client_ip: str, instant: datetime) -> list[tuple[AuthThrottle, int]]:
    keys = sorted([(hashlib.sha256(("login:" + username).encode()).hexdigest(), 5), (hashlib.sha256(("ip:" + client_ip).encode()).hexdigest(), 30)])
    rows = []
    for key, limit in keys:
        session.execute(insert(AuthThrottle).values(key=key, failures=0, window_started_at=instant).on_conflict_do_nothing())
        row = session.scalar(select(AuthThrottle).where(AuthThrottle.key == key).with_for_update())
        if row.blocked_until and row.blocked_until > instant:
            session.commit()
            raise ApiException(429, "RATE_LIMITED", "尝试过于频繁，请稍后重试", retryable=True)
        if instant - row.window_started_at >= timedelta(minutes=10):
            row.failures, row.window_started_at, row.blocked_until = 0, instant, None
        rows.append((row, limit))
    return rows


def login(session: Session, settings: Settings, username: str, password: str, client_ip: str, request_id: UUID) -> tuple[AuthAccount, str]:
    instant = now()
    buckets = _throttles(session, username, client_ip, instant)
    account = session.scalar(select(AuthAccount).where(AuthAccount.username == username).with_for_update())
    person = session.get(Person, account.person_id) if account else None
    if account and account.password_hash:
        matches = password_matches(password, account.password_hash)
    else:
        # Do equivalent scrypt work for unknown and pending accounts.
        password_hash(password)
        matches = False
    if not matches or not person or account.status != "active" or person.status != "active":
        for bucket, limit in buckets:
            bucket.failures += 1
            if bucket.failures >= limit:
                bucket.blocked_until = instant + timedelta(minutes=10)
        audit(session, "auth.login_failed", None, request_id)
        session.commit()
        raise ApiException(401, "INVALID_CREDENTIALS", "账号或密码不正确，或账号尚未启用")
    # Reset only the account bucket; IP bucket counts failures across accounts.
    account_key = hashlib.sha256(("login:" + username).encode()).hexdigest()
    for bucket, _ in buckets:
        if bucket.key == account_key:
            bucket.failures, bucket.blocked_until = 0, None
    raw_token = opaque_token()
    session.add(AuthSession(account_id=account.id, token_hash=token_hash(raw_token), expires_at=instant + timedelta(seconds=settings.auth_session_seconds), last_seen_at=instant, authenticated_at=instant))
    audit(session, "auth.login", person.id, request_id, {"account_id": str(account.id)})
    session.commit()
    return account, raw_token


def resolve_session(engine, settings: Settings, raw_token: str) -> LocalPrincipal | None:
    if not raw_token or len(raw_token) > 256:
        return None
    with Session(engine) as session:
        row = session.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash(raw_token)))
        instant = now()
        if row is None or row.revoked_at or row.expires_at <= instant or instant - row.last_seen_at >= timedelta(seconds=settings.auth_idle_seconds):
            return None
        account = session.get(AuthAccount, row.account_id)
        person = session.get(Person, account.person_id) if account else None
        if account is None or account.status != "active" or person is None or person.status != "active":
            return None
        capabilities = set(ROLE_CAPABILITIES[account.role])
        from app.platform.db.models import CredentialGrant
        has_grant = session.scalar(select(CredentialGrant.id).where(CredentialGrant.person_id == person.id, CredentialGrant.capability.in_(["view", "rotate"]), CredentialGrant.valid_from <= instant,
                                      (CredentialGrant.valid_to.is_(None) | (CredentialGrant.valid_to > instant))).limit(1))
        if has_grant:
            capabilities.add("credential.read")
        if settings.read_only:
            capabilities.intersection_update({"resource.read", "directory.read", "binding.read", "materials.read", "governance.read", "finance.read"})
        principal = LocalPrincipal(account.id, person.id, account.username, person.display_name, person.department_id, account.role, row.id, row.expires_at, row.authenticated_at, account.must_change_password, frozenset(capabilities))
        if instant - row.last_seen_at >= timedelta(seconds=60):
            row.last_seen_at = instant
            session.commit()
        return principal


def revoke_sessions(session: Session, account_id: UUID) -> None:
    session.execute(update(AuthSession).where(AuthSession.account_id == account_id, AuthSession.revoked_at.is_(None)).values(revoked_at=now()))


def verify_current_password(session: Session, principal: LocalPrincipal, password: str, client_ip: str, request_id: UUID) -> AuthAccount:
    instant = now()
    buckets = _throttles(session, principal.username, client_ip, instant)
    account = session.scalar(select(AuthAccount).where(AuthAccount.id == principal.account_id).with_for_update())
    if not account or account.status != "active" or not password_matches(password, account.password_hash):
        for bucket, limit in buckets:
            bucket.failures += 1
            if bucket.failures >= limit:
                bucket.blocked_until = instant + timedelta(minutes=10)
        audit(session, "auth.reauthentication_failed", principal.person_id, request_id)
        session.commit()
        raise ApiException(401, "INVALID_CREDENTIALS", "当前密码不正确")
    account_key = hashlib.sha256(("login:" + principal.username).encode()).hexdigest()
    for bucket, _ in buckets:
        if bucket.key == account_key:
            bucket.failures, bucket.blocked_until = 0, None
    return account


def change_password(session: Session, principal: LocalPrincipal, current: str, replacement: str, request_id: UUID, client_ip: str = "unknown") -> None:
    account = verify_current_password(session, principal, current, client_ip, request_id)
    if password_matches(replacement, account.password_hash):
        raise ApiException(422, "PASSWORD_UNCHANGED", "新密码应与当前密码不同")
    account.password_hash = password_hash(replacement)
    account.must_change_password = False
    account.version += 1
    revoke_sessions(session, account.id)
    audit(session, "auth.password_changed", principal.person_id, request_id, {"account_id": str(account.id)})
    session.commit()


def issue_token(session: Session, account: AuthAccount, purpose: str) -> tuple[str, datetime]:
    session.execute(update(AuthActionToken).where(AuthActionToken.account_id == account.id, AuthActionToken.used_at.is_(None)).values(used_at=now()))
    raw, expires = opaque_token(), now() + timedelta(hours=24 if purpose == "activate" else 1)
    session.add(AuthActionToken(account_id=account.id, token_hash=token_hash(raw), purpose=purpose, expires_at=expires))
    return raw, expires


def redeem_token(session: Session, raw: str, replacement: str, request_id: UUID) -> None:
    candidate = session.scalar(select(AuthActionToken).where(AuthActionToken.token_hash == token_hash(raw)))
    if candidate is None:
        raise ApiException(410, "ACTION_TOKEN_EXPIRED", "激活或恢复口令无效、已使用或已过期")
    # Token issuance locks account then tokens. Use the same order here.
    account = session.scalar(select(AuthAccount).where(AuthAccount.id == candidate.account_id).with_for_update())
    token = session.scalar(select(AuthActionToken).where(AuthActionToken.id == candidate.id).with_for_update().execution_options(populate_existing=True))
    if token is None or token.used_at or token.expires_at <= now():
        raise ApiException(410, "ACTION_TOKEN_EXPIRED", "激活或恢复口令无效、已使用或已过期")
    if account is None or account.status == "inactive":
        raise ApiException(403, "ACCOUNT_INACTIVE", "账号已停用，请联系管理员")
    account.password_hash = password_hash(replacement)
    account.must_change_password = False
    account.status, account.updated_at = "active", now()
    account.version += 1
    token.used_at = now()
    revoke_sessions(session, account.id)
    audit(session, "auth.token_redeemed", account.person_id, request_id, {"account_id": str(account.id), "purpose": token.purpose})
    session.commit()


def replace_scopes(session: Session, account_id: UUID, scopes: list[ScopeInput]) -> None:
    seen = set()
    for scope in scopes:
        key = (scope.kind, scope.target_id)
        if key in seen:
            raise ApiException(422, "DUPLICATE_SCOPE", "同一范围不能重复配置")
        seen.add(key)
        target = session.get(Department if scope.kind == "department" else Resource, scope.target_id)
        if target is None or (scope.kind == "department" and target.status != "active"):
            raise ApiException(422, "REFERENCE_NOT_FOUND", "授权范围目标不存在或不可用")
    session.execute(delete(AuthScope).where(AuthScope.account_id == account_id))
    for scope in scopes:
        session.add(AuthScope(account_id=account_id, **scope.model_dump()))


def create_account(session: Session, payload: AccountCreateRequest, actor: UUID, request_id: UUID) -> tuple[AuthAccount, str, datetime]:
    require_department(session, payload.department_id)
    if payload.person_id:
        person = session.get(Person, payload.person_id)
        if person is None or person.status != "active":
            raise ApiException(422, "REFERENCE_NOT_FOUND", "人员不存在或尚未确认为有效人员")
        if session.scalar(select(AuthAccount.id).where(AuthAccount.person_id == person.id)):
            raise ApiException(409, "PERSON_ALREADY_LINKED", "该人员已有登录账号")
        if person.display_name != payload.display_name or (payload.department_id is not None and payload.department_id != person.department_id):
            raise ApiException(422, "PERSON_MAPPING_CONFLICT", "已有人员资料与提交内容不一致，请确认人员后重试")
    else:
        person = Person(id=uuid4(), display_name=payload.display_name, department_id=payload.department_id, status="active")
        session.add(person)
        session.flush()
    account = AuthAccount(id=uuid4(), person_id=person.id, username=payload.username, role=payload.role, status="pending")
    session.add(account)
    try:
        session.flush()
        replace_scopes(session, account.id, payload.scopes)
        raw, expires = issue_token(session, account, "activate")
        audit(session, "auth.account_created", actor, request_id, {"account_id": str(account.id), "role": account.role})
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ApiException(409, "ACCOUNT_CONFLICT", "账号标识或人员映射已被使用") from None
    return account, raw, expires


def patch_account(session: Session, account_id: UUID, payload: AccountPatchRequest, actor: UUID, request_id: UUID) -> AuthAccount:
    identity_lock(session)
    account = session.scalar(select(AuthAccount).where(AuthAccount.id == account_id).with_for_update())
    if account is None:
        raise ApiException(404, "ACCOUNT_NOT_FOUND", "账号不存在")
    if account.version != payload.expected_version:
        raise ApiException(409, "STATE_CONFLICT", "账号已更新，请刷新后重试")
    if account.role == "admin" and account.status == "active" and ((payload.role and payload.role != "admin") or payload.status == "inactive"):
        count = session.scalar(select(func.count()).select_from(AuthAccount).where(AuthAccount.role == "admin", AuthAccount.status == "active"))
        if count <= 1:
            raise ApiException(409, "LAST_ADMIN_REQUIRED", "必须保留至少一名有效管理员")
    if payload.status == "active" and not account.password_hash:
        raise ApiException(409, "ACTIVATION_REQUIRED", "请先使用一次性口令完成激活")
    person = session.get(Person, account.person_id)
    if "department_id" in payload.model_fields_set:
        require_department(session, payload.department_id)
        person.department_id = payload.department_id
    if payload.display_name is not None:
        person.display_name = payload.display_name
    if payload.role is not None:
        account.role = payload.role
    if payload.status is not None:
        account.status = payload.status
        person.status = "active" if payload.status == "active" else "inactive"
        if payload.status == "inactive":
            session.execute(update(AuthActionToken).where(AuthActionToken.account_id == account.id, AuthActionToken.used_at.is_(None)).values(used_at=now()))
    if payload.scopes is not None:
        replace_scopes(session, account.id, payload.scopes)
    account.version += 1
    account.updated_at = person.updated_at = now()
    revoke_sessions(session, account.id)
    audit(session, "auth.account_updated", actor, request_id, {"account_id": str(account.id), "version": account.version, "status": account.status, "role": account.role})
    session.commit()
    return account
