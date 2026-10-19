from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.platform.http.schemas import StrictModel


CredentialKind = Literal["password", "api_key", "certificate_pin", "other"]
CredentialCapability = Literal["view", "rotate"]


class SecretStageCreate(StrictModel):
    kind: CredentialKind
    secret_value: str = Field(min_length=1, max_length=10000,repr=False,json_schema_extra={"writeOnly":True})
    resource_id: UUID | None = None
    purpose: Literal["attach","replace"] = "attach"


class SecretStageView(StrictModel):
    stage_token: str
    expires_at: datetime


class CredentialAttachRequest(StrictModel):
    expected_version: int = Field(ge=1)
    stage_token: str = Field(min_length=20, max_length=200)
    kind: CredentialKind


class CredentialRevealRequest(StrictModel):
    reason: str = Field(min_length=1, max_length=1000)


class CredentialGrantCreate(StrictModel):
    person_id: UUID
    capability: CredentialCapability
    valid_to: datetime
    reason: str = Field(min_length=1, max_length=1000)
    expected_version: int = Field(ge=1)


class CredentialStorageCorrection(StrictModel):
    expected_version: int = Field(ge=1)
    stage_token: str = Field(min_length=20, max_length=200)
    reason: str = Field(min_length=1, max_length=1000)


class CredentialRevealView(StrictModel):
    secret_value: str


class SafeOperationResult(StrictModel):
    resource_id: UUID | None = None
    credential_id: UUID | None = None
    credential_status: Literal["not_saved", "pending", "saved", "failed"] | None = None


class CredentialOperationView(StrictModel):
    operation_id: UUID
    status: Literal["pending", "succeeded", "failed"]
    safe_result: SafeOperationResult | None
    retryable: bool


class CredentialGrantView(StrictModel):
    id: UUID
    credential_id: UUID
    person_id: UUID
    capability: CredentialCapability
    valid_from: datetime
    valid_to: datetime | None
    reason: str
    version: int
