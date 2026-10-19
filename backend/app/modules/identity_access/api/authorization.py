from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import Request

from app.modules.identity_access.domain.policy import (
    DenialCode,
    PolicyEngine,
    PolicyFacts,
    PolicySubject,
)
from app.platform.http.errors import ApiException

_policy_engine = PolicyEngine()


def current_subject(request: Request) -> PolicySubject:
    """Read only an adapter-populated subject; never trust a client-supplied ID."""
    subject = getattr(request.state, "policy_subject", None)
    if isinstance(subject, PolicySubject):
        return subject
    return PolicySubject(subject_id=None, authenticated=False)


def require_capability(
    capability: str,
    *,
    resource_id: str | Callable[[Request], str] | None = None,
    requires_scope: bool = False,
    requires_action: bool = False,
    credential_access: bool = False,
    facts_reader: Callable[[Request], PolicyFacts] | None = None,
):
    def dependency(request: Request) -> PolicySubject:
        subject = current_subject(request)
        principal = getattr(request.state, "local_principal", None)
        if principal is not None and capability == "credential.read":
            age = (datetime.now(UTC) - principal.authenticated_at).total_seconds()
            if age > request.app.state.settings.auth_recent_seconds:
                raise ApiException(403, "REAUTHENTICATION_REQUIRED", "查看凭据前请重新验证当前密码")
        facts = facts_reader(request) if facts_reader is not None else PolicyFacts()
        target_id = resource_id(request) if callable(resource_id) else resource_id
        decision = _policy_engine.decide(
            subject,
            capability,
            facts=facts,
            resource_id=target_id,
            requires_scope=requires_scope,
            requires_action=requires_action,
            credential_access=credential_access,
        )
        if decision.allowed:
            return subject
        denial = decision.denial_code or DenialCode.PERMISSION_DENIED
        if denial == DenialCode.AUDIT_UNAVAILABLE:
            raise ApiException(
                503,
                "DEPENDENCY_UNAVAILABLE",
                "安全审计暂不可用，已阻止敏感操作",
                retryable=True,
            )
        status_code = (
            404
            if denial == DenialCode.RESOURCE_NOT_FOUND
            else 401
            if denial == DenialCode.AUTHENTICATION_REQUIRED
            else 403
        )
        message = (
            "请先登录"
            if status_code == 401
            else "资源不存在或不可见"
            if status_code == 404
            else "当前操作不被允许"
        )
        raise ApiException(status_code, denial.value, message)

    return dependency
