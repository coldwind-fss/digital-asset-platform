from __future__ import annotations

from uuid import UUID

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import Settings
from app.modules.identity_access.public import PolicySubject


class TestIdentityMiddleware:
    """Explicit test identity adapter; it is inert outside development/test mode."""

    _allowed_capabilities = frozenset(
        {
            "binding.read",
            "binding.write",
            "credential.grant",
            "credential.read",
            "credential.write",
            "directory.read",
            "governance.confirm",
            "governance.read",
            "governance.write",
            "materials.read",
            "materials.write",
            "resource.read",
            "resource.write",
        }
    )

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self.settings.auth_provider != "test":
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive=receive)
        raw_subject = request.headers.get("x-dap-test-subject")
        if raw_subject:
            try:
                subject_id = str(UUID(raw_subject))
            except ValueError:
                subject_id = None
            raw_capabilities = request.headers.get("x-dap-test-capabilities", "")
            capabilities = frozenset(
                capability.strip()
                for capability in raw_capabilities.split(",")
                if capability.strip() in self._allowed_capabilities
            )
            scope.setdefault("state", {})["policy_subject"] = PolicySubject(
                subject_id=subject_id,
                capabilities=capabilities,
                authenticated=subject_id is not None,
            )
        await self.app(scope, receive, send)
