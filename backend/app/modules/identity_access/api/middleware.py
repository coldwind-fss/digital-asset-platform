import asyncio
import hmac
from datetime import UTC, datetime

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import Settings
from app.modules.identity_access.application.passwords import csrf_token
from app.modules.identity_access.application.service import resolve_session
from app.platform.http.errors import _response
from app.platform.http.schemas import ApiErrorBody


class LocalIdentityMiddleware:
    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app, self.settings = app, settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self.settings.auth_provider != "local":
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive=receive)

        async def reject(code: str, message: str, status: int = 403):
            response = _response(request, status, ApiErrorBody(code=code, message=message, retryable=False, details=[]))
            response.headers["Cache-Control"] = "no-store"
            await response(scope, receive, send)

        if request.headers.get("x-dap-test-subject") or request.headers.get("x-dap-test-capabilities"):
            await reject("TEST_IDENTITY_FORBIDDEN", "真实登录模式不接受测试身份")
            return
        engine = getattr(request.app.state, "database_engine", None)
        raw = request.cookies.get(self.settings.auth_cookie_name, "")
        principal = await asyncio.to_thread(resolve_session, engine, self.settings, raw) if raw and engine is not None else None
        if principal:
            scope.setdefault("state", {})["local_principal"] = principal
            scope["state"]["policy_subject"] = principal.policy_subject()
        unsafe = request.method not in {"GET", "HEAD", "OPTIONS"}
        if self.settings.read_only and unsafe and request.url.path not in {
            "/api/v1/auth/login", "/api/v1/auth/logout",
        }:
            await reject("READ_ONLY_EXPERIENCE", "当前为只读体验环境，不支持修改数据或查看凭据")
            return
        public_write = request.url.path in {"/api/v1/auth/bootstrap", "/api/v1/auth/login", "/api/v1/auth/activate"}
        if unsafe and (principal or public_write):
            origin = request.headers.get("origin", "")
            own_origin = f"{request.url.scheme}://{request.url.netloc}"
            if origin not in {*self.settings.allowed_origins, own_origin}:
                await reject("ORIGIN_REJECTED", "请求来源不被允许")
                return
            if principal and not public_write:
                supplied = request.headers.get("x-csrf-token", "")
                if not hmac.compare_digest(supplied.encode("utf-8"), csrf_token(raw).encode("utf-8")):
                    await reject("CSRF_VALIDATION_FAILED", "会话校验已失效，请刷新后重试")
                    return
        if principal and principal.must_change_password and not request.url.path.startswith("/api/v1/auth/"):
            await reject("PASSWORD_CHANGE_REQUIRED", "请先修改初始密码")
            return
        # All authenticated responses can contain private metadata.
        async def no_store(message):
            if message["type"] == "http.response.start" and (principal or request.url.path.startswith("/api/v1/auth/")):
                headers = list(message.get("headers", []))
                headers = [(k,v) for k,v in headers if k.lower() != b"cache-control"]
                headers.append((b"cache-control", b"no-store"))
                message["headers"] = headers
            await send(message)
        await self.app(scope, receive, no_store)
