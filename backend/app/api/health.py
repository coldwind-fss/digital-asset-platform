from datetime import UTC, datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings
from app.platform.http.errors import ApiException
from app.platform.http.schemas import ResponseMeta, SuccessEnvelope
from app.platform.db.target import DatabaseTargetError, verify_database_identity, verify_runtime_schema

router = APIRouter(prefix="/health", tags=["health"])


class ReadyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    service: str
    release_id: str
    checked_at: datetime


@router.get("/ready", response_model=SuccessEnvelope[ReadyResponse])
def ready(request: Request) -> SuccessEnvelope[ReadyResponse]:
    settings: Settings = request.app.state.settings
    engine = getattr(request.app.state, "database_engine", None)
    if engine is None:
        raise ApiException(
            503,
            "DEPENDENCY_UNAVAILABLE",
            "数字资产管理中台数据库未配置",
            retryable=True,
        )
    try:
        with engine.connect() as connection:
            verify_database_identity(
                connection,
                expected_database=settings.expected_database or "",
                expected_instance_id=settings.instance_id or "",
                expected_environment=settings.app_env,
            )
            if settings.auth_provider == "local":
                verify_runtime_schema(connection)
    except (DatabaseTargetError, SQLAlchemyError):
        raise ApiException(
            503,
            "DEPENDENCY_UNAVAILABLE",
            "数字资产管理中台数据库不可用或 schema 不兼容",
            retryable=True,
        ) from None

    request_id = request.state.request_id
    return SuccessEnvelope[ReadyResponse](
        data=ReadyResponse(
            status="ok",
            service=settings.app_name,
            release_id=settings.release_id,
            checked_at=datetime.now(UTC),
        ),
        error=None,
        meta=ResponseMeta(request_id=request_id),
    )


@router.get("/live", response_model=SuccessEnvelope[ReadyResponse])
def live(request: Request) -> SuccessEnvelope[ReadyResponse]:
    settings: Settings = request.app.state.settings
    request_id = request.state.request_id
    return SuccessEnvelope[ReadyResponse](
        data=ReadyResponse(
            status="ok",
            service=settings.app_name,
            release_id=settings.release_id,
            checked_at=datetime.now(UTC),
        ),
        error=None,
        meta=ResponseMeta(request_id=request_id),
    )
