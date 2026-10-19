from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.identity_access.api.schemas import (
    AccountCreateRequest, AccountPage, AccountPatchRequest, AccountView,
    BootstrapRequest, BootstrapStatus, DepartmentCreateRequest,
    DepartmentPatchRequest, DepartmentView, LoginRequest, OperationResult,
    PasswordChangeRequest, ReauthenticationRequest, SessionView,
    TokenIssuedView, TokenRedemptionRequest,
)
from app.modules.identity_access.api.authorization import require_capability
from app.modules.identity_access.application import service
from app.modules.identity_access.application.passwords import csrf_token
from app.platform.db.models import AuthAccount, AuthSession, Department, Person, Resource, NotificationPreference
from app.platform.db.session import database_session
from app.platform.http.errors import ApiException
from app.platform.http.pagination import PageSize
from app.platform.http.schemas import ResponseMeta, SuccessEnvelope


def require_local_mode(request: Request) -> None:
    if request.app.state.settings.auth_provider != "local":
        raise ApiException(404, "LOCAL_AUTH_NOT_ENABLED", "本地账号登录未启用")


router = APIRouter(tags=["identity"], dependencies=[Depends(require_local_mode)])
DB = Annotated[Session, Depends(database_session)]
Admin = Annotated[object, Depends(require_capability("identity.manage"))]


def current_local(request: Request) -> service.LocalPrincipal:
    principal = getattr(request.state, "local_principal", None)
    if principal is None:
        raise ApiException(401, "AUTHENTICATION_REQUIRED", "请先登录")
    return principal


Local = Annotated[service.LocalPrincipal, Depends(current_local)]

from app.platform.http.schemas import StrictModel
from pydantic import Field

class NotificationPreferenceView(StrictModel):
    show_due: bool
    version: int

class NotificationPreferencePatch(StrictModel):
    expected_version: int = Field(ge=1)
    show_due: bool

class DepartmentManagementPage(StrictModel):
    items: list[DepartmentView]
    pagination: dict[str,int|bool]

@router.get('/admin/departments',response_model=SuccessEnvelope[DepartmentManagementPage],operation_id='listManagedDepartments')
def managed_departments(request:Request,_admin:Admin,session:DB,page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100)):
    total=session.scalar(select(func.count()).select_from(Department))
    rows=session.scalars(select(Department).order_by(Department.name,Department.id).offset((page-1)*page_size).limit(page_size)).all()
    return SuccessEnvelope(data=DepartmentManagementPage(items=[DepartmentView(id=r.id,name=r.name,parent_id=r.parent_id,status=r.status,version=r.version) for r in rows],pagination=dict(page=page,page_size=page_size,total=total,has_next=page*page_size<total)),error=None,meta=ResponseMeta(request_id=request.state.request_id))

@router.get('/me/notification-preferences',response_model=SuccessEnvelope[NotificationPreferenceView],operation_id='getNotificationPreferences')
def get_preferences(request:Request,principal:Local,session:DB):
    row=session.get(NotificationPreference,principal.person_id)
    return SuccessEnvelope(data=NotificationPreferenceView(show_due=row.show_due if row else True,version=row.version if row else 1),error=None,meta=ResponseMeta(request_id=request.state.request_id))

@router.patch('/me/notification-preferences',response_model=SuccessEnvelope[NotificationPreferenceView],operation_id='patchNotificationPreferences')
def patch_preferences(payload:NotificationPreferencePatch,request:Request,principal:Local,session:DB):
    # Serialize the absent-row case as well as updates to avoid lost preferences.
    session.scalar(select(Person).where(Person.id==principal.person_id).with_for_update())
    row=session.scalar(select(NotificationPreference).where(NotificationPreference.person_id==principal.person_id).with_for_update())
    if payload.expected_version != (row.version if row else 1):raise ApiException(409,'STATE_CONFLICT','提醒设置已变化，请刷新后重试')
    if row is None:
        row=NotificationPreference(person_id=principal.person_id,version=1);session.add(row)
    row.show_due=payload.show_due;row.version+=1;session.commit()
    return SuccessEnvelope(data=NotificationPreferenceView(show_due=row.show_due,version=row.version),error=None,meta=ResponseMeta(request_id=request.state.request_id))


def meta(request: Request) -> ResponseMeta:
    return ResponseMeta(request_id=request.state.request_id)


def request_id(request: Request) -> UUID:
    return UUID(str(request.state.request_id))


def client_ip(request: Request) -> str:
    # Uvicorn's configured proxy trust controls the address; do not trust an
    # arbitrary X-Forwarded-For header in the application.
    return request.client.host if request.client else "unknown"


def session_view(request: Request, principal: service.LocalPrincipal, raw: str) -> SessionView:
    return SessionView(account_id=principal.account_id, person_id=principal.person_id, username=principal.username,
        display_name=principal.display_name, department_id=principal.department_id, role=principal.role,
        capabilities=sorted(principal.capabilities), expires_at=principal.expires_at,
        csrf_token=csrf_token(raw), must_change_password=principal.must_change_password,
        read_only=request.app.state.settings.read_only)


def login_response(request: Request, response: Response, raw: str) -> SessionView:
    settings = request.app.state.settings
    principal = service.resolve_session(request.app.state.database_engine, settings, raw)
    if principal is None:
        raise ApiException(503, "DEPENDENCY_UNAVAILABLE", "登录会话创建失败，请重试")
    response.set_cookie(settings.auth_cookie_name, raw, httponly=True, secure=settings.auth_cookie_secure,
                        samesite="lax", max_age=settings.auth_session_seconds, path="/")
    response.headers["Cache-Control"] = "no-store"
    return session_view(request, principal, raw)


@router.get("/auth/bootstrap-status", response_model=SuccessEnvelope[BootstrapStatus], operation_id="getBootstrapStatus")
def bootstrap_status(request: Request, session: DB):
    ready = service.initialized(session)
    settings = request.app.state.settings
    return SuccessEnvelope(data=BootstrapStatus(initialized=ready, setup_available=not ready and bool(settings.auth_bootstrap_token) and not settings.read_only, read_only=settings.read_only), error=None, meta=meta(request))


@router.post("/auth/bootstrap", response_model=SuccessEnvelope[SessionView], status_code=201, operation_id="bootstrapAdministrator")
def bootstrap(request: Request, response: Response, payload: BootstrapRequest, session: DB):
    settings = request.app.state.settings
    service.bootstrap(session, settings, payload.username, payload.display_name, payload.password.get_secret_value(), payload.bootstrap_token.get_secret_value(), request_id(request))
    _, raw = service.login(session, settings, payload.username, payload.password.get_secret_value(), client_ip(request), request_id(request))
    return SuccessEnvelope(data=login_response(request, response, raw), error=None, meta=meta(request))


@router.post("/auth/login", response_model=SuccessEnvelope[SessionView], operation_id="loginLocalAccount")
def login(request: Request, response: Response, payload: LoginRequest, session: DB):
    _, raw = service.login(session, request.app.state.settings, payload.username, payload.password.get_secret_value(), client_ip(request), request_id(request))
    return SuccessEnvelope(data=login_response(request, response, raw), error=None, meta=meta(request))


@router.get("/auth/session", response_model=SuccessEnvelope[SessionView], operation_id="getLocalSession")
def get_session(request: Request, principal: Local):
    raw = request.cookies[request.app.state.settings.auth_cookie_name]
    return SuccessEnvelope(data=session_view(request, principal, raw), error=None, meta=meta(request))


@router.post("/auth/logout", response_model=SuccessEnvelope[OperationResult], operation_id="logoutLocalSession")
def logout(request: Request, response: Response, session: DB):
    principal = getattr(request.state, "local_principal", None)
    if principal:
        row = session.get(AuthSession, principal.session_id)
        if row:
            row.revoked_at = service.now()
        service.audit(session, "auth.logout", principal.person_id, request_id(request))
        session.commit()
    response.delete_cookie(request.app.state.settings.auth_cookie_name, path="/")
    return SuccessEnvelope(data=OperationResult(message="已退出登录"), error=None, meta=meta(request))


@router.post("/auth/change-password", response_model=SuccessEnvelope[OperationResult], operation_id="changeLocalPassword")
def change_password(request: Request, response: Response, payload: PasswordChangeRequest, principal: Local, session: DB):
    service.change_password(session, principal, payload.current_password.get_secret_value(), payload.new_password.get_secret_value(), request_id(request), client_ip(request))
    response.delete_cookie(request.app.state.settings.auth_cookie_name, path="/")
    return SuccessEnvelope(data=OperationResult(message="密码已修改，请重新登录"), error=None, meta=meta(request))


@router.post("/auth/reauthenticate", response_model=SuccessEnvelope[OperationResult], operation_id="reauthenticateLocalSession")
def reauthenticate(request: Request, payload: ReauthenticationRequest, principal: Local, session: DB):
    service.verify_current_password(session, principal, payload.password.get_secret_value(), client_ip(request), request_id(request))
    row = session.get(AuthSession, principal.session_id)
    row.authenticated_at = service.now()
    service.audit(session, "auth.reauthenticated", principal.person_id, request_id(request))
    session.commit()
    return SuccessEnvelope(data=OperationResult(message="已重新验证身份"), error=None, meta=meta(request))


@router.post("/auth/activate", response_model=SuccessEnvelope[OperationResult], operation_id="redeemAccountToken")
def activate(request: Request, payload: TokenRedemptionRequest, session: DB):
    service.redeem_token(session, payload.action_token.get_secret_value(), payload.new_password.get_secret_value(), request_id(request))
    return SuccessEnvelope(data=OperationResult(message="账号密码已设置，请登录"), error=None, meta=meta(request))


@router.get("/admin/accounts", response_model=SuccessEnvelope[AccountPage], operation_id="listLocalAccounts")
def accounts(request: Request, _admin: Admin, session: DB, page: int = Query(1, ge=1), page_size: PageSize = Query(25)):
    total = int(session.scalar(select(func.count()).select_from(AuthAccount)) or 0)
    rows = session.scalars(select(AuthAccount).order_by(AuthAccount.created_at, AuthAccount.id).offset((page-1)*page_size).limit(page_size)).all()
    data = AccountPage(items=[service.account_view(session,a) for a in rows], pagination={"page":page,"page_size":int(page_size),"total":total,"has_next":page*page_size<total})
    return SuccessEnvelope(data=data, error=None, meta=meta(request))


@router.post("/admin/accounts", response_model=SuccessEnvelope[TokenIssuedView], status_code=201, operation_id="createLocalAccount")
def create_account(request: Request, payload: AccountCreateRequest, principal: Local, _admin: Admin, session: DB):
    account, raw, expires = service.create_account(session, payload, principal.person_id, request_id(request))
    return SuccessEnvelope(data=TokenIssuedView(account=service.account_view(session,account),action_token=raw,expires_at=expires), error=None, meta=meta(request))


@router.patch("/admin/accounts/{account_id}", response_model=SuccessEnvelope[AccountView], operation_id="patchLocalAccount")
def patch_account(account_id: UUID, request: Request, payload: AccountPatchRequest, principal: Local, _admin: Admin, session: DB):
    account = service.patch_account(session, account_id, payload, principal.person_id, request_id(request))
    return SuccessEnvelope(data=service.account_view(session,account), error=None, meta=meta(request))


@router.post("/admin/accounts/{account_id}/recovery-token", response_model=SuccessEnvelope[TokenIssuedView], operation_id="issueAccountRecoveryToken")
def recovery_token(account_id: UUID, request: Request, principal: Local, _admin: Admin, session: DB):
    account = session.scalar(select(AuthAccount).where(AuthAccount.id == account_id).with_for_update())
    if not account:
        raise ApiException(404, "ACCOUNT_NOT_FOUND", "账号不存在")
    if account.status == "inactive":
        raise ApiException(403, "ACCOUNT_INACTIVE", "请先明确恢复该账号的使用状态")
    raw, expires = service.issue_token(session, account, "activate" if account.status == "pending" else "recover")
    service.revoke_sessions(session, account.id)
    service.audit(session, "auth.recovery_issued", principal.person_id, request_id(request), {"account_id":str(account.id)})
    session.commit()
    return SuccessEnvelope(data=TokenIssuedView(account=service.account_view(session,account),action_token=raw,expires_at=expires),error=None,meta=meta(request))


def department_view(row: Department) -> DepartmentView:
    return DepartmentView(id=row.id,name=row.name,parent_id=row.parent_id,status=row.status,version=row.version)


def validate_parent(session: Session, target_id: UUID | None, department_id: UUID | None = None) -> None:
    seen = {department_id} if department_id else set()
    while target_id is not None:
        if target_id in seen:
            raise ApiException(422, "DEPARTMENT_CYCLE", "部门上级不能形成环路")
        seen.add(target_id)
        parent = session.get(Department,target_id)
        if not parent or parent.status != "active":
            raise ApiException(422,"REFERENCE_NOT_FOUND","上级部门不存在或已停用")
        target_id = parent.parent_id


@router.post("/admin/departments", response_model=SuccessEnvelope[DepartmentView], status_code=201, operation_id="createDepartment")
def create_department(request: Request, payload: DepartmentCreateRequest, principal: Local, _admin: Admin, session: DB):
    service.identity_lock(session)
    validate_parent(session,payload.parent_id)
    row = Department(name=payload.name,parent_id=payload.parent_id,status="active")
    session.add(row)
    session.flush()
    service.audit(session,"auth.department_created",principal.person_id,request_id(request),{"department_id":str(row.id)})
    session.commit()
    return SuccessEnvelope(data=department_view(row),error=None,meta=meta(request))


@router.patch("/admin/departments/{department_id}", response_model=SuccessEnvelope[DepartmentView], operation_id="patchDepartment")
def patch_department(department_id: UUID, request: Request, payload: DepartmentPatchRequest, principal: Local, _admin: Admin, session: DB):
    service.identity_lock(session)
    row = session.scalar(select(Department).where(Department.id==department_id).with_for_update())
    if not row:
        raise ApiException(404,"REFERENCE_NOT_FOUND","部门不存在")
    if row.version != payload.expected_version:
        raise ApiException(409,"STATE_CONFLICT","部门已更新，请刷新后重试")
    if "parent_id" in payload.model_fields_set:
        validate_parent(session,payload.parent_id,department_id)
        row.parent_id = payload.parent_id
    if payload.status == "inactive":
        counts = [session.scalar(select(func.count()).select_from(model).where(condition)) for model,condition in (
            (Department,(Department.parent_id==department_id)&(Department.status=="active")),
            (Person,(Person.department_id==department_id)&(Person.status=="active")),
            (Resource,Resource.owning_department_id==department_id))]
        if any(counts):
            raise ApiException(409,"DEPARTMENT_IN_USE","请先处理该部门的有效子部门、成员和资源归属")
        row.status="inactive"
    elif payload.status:
        row.status=payload.status
    if payload.name is not None:
        row.name=payload.name
    row.version+=1
    row.updated_at=service.now()
    service.audit(session,"auth.department_updated",principal.person_id,request_id(request),{"department_id":str(row.id),"version":row.version})
    session.commit()
    return SuccessEnvelope(data=department_view(row),error=None,meta=meta(request))
