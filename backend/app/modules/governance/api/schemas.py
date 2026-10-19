from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field,field_validator,model_validator

from app.platform.http.schemas import StrictModel


class ChangeOwnerProposal(StrictModel):
    action: Literal["change_owner"]
    assignment_id: UUID | None = None
    to_person_id: UUID


class ChangeOrganizationProposal(StrictModel):
    action: Literal["change_organization"]
    company_id: UUID | None = None
    owning_department_id: UUID | None = None


class RemoveUseProposal(StrictModel):
    action: Literal["remove_use"]
    assignment_id: UUID


class TransferControllerProposal(StrictModel):
    action: Literal["transfer_controller"]
    assignment_id: UUID
    to_person_id: UUID


class ChangeBindingProposal(StrictModel):
    action: Literal["change_binding"]
    binding_id: UUID
    new_contact_identity_id: UUID
    purpose: Literal["registration", "login", "recovery", "mfa"] | None = None


class ChangeMailboxAddressProposal(StrictModel):
    action: Literal["change_mailbox_address"]
    binding_id: UUID | None = None
    new_contact_identity_id: UUID


class ChangeManagementRelationProposal(StrictModel):
    action: Literal["change_management_relation"]
    relation_id: UUID
    proposed_target_id: UUID


class RevokeCredentialGrantProposal(StrictModel):
    action: Literal["revoke_credential_grant"]
    credential_grant_id: UUID
    operation_id: UUID


class RevokeCredentialProposal(StrictModel):
    action: Literal["revoke_credential"]
    credential_id: UUID
    operation_id: UUID


class GrantUseProposal(StrictModel):
    action: Literal["grant_use"]
    person_id: UUID


class ChangeVisibilityProposal(StrictModel):
    action: Literal["change_visibility"]
    visibility_scope: Literal["restricted","department","company"]


class RotateCredentialProposal(StrictModel):
    action: Literal["rotate_credential"]
    credential_id: UUID
    operation_id: UUID


class ReplaceKeyProposal(StrictModel):
    action: Literal["replace_key"]
    replacement_resource_id: UUID


class DisableResourceProposal(StrictModel):
    action: Literal["disable_resource"]


class RetireResourceProposal(StrictModel):
    action: Literal["retire_resource"]


class ReactivateResourceProposal(StrictModel):
    action: Literal["reactivate_resource"]


ChangeItemProposal = Annotated[
    ChangeOwnerProposal
    | ChangeOrganizationProposal
    | RemoveUseProposal
    | TransferControllerProposal
    | ChangeBindingProposal
    | ChangeMailboxAddressProposal
    | ChangeManagementRelationProposal
    | RevokeCredentialGrantProposal
    | RevokeCredentialProposal
    | GrantUseProposal
    | ChangeVisibilityProposal
    | RotateCredentialProposal
    | ReplaceKeyProposal
    | DisableResourceProposal
    | RetireResourceProposal
    | ReactivateResourceProposal,
    Field(discriminator="action"),
]


class ChangeCaseCreate(StrictModel):
    case_type: Literal["change", "transfer", "offboard"]
    reason: str = Field(min_length=1, max_length=2000)
    coordinator_person_id: UUID
    subject_person_id: UUID | None = None


class ChangeCasePatch(StrictModel):
    expected_version: int = Field(ge=1)
    reason: str | None = Field(default=None, min_length=1, max_length=2000)
    coordinator_person_id: UUID | None = None
    subject_person_id: UUID | None = None

    @model_validator(mode='after')
    def require_changes(self):
        if not self.model_fields_set-{'expected_version'}:raise ValueError('至少修改一项')
        return self


class ChangeItemCreate(StrictModel):
    resource_id: UUID
    assignee_person_id: UUID | None = None
    proposal: ChangeItemProposal


class ChangeItemPatch(StrictModel):
    expected_version: int = Field(ge=1)
    assignee_person_id: UUID | None = None
    proposal: ChangeItemProposal | None = None

    @model_validator(mode='after')
    def require_changes(self):
        if not self.model_fields_set-{'expected_version'}:raise ValueError('至少修改一项')
        return self


class ExpectedVersionRequest(StrictModel):
    expected_version: int = Field(ge=1)
    closure_note: str | None = Field(default=None, min_length=1, max_length=2000)


class VersionReasonRequest(StrictModel):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=2000)


class RecordExecutionRequest(StrictModel):
    expected_version: int = Field(ge=1)
    evidence_ids: list[UUID] = Field(min_length=1, max_length=20)
    non_secret_result: str | None = Field(default=None, max_length=4000)
    outcome: Literal["succeeded", "failed"] = "succeeded"

    @field_validator('non_secret_result')
    @classmethod
    def reject_secret_result(cls,value):
        import re
        if value and re.search(r'sk-[A-Za-z0-9_-]{20,}|(?:password|secret|密码|密钥)\s*[:=]',value,re.I):raise ValueError('执行结果不得包含秘密')
        return value


class ConfirmChangeRequest(StrictModel):
    expected_version: int = Field(ge=1)
    confirmation_note: str = Field(min_length=1, max_length=2000)


class ChangeCaseView(StrictModel):
    available_actions: list[str] = Field(default_factory=list)
    id: UUID
    case_type: Literal["change", "transfer", "offboard"]
    subject_person_id: UUID | None
    coordinator_person_id: UUID
    reason: str
    status: Literal["draft", "active", "completed", "completed_with_exceptions", "cancelled"]
    version: int
    created_at: datetime
    closed_at: datetime | None


class ChangeItemView(StrictModel):
    available_actions: list[str] = Field(default_factory=list)
    id: UUID
    case_id: UUID
    resource_id: UUID
    action: str
    assignee_person_id: UUID | None
    proposal: ChangeItemProposal
    status: Literal["pending", "in_progress", "awaiting_confirmation", "completed", "cancelled", "failed", "cancellation_requested"]
    version: int
    non_secret_result: str | None
    executed_by_person_id: UUID | None = None
    confirmed_by_person_id: UUID | None = None
    executed_at: datetime | None = None
    confirmed_at: datetime | None = None
    execution_history: list[dict] = Field(default_factory=list)


class Pagination(StrictModel):
    page: int
    page_size: int
    total: int
    has_next: bool


class ChangeCasePage(StrictModel):
    items: list[ChangeCaseView]
    pagination: Pagination


class ChangeItemPage(StrictModel):
    items: list[ChangeItemView]
    pagination: Pagination
