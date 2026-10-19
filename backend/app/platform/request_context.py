from contextvars import ContextVar

current_request_id: ContextVar[str | None] = ContextVar("digital_asset_platform_request_id", default=None)
