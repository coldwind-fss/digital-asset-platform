from __future__ import annotations

from uuid import UUID

from pydantic import Field

from app.platform.http.schemas import StrictModel


class OrganizationSummary(StrictModel):
    id: UUID
    display_name: str


class PersonPickerOption(StrictModel):
    id: UUID
    display_name: str
    department: OrganizationSummary | None
    status: str


class DepartmentPickerOption(StrictModel):
    id: UUID
    display_name: str
    parent_department_id: UUID | None
    status: str = Field(max_length=40)


class CompanyPickerOption(StrictModel):
    id: UUID
    display_name: str
    status: str = Field(max_length=40)


class Pagination(StrictModel):
    page: int
    page_size: int
    total: int
    has_next: bool


class PersonPage(StrictModel):
    items: list[PersonPickerOption]
    pagination: Pagination


class DepartmentPage(StrictModel):
    items: list[DepartmentPickerOption]
    pagination: Pagination


class CompanyPage(StrictModel):
    items: list[CompanyPickerOption]
    pagination: Pagination
