from __future__ import annotations

import time
import uuid
from urllib.parse import urlsplit

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import Settings
from app.platform.http.schemas import ApiErrorBody, ErrorEnvelope, ResponseMeta
from app.platform.logging import log_request
from app.platform.request_context import current_request_id


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        incoming = request.headers.get("x-request-id", "")
        try:
            request_id = str(uuid.UUID(incoming))
        except (ValueError, AttributeError):
            request_id = str(uuid.uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        token = current_request_id.set(request_id)
        started = time.perf_counter()
        response_status: int | None = None

        async def send_with_request_id(message: Message) -> None:
            nonlocal response_status
            if message["type"] == "http.response.start":
                response_status = int(message["status"])
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() != b"x-request-id"
                ]
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            if self._host_is_allowed(request.headers.get("host", "")):
                await self.app(scope, receive, send_with_request_id)
            else:
                rejection = JSONResponse(
                    status_code=400,
                    content=ErrorEnvelope(
                        data=None,
                        error=ApiErrorBody(
                            code="INVALID_REQUEST",
                            message="请求主机不在允许范围内",
                            details=[],
                            retryable=False,
                        ),
                        meta=ResponseMeta(request_id=request_id),
                    ).model_dump(mode="json"),
                )
                await rejection(scope, receive, send_with_request_id)
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            route = scope.get("route")
            route_template = getattr(route, "path", "unmatched")
            log_request(
                request_id=request_id,
                method=str(scope.get("method", "")),
                route_template=route_template,
                status_code=response_status or 500,
                duration_ms=duration_ms,
            )
            current_request_id.reset(token)

    def _host_is_allowed(self, authority: str) -> bool:
        if not self.settings.trusted_hosts:
            return True
        try:
            hostname = urlsplit(f"//{authority}").hostname
        except ValueError:
            return False
        if not hostname:
            return False
        return hostname.rstrip(".").lower() in {
            allowed.rstrip(".").lower() for allowed in self.settings.trusted_hosts
        }
