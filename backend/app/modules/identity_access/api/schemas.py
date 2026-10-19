from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, SecretStr, field_validator
from app.platform.http.schemas import StrictModel

Role = Literal["admin", "resource_manager", "member"]


class NamedInput(StrictModel):
    @field_validator("display_name", "name", mode="before", check_fields=False)
    @classmethod
    def normalize_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class UsernameInput(NamedInput):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-z0-9][a-z0-9._-]+$")

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class LoginRequest(UsernameInput):
    password: SecretStr = Field(min_length=1, max_length=256)


class BootstrapRequest(UsernameInput):
    display_name: str = Field(min_length=1, max_length=200)
    password: SecretStr = Field(min_length=12, max_length=256)
    bootstrap_token: SecretStr = Field(min_length=32, max_length=256)


class PasswordChangeRequest(StrictModel):
    current_password: SecretStr = Field(min_length=1, max_length=256)
    new_password: SecretStr = Field(min_length=12, max_length=256)


class ReauthenticationRequest(StrictModel):
    password: SecretStr = Field(min_length=1, max_length=256)


class TokenRedemptionRequest(StrictModel):
    action_token: SecretStr = Field(min_length=20, max_length=256)
    new_password: SecretStr = Field(min_length=12, max_length=256)


class ScopeInput(StrictModel):
    kind: Literal["department", "resource"]
    target_id: UUID
    permission: Literal["read", "manage"]


class AccountCreateRequest(UsernameInput):
    display_name: str = Field(min_length=1, max_length=200)
    person_id: UUID | None = None
    department_id: UUID | None = None
    role: Role = "member"
    scopes: list[ScopeInput] = Field(default_factory=list, max_length=100)


class AccountPatchRequest(NamedInput):
    expected_version: int = Field(ge=1)
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    department_id: UUID | None = None
    role: Role | None = None
    status: Literal["active", "inactive"] | None = None
    scopes: list[ScopeInput] | None = Field(default=None, max_length=100)


class AccountView(StrictModel):
    id: UUID
    person_id: UUID
    username: str
    display_name: str
    department_id: UUID | None
    role: Role
    status: str
    version: int
    scopes: list[ScopeInput]


class TokenIssuedView(StrictModel):
    account: AccountView
    action_token: str
    expires_at: datetime


class AccountPage(StrictModel):
    items: list[AccountView]
    pagination: dict[str, int | bool]


class SessionView(StrictModel):
    account_id: UUID
    person_id: UUID
    username: str
    display_name: str
    department_id: UUID | None
    role: Role
    capabilities: list[str]
    expires_at: datetime
    csrf_token: str
    must_change_password: bool
    read_only: bool = False


class BootstrapStatus(StrictModel):
    initialized: bool
    setup_available: bool
    read_only: bool = False


class OperationResult(StrictModel):
    message: str


class DepartmentCreateRequest(NamedInput):
    name: str = Field(min_length=1, max_length=200)
    parent_id: UUID | None = None


class DepartmentPatchRequest(NamedInput):
    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    parent_id: UUID | None = None
    status: Literal["active", "inactive"] | None = None


class DepartmentView(StrictModel):
    id: UUID
    name: str
    parent_id: UUID | None
    status: str
    version: int
