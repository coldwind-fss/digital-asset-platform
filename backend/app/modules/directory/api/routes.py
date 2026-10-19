from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.modules.directory.api.schemas import (
    CompanyPage,
    CompanyPickerOption,
    DepartmentPage,
    DepartmentPickerOption,
    OrganizationSummary,
    Pagination,
    PersonPage,
    PersonPickerOption,
)
from app.modules.directory.application.service import list_companies, list_departments, list_people
from app.modules.identity_access.public import PolicySubject, require_capability
from app.platform.db.models import Department
from app.platform.db.session import database_session
from app.platform.http.pagination import PageSize
from app.platform.http.schemas import ResponseMeta, SuccessEnvelope

router = APIRouter(tags=["directory"])
SessionDependency = Annotated[Session, Depends(database_session)]
DirectorySubject = Annotated[PolicySubject, Depends(require_capability("directory.read"))]
def _meta(request: Request) -> ResponseMeta:
    return ResponseMeta(request_id=request.state.request_id)


@router.get("/people", response_model=SuccessEnvelope[PersonPage])
def list_people_route(
    request: Request,
    _subject: DirectorySubject,
    session: SessionDependency,
    q: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: PageSize = Query(default=25),
) -> SuccessEnvelope[PersonPage]:
    rows, total = list_people(session, q=q, page=page, page_size=page_size)
    items = []
    for person in rows:
        department = session.get(Department, person.department_id) if person.department_id else None
        items.append(
            PersonPickerOption(
                id=person.id,
                display_name=person.display_name,
                department=OrganizationSummary(id=department.id, display_name=department.name) if department else None,
                status=person.status,
            )
        )
    data = PersonPage(
        items=items,
        pagination=Pagination(page=page, page_size=page_size, total=total, has_next=page * page_size < total),
    )
    return SuccessEnvelope(data=data, error=None, meta=_meta(request))


@router.get("/departments", response_model=SuccessEnvelope[DepartmentPage])
def list_departments_route(
    request: Request,
    _subject: DirectorySubject,
    session: SessionDependency,
    q: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: PageSize = Query(default=25),
) -> SuccessEnvelope[DepartmentPage]:
    rows, total = list_departments(session, q=q, page=page, page_size=page_size)
    data = DepartmentPage(
        items=[
            DepartmentPickerOption(
                id=department.id,
                display_name=department.name,
                parent_department_id=department.parent_id,
                status=department.status,
            )
            for department in rows
        ],
        pagination=Pagination(page=page, page_size=page_size, total=total, has_next=page * page_size < total),
    )
    return SuccessEnvelope(data=data, error=None, meta=_meta(request))


@router.get("/companies", response_model=SuccessEnvelope[CompanyPage])
def list_companies_route(
    request: Request,
    _subject: DirectorySubject,
    session: SessionDependency,
    q: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: PageSize = Query(default=25),
) -> SuccessEnvelope[CompanyPage]:
    rows, total = list_companies(session, q=q, page=page, page_size=page_size)
    data = CompanyPage(
        items=[CompanyPickerOption(id=company.id, display_name=company.name, status=company.status) for company in rows],
        pagination=Pagination(page=page, page_size=page_size, total=total, has_next=page * page_size < total),
    )
    return SuccessEnvelope(data=data, error=None, meta=_meta(request))
