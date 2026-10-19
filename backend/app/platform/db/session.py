from __future__ import annotations

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from app.platform.http.errors import ApiException
from app.modules.identity_access.public import attach_session_scope


def database_session(request: Request) -> Iterator[Session]:
    shared = getattr(request.state, "business_session", None)
    if shared is not None:
        yield shared
        return
    engine = getattr(request.app.state, "database_engine", None)
    if engine is None:
        raise ApiException(503, "DEPENDENCY_UNAVAILABLE", "数字资产管理中台数据库未配置", retryable=True)
    with Session(engine) as session:
        session.info["settings"] = request.app.state.settings
        attach_session_scope(session, request)
        yield session
