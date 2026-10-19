from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.platform.http.schemas import StrictModel


class MaterialCreateRequest(StrictModel):
    kind: Literal["entry", "note", "attachment"]
    title: str | None = Field(default=None, max_length=200)
    url: str | None = Field(default=None, max_length=2000)
    body: str | None = Field(default=None, max_length=20000)
    file_ref: str | None = Field(default=None, max_length=200)
    classification: str | None = Field(default=None, pattern="^(normal|restricted|sensitive)$")

    @model_validator(mode="after")
    def validate_payload(self) -> "MaterialCreateRequest":
        if self.kind == "entry" and (not self.url or not self.url.startswith(("http://", "https://"))):
            raise ValueError("入口资料必须使用 HTTP(S) URL")
        if self.kind == "note" and not self.body:
            raise ValueError("说明资料必须有正文")
        if self.kind == "attachment" and not self.file_ref:
            raise ValueError("附件资料必须引用已扫描文件")
        if self.kind != "entry" and self.url is not None:
            raise ValueError("只有入口资料可以填写 URL")
        return self


class MaterialPatchChanges(StrictModel):
    title: str | None = Field(default=None, max_length=200)
    url: str | None = Field(default=None, max_length=2000)
    body: str | None = Field(default=None, max_length=20000)
    classification: str | None = Field(default=None, pattern="^(normal|restricted|sensitive)$")

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith(("http://", "https://")):
            raise ValueError("入口资料必须使用 HTTP(S) URL")
        return value


class MaterialPatchRequest(StrictModel):
    expected_version: int = Field(ge=1)
    kind: Literal["entry", "note", "attachment"]
    changes: MaterialPatchChanges

    @model_validator(mode="after")
    def require_change(self) -> "MaterialPatchRequest":
        if not self.changes.model_fields_set:
            raise ValueError("至少需要一项资料变更")
        if self.kind == "entry" and "body" in self.changes.model_fields_set:
            raise ValueError("入口资料不支持正文")
        if self.kind == "note" and "url" in self.changes.model_fields_set:
            raise ValueError("说明资料不支持 URL")
        if self.kind == "attachment" and {"url", "body"} & self.changes.model_fields_set:
            raise ValueError("附件资料不支持 URL 或正文")
        return self


class EntryMaterialView(StrictModel):
    id: UUID
    version: int
    kind: Literal["entry"]
    title: str | None
    url: str
    classification: str | None
    created_at: datetime
    updated_at: datetime


class NoteMaterialView(StrictModel):
    id: UUID
    version: int
    kind: Literal["note"]
    title: str | None
    body: str
    classification: str | None
    created_at: datetime
    updated_at: datetime


class AttachmentMaterialView(StrictModel):
    id: UUID
    version: int
    kind: Literal["attachment"]
    title: str | None
    file_ref: UUID
    scan_state: Literal["pending", "clean", "rejected"]
    classification: str | None
    created_at: datetime
    updated_at: datetime


MaterialView = Annotated[EntryMaterialView | NoteMaterialView | AttachmentMaterialView, Field(discriminator="kind")]


class Pagination(StrictModel):
    page: int
    page_size: int
    total: int
    has_next: bool


class MaterialPage(StrictModel):
    items: list[MaterialView]
    pagination: Pagination
