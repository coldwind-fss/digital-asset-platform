from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

from app.config import Settings

_SAFE_EXTRA_KEYS = {
    "event",
    "request_id",
    "exception_type",
    "http_method",
    "route_template",
    "status_code",
    "duration_ms",
}


class SafeJsonFormatter(logging.Formatter):
    def __init__(self, service: str, release_id: str) -> None:
        super().__init__()
        self.service = service
        self.release_id = release_id

    def format(self, record: logging.LogRecord) -> str:
        event = getattr(record, "event", "runtime_event")
        safe_event = event if isinstance(event, str) and re.fullmatch(r"[a-z0-9_]{1,64}", event) else "runtime_event"
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname.lower(),
            "service": self.service,
            "release_id": self.release_id,
            # Never serialize arbitrary log messages (e.g. Uvicorn access lines may
            # contain query strings). Only a controlled event name is emitted.
            "message": safe_event,
        }
        for key in _SAFE_EXTRA_KEYS:
            value = getattr(record, key, None)
            if value is not None and isinstance(value, (str, int, float, bool)):
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(settings: Settings) -> None:
    root = logging.getLogger()
    root.setLevel(settings.log_level)
    if not root.handlers:
        root.addHandler(logging.StreamHandler(sys.stdout))
    for handler in root.handlers:
        handler.setFormatter(SafeJsonFormatter(settings.app_name, settings.release_id))


def log_request(
    *,
    request_id: str,
    method: str,
    route_template: str,
    status_code: int,
    duration_ms: float,
) -> None:
    logging.getLogger("digital_asset_platform.http").info(
        "request_completed",
        extra={
            "event": "request_completed",
            "request_id": request_id,
            "http_method": method,
            "route_template": route_template,
            "status_code": status_code,
            "duration_ms": duration_ms,
        },
    )
