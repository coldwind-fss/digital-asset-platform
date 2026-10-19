from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.platform.http.schemas import ApiErrorBody, ErrorEnvelope, FieldError, ResponseMeta
from app.platform.request_context import current_request_id

logger = logging.getLogger("digital_asset_platform.errors")


class ApiException(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        details: list[FieldError] | None = None,
    ) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details or []


_HTTP_ERRORS: dict[int, tuple[str, str, bool]] = {
    400: ("INVALID_REQUEST", "请求格式无效", False),
    401: ("AUTHENTICATION_REQUIRED", "请先登录", False),
    403: ("PERMISSION_DENIED", "当前操作不被允许", False),
    404: ("RESOURCE_NOT_FOUND", "资源不存在或不可见", False),
    405: ("METHOD_NOT_ALLOWED", "不支持此请求方法", False),
    409: ("STATE_TRANSITION_INVALID", "当前状态冲突，请刷新后重试", False),
    410: ("RESOURCE_EXPIRED", "请求内容已过期，请重新操作", False),
    413: ("PAYLOAD_TOO_LARGE", "请求内容过大", False),
    415: ("UNSUPPORTED_MEDIA_TYPE", "不支持此内容类型", False),
    422: ("VALIDATION_FAILED", "请检查填写内容", False),
    429: ("RATE_LIMITED", "操作过于频繁，请稍后重试", True),
    500: ("INTERNAL_ERROR", "服务内部错误，请提供请求编号联系管理员", False),
    503: ("DEPENDENCY_UNAVAILABLE", "服务暂不可用，请稍后重试", True),
}


def _request_id(request: Request) -> str:
    return (
        getattr(request.state, "request_id", None)
        or current_request_id.get()
        or str(uuid.uuid4())
    )


def _response(request: Request, status_code: int, error: ApiErrorBody) -> JSONResponse:
    request_id = _request_id(request)
    body = ErrorEnvelope(
        data=None,
        error=error,
        meta=ResponseMeta(request_id=request_id),
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
        headers={"X-Request-ID": request_id},
    )


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiException)
    async def handle_api_exception(request: Request, exc: ApiException) -> JSONResponse:
        return _response(
            request,
            exc.status_code,
            ApiErrorBody(
                code=exc.code,
                message=exc.message,
                details=exc.details,
                retryable=exc.retryable,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        issues = exc.errors()
        invalid_json = any(issue.get("type") == "json_invalid" for issue in issues)
        details: list[FieldError] = []
        if not invalid_json:
            for issue in issues:
                location = issue.get("loc", ())
                field = ".".join(str(part) for part in location if part != "body") or "request"
                details.append(
                    FieldError(
                        field=field,
                        code="REQUIRED" if issue.get("type") == "missing" else "INVALID_VALUE",
                        message="此字段为必填项" if issue.get("type") == "missing" else "字段格式不正确",
                    )
                )
        return _response(
            request,
            400 if invalid_json else 422,
            ApiErrorBody(
                code="INVALID_JSON" if invalid_json else "VALIDATION_FAILED",
                message="请求 JSON 格式无效" if invalid_json else "请检查填写内容",
                details=details,
                retryable=False,
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code, message, retryable = _HTTP_ERRORS.get(
            exc.status_code,
            ("REQUEST_REJECTED", "请求未能完成", False),
        )
        return _response(
            request,
            exc.status_code,
            ApiErrorBody(code=code, message=message, details=[], retryable=retryable),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "unhandled_request_error",
            extra={
                "event": "unhandled_request_error",
                "request_id": _request_id(request),
                "exception_type": type(exc).__name__,
            },
        )
        return _response(
            request,
            500,
            ApiErrorBody(
                code="INTERNAL_ERROR",
                message="服务内部错误，请提供请求编号联系管理员",
                details=[],
                retryable=False,
            ),
        )
