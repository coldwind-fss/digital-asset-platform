from __future__ import annotations

from typing import Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResponseMeta(StrictModel):
    request_id: UUID


class FieldError(StrictModel):
    field: str = Field(min_length=1)
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    message: str = Field(min_length=1)


class ApiErrorBody(StrictModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    message: str = Field(min_length=1)
    details: list[FieldError] = Field(default_factory=list)
    retryable: bool


class SuccessEnvelope(StrictModel, Generic[T]):
    data: T
    error: Literal[None]
    meta: ResponseMeta


class ErrorEnvelope(StrictModel):
    data: Literal[None]
    error: ApiErrorBody
    meta: ResponseMeta
