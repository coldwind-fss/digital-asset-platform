"""Public ports exposed by identity_access to other bounded contexts."""

from app.modules.identity_access.api.authorization import current_subject, require_capability
from app.modules.identity_access.domain.policy import PolicySubject
from app.modules.identity_access.api.middleware import LocalIdentityMiddleware


def attach_session_scope(session, request):
    principal = getattr(request.state, "local_principal", None)
    if principal is not None:
        from app.modules.identity_access.application.scope import attach_scope
        attach_scope(session, principal)


def get_auth_router():
    from app.modules.identity_access.api.routes import router
    return router


def has_login_account(session,person_id):
    from sqlalchemy import select
    from app.platform.db.models import AuthAccount
    return session.scalar(select(AuthAccount.id).where(AuthAccount.person_id==person_id).limit(1)) is not None

__all__ = ["PolicySubject", "current_subject", "require_capability", "attach_session_scope", "LocalIdentityMiddleware", "get_auth_router"]
