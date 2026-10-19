from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.modules.identity_access.public import PolicySubject, require_capability
from app.modules.materials.api.schemas import (
    AttachmentMaterialView,
    EntryMaterialView,
    MaterialCreateRequest,
    MaterialPage,
    MaterialPatchRequest,
    MaterialView,
    NoteMaterialView,
    Pagination,
)
from app.modules.materials.application.service import create_material, list_materials, patch_material
from app.platform.db.session import database_session
from app.platform.db.models import Material
from app.platform.http.errors import ApiException
from app.platform.http.pagination import PageSize
from app.platform.http.schemas import ResponseMeta, SuccessEnvelope

router = APIRouter(tags=["resources"])
SessionDependency = Annotated[Session, Depends(database_session)]
ReadSubject = Annotated[PolicySubject, Depends(require_capability("materials.read"))]
WriteSubject = Annotated[PolicySubject, Depends(require_capability("materials.write"))]
def _actor(subject: PolicySubject) -> UUID:
    if not subject.subject_id:
        raise ApiException(401, "AUTHENTICATION_REQUIRED", "请先登录")
    try:
        return UUID(subject.subject_id)
    except ValueError:
        raise ApiException(401, "AUTHENTICATION_REQUIRED", "当前主体 ID 无效") from None


def _request_id(request: Request) -> UUID:
    return UUID(str(request.state.request_id))


def _meta(request: Request) -> ResponseMeta:
    return ResponseMeta(request_id=request.state.request_id)


def _view(material: Material):
    common = {
        "id": material.id,
        "version": material.version,
        "title": material.title,
        "classification": material.classification,
        "created_at": material.created_at,
        "updated_at": material.updated_at,
    }
    if material.kind == "entry":
        if not material.url:
            raise ApiException(503, "DEPENDENCY_UNAVAILABLE", "入口资料元数据不可用", retryable=True)
        return EntryMaterialView(kind="entry", url=material.url, **common)
    if material.kind == "note":
        if not material.body:
            raise ApiException(503, "DEPENDENCY_UNAVAILABLE", "说明资料元数据不可用", retryable=True)
        return NoteMaterialView(kind="note", body=material.body, **common)
    try:
        file_ref = UUID(material.file_ref or "")
    except ValueError:
        raise ApiException(503, "DEPENDENCY_UNAVAILABLE", "附件元数据不可用", retryable=True) from None
    return AttachmentMaterialView(kind="attachment", file_ref=file_ref, scan_state="pending", **common)


@router.get("/resources/{resource_id}/materials", response_model=SuccessEnvelope[MaterialPage])
def list_resource_materials_route(
    request: Request,
    resource_id: UUID,
    _subject: ReadSubject,
    session: SessionDependency,
    page: int = Query(default=1, ge=1),
    page_size: PageSize = Query(default=25),
) -> SuccessEnvelope[MaterialPage]:
    rows, total = list_materials(session, resource_id, page=page, page_size=page_size)
    data = MaterialPage(
        items=[_view(row) for row in rows],
        pagination=Pagination(page=page, page_size=page_size, total=total, has_next=page * page_size < total),
    )
    return SuccessEnvelope(data=data, error=None, meta=_meta(request))


@router.post("/resources/{resource_id}/materials", response_model=SuccessEnvelope[MaterialView], status_code=201)
def create_resource_material_route(
    request: Request,
    resource_id: UUID,
    payload: MaterialCreateRequest,
    subject: WriteSubject,
    session: SessionDependency,
) -> SuccessEnvelope[MaterialView]:
    material = create_material(session, resource_id, payload, actor_id=_actor(subject), request_id=_request_id(request))
    return SuccessEnvelope(data=_view(material), error=None, meta=_meta(request))


@router.patch("/resources/{resource_id}/materials/{material_id}", response_model=SuccessEnvelope[MaterialView])
def patch_resource_material_route(
    request: Request,
    resource_id: UUID,
    material_id: UUID,
    payload: MaterialPatchRequest,
    subject: WriteSubject,
    session: SessionDependency,
) -> SuccessEnvelope[MaterialView]:
    material = patch_material(session, resource_id, material_id, payload, actor_id=_actor(subject), request_id=_request_id(request))
    return SuccessEnvelope(data=_view(material), error=None, meta=_meta(request))
