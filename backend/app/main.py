from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.config import Settings
from app.modules.credentials.public import router as credentials_router
from app.modules.credentials.public import get_operations_router
from app.modules.bindings.public import router as bindings_router
from app.modules.directory.public import router as directory_router
from app.modules.governance.public import router as governance_router
from app.modules.materials.public import router as materials_router
from app.modules.materials.public import get_files_router
from app.modules.provenance.public import router as provenance_router
from app.modules.subscriptions.public import router as subscriptions_router
from app.modules.integrations.public import router as integrations_router
from app.modules.resources.public import router as resources_router
from app.modules.resources.public import get_facts_router, get_graph_router
from app.modules.directory.public import get_catalog_router
from app.modules.identity_access.public import LocalIdentityMiddleware, get_auth_router
from app.platform.http.errors import install_exception_handlers
from app.platform.http.test_identity import TestIdentityMiddleware
from app.platform.http.middleware import RequestContextMiddleware
from app.platform.db.target import create_database_engine, verify_database_identity, verify_runtime_schema
from app.platform.logging import configure_logging
from app.platform.db.unit_of_work import BusinessUnitOfWorkMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings.from_environment()
    configure_logging(resolved_settings)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        engine = None
        if resolved_settings.database_url:
            engine = create_database_engine(resolved_settings)

            def verify_startup_target() -> None:
                with engine.connect() as connection:
                    verify_database_identity(
                        connection,
                        expected_database=resolved_settings.expected_database or "",
                        expected_instance_id=resolved_settings.instance_id or "",
                        expected_environment=resolved_settings.app_env,
                    )
                    if resolved_settings.auth_provider == "local":
                        verify_runtime_schema(connection)

            try:
                await asyncio.to_thread(verify_startup_target)
            except Exception:
                engine.dispose()
                raise RuntimeError("Digital Asset Platform database is unavailable or its instance/schema marker is incompatible") from None
        application.state.database_engine = engine
        try:
            yield
        finally:
            if engine is not None:
                engine.dispose()

    application = FastAPI(
        title="数字资产管理中台 API",
        version="0.1.0",
        description="数字资产管理中台 API。业务接口仅在认证、权限与数据层就绪后按阶段开放。",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    application.state.settings = resolved_settings
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Idempotency-Key",
            "X-CSRF-Token",
            "X-Request-ID",
            "X-DAP-Test-Subject",
            "X-DAP-Test-Capabilities",
        ],
        expose_headers=["X-Request-ID", "Retry-After", "Idempotency-Replayed"],
    )
    # Keep request context outermost so even host/CORS rejections carry a request ID.
    application.add_middleware(BusinessUnitOfWorkMiddleware)
    application.add_middleware(LocalIdentityMiddleware, settings=resolved_settings)
    application.add_middleware(TestIdentityMiddleware, settings=resolved_settings)
    application.add_middleware(RequestContextMiddleware, settings=resolved_settings)
    install_exception_handlers(application)
    application.include_router(health_router, prefix="/api/v1")
    application.include_router(directory_router, prefix="/api/v1")
    application.include_router(get_facts_router(), prefix="/api/v1")
    application.include_router(get_graph_router(), prefix="/api/v1")
    application.include_router(resources_router, prefix="/api/v1")
    application.include_router(get_catalog_router(), prefix="/api/v1")
    application.include_router(bindings_router, prefix="/api/v1")
    application.include_router(credentials_router, prefix="/api/v1")
    application.include_router(get_operations_router(), prefix="/api/v1")
    application.include_router(governance_router, prefix="/api/v1")
    application.include_router(materials_router, prefix="/api/v1")
    application.include_router(get_files_router(), prefix="/api/v1")
    application.include_router(provenance_router, prefix="/api/v1")
    application.include_router(subscriptions_router, prefix="/api/v1")
    application.include_router(integrations_router, prefix="/api/v1")
    application.include_router(get_auth_router(), prefix="/api/v1")
    return application


app = create_app()
