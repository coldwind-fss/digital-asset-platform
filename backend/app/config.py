"""Validated Digital Asset Platform configuration; this module intentionally never loads dotenv files."""

from __future__ import annotations

import json
import os
import base64
from collections.abc import Mapping
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    app_env: Literal["development", "test", "staging", "production"] = "development"
    app_name: str = "数字资产管理中台 API"
    app_host: str = "127.0.0.1"
    app_port: int = Field(default=8300, ge=1, le=65535)
    app_debug: bool = False
    release_id: str = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    api_base_path: str = "/api/v1"
    allowed_origins: tuple[str, ...] = ("http://localhost:5173",)
    trusted_hosts: tuple[str, ...] = ("localhost", "127.0.0.1", "testserver")
    auth_provider: Literal["disabled", "test", "dingtalk", "local"] = "disabled"
    auth_bootstrap_token: str | None = Field(default=None, min_length=32, max_length=256, repr=False)
    auth_cookie_name: str = Field(default="digital_asset_platform_session", pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    auth_cookie_secure: bool = False
    auth_session_seconds: int = Field(default=43200, ge=300, le=604800)
    auth_idle_seconds: int = Field(default=1800, ge=60, le=86400)
    auth_recent_seconds: int = Field(default=900, ge=30, le=3600)
    mock_data_enabled: bool = False
    # Dedicated synthetic public experience. Auth sessions may change, business
    # commands and credential reveal are denied regardless of account role.
    read_only: bool = False
    database_url: str | None = Field(default=None, repr=False)
    expected_database: str | None = None
    instance_id: str | None = None
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=10, ge=0, le=100)
    db_pool_timeout_seconds: float = Field(default=30, gt=0, le=300)
    credential_master_key: str | None = Field(default=None, repr=False)
    credential_key_version: str = Field(default="key-1", min_length=1, max_length=64)
    credential_read_keys: dict[str,str] = Field(default_factory=dict, repr=False)
    private_file_root: str | None = None
    attachment_scan_required: bool = False

    @field_validator("allowed_origins", "trusted_hosts", mode="before")
    @classmethod
    def parse_json_list(cls, value: object) -> object:
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError("must be a JSON array") from exc
            if not isinstance(parsed, list):
                raise ValueError("must be a JSON array")
            return tuple(parsed)
        if isinstance(value, list):
            return tuple(value)
        return value

    @field_validator("allowed_origins")
    @classmethod
    def validate_origins(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        for origin in values:
            parsed = urlsplit(origin)
            if (
                not origin
                or origin == "*"
                or parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.path
                or parsed.query
                or parsed.fragment
                or parsed.username
                or parsed.password
            ):
                raise ValueError("origins must be explicit HTTP(S) origins")
        return tuple(dict.fromkeys(values))

    @field_validator("trusted_hosts")
    @classmethod
    def validate_hosts(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not host or host == "*" or "/" in host or ":" in host for host in values):
            raise ValueError("trusted hosts must be exact hostnames without ports")
        return tuple(dict.fromkeys(host.lower().rstrip(".") for host in values))

    @field_validator("credential_master_key")
    @classmethod
    def validate_credential_master_key(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            decoded_key = base64.urlsafe_b64decode(value.encode("ascii"))
        except (ValueError, UnicodeEncodeError):
            raise ValueError("must be URL-safe base64") from None
        if len(decoded_key) != 32:
            raise ValueError("must decode to 32 bytes")
        return value

    @field_validator("credential_read_keys",mode="before")
    @classmethod
    def validate_read_keys(cls,value):
        if isinstance(value,str):
            try:value=json.loads(value)
            except ValueError:raise ValueError("must be a JSON key-version map") from None
        if not isinstance(value,dict) or len(value)>20:raise ValueError("invalid key-version map")
        for key,material in value.items():
            if not isinstance(key,str) or len(key)>64:raise ValueError("invalid key version")
            cls.validate_credential_master_key(material)
        return value

    @field_validator("api_base_path")
    @classmethod
    def validate_api_base_path(cls, value: str) -> str:
        if not value.startswith("/") or value.endswith("/") or "//" in value:
            raise ValueError("must be an absolute path without a trailing slash")
        if value != "/api/v1":
            raise ValueError("The API protocol path is fixed at /api/v1")
        return value

    @model_validator(mode="after")
    def validate_environment_boundaries(self) -> "Settings":
        if self.app_env in {"staging", "production"} and not self.credential_master_key:
            raise ValueError("credential_master_key is required outside development/test")
        if self.database_url is not None:
            if not self.expected_database or not self.instance_id:
                raise ValueError("database_url requires expected_database and instance_id")
        elif self.expected_database is not None or self.instance_id is not None:
            raise ValueError("expected_database and instance_id require database_url")
        if self.auth_provider == "test" and self.app_env not in {"development", "test"}:
            raise ValueError("test identity provider is allowed only in development/test")
        if self.mock_data_enabled and self.app_env not in {"development", "test"}:
            raise ValueError("mock data is allowed only in development/test")
        if self.read_only and self.auth_provider != "local":
            raise ValueError("read-only experience requires real local authentication")
        if self.app_env in {"staging", "production"}:
            if self.auth_provider == "local" and not self.auth_cookie_secure:
                raise ValueError("local authentication requires secure cookies outside development/test")
            if self.app_debug:
                raise ValueError("debug mode is forbidden outside development/test")
            if not self.database_url:
                raise ValueError("database_url is required outside development/test")
            if not self.allowed_origins or "*" in self.allowed_origins:
                raise ValueError("an explicit non-wildcard origin allowlist is required")
            if not self.trusted_hosts:
                raise ValueError("an explicit trusted-host allowlist is required")
        return self

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        source = os.environ if environ is None else environ
        names = {
            "APP_ENV": "app_env",
            "APP_NAME": "app_name",
            "APP_HOST": "app_host",
            "APP_PORT": "app_port",
            "APP_DEBUG": "app_debug",
            "RELEASE_ID": "release_id",
            "LOG_LEVEL": "log_level",
            "API_BASE_PATH": "api_base_path",
            "ALLOWED_ORIGINS": "allowed_origins",
            "TRUSTED_HOSTS": "trusted_hosts",
            "AUTH_PROVIDER": "auth_provider",
            "AUTH_BOOTSTRAP_TOKEN": "auth_bootstrap_token",
            "AUTH_COOKIE_NAME": "auth_cookie_name",
            "AUTH_COOKIE_SECURE": "auth_cookie_secure",
            "AUTH_SESSION_SECONDS": "auth_session_seconds",
            "AUTH_IDLE_SECONDS": "auth_idle_seconds",
            "AUTH_RECENT_SECONDS": "auth_recent_seconds",
            "DAP_MOCK_DATA_ENABLED": "mock_data_enabled",
            "APP_READ_ONLY": "read_only",
            "DATABASE_URL": "database_url",
            "EXPECTED_DATABASE": "expected_database",
            "INSTANCE_ID": "instance_id",
            "DB_POOL_SIZE": "db_pool_size",
            "DB_MAX_OVERFLOW": "db_max_overflow",
            "DB_POOL_TIMEOUT_SECONDS": "db_pool_timeout_seconds",
            "CREDENTIAL_MASTER_KEY": "credential_master_key",
            "CREDENTIAL_KEY_VERSION": "credential_key_version",
            "CREDENTIAL_READ_KEYS": "credential_read_keys",
            "PRIVATE_FILE_ROOT": "private_file_root",
            "ATTACHMENT_SCAN_REQUIRED": "attachment_scan_required",
        }
        values = {field: source[key] for key, field in names.items() if key in source}
        try:
            return cls.model_validate(values)
        except ValidationError as exc:
            fields = sorted(
                {
                    ".".join(str(part) for part in issue["loc"]) or "configuration"
                    for issue in exc.errors(include_input=False)
                }
            )
            # Never include rejected values: DATABASE_URL may contain credentials.
            raise RuntimeError(f"Invalid Digital Asset Platform configuration fields: {', '.join(fields)}") from None


class MigrationSettings(BaseModel):
    """Credentials and target identity used only by the Alembic process."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    app_env: Literal["development", "test", "staging", "production"]
    migration_database_url: str = Field(min_length=1, repr=False)
    runtime_database_user: str = Field(min_length=1, max_length=128)
    expected_database: str = Field(min_length=1, max_length=63)
    instance_id: str = Field(min_length=1, max_length=128)

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "MigrationSettings":
        source = os.environ if environ is None else environ
        values = {
            "app_env": source.get("APP_ENV", "development"),
            "migration_database_url": source.get("MIGRATOR_DATABASE_URL", ""),
            "runtime_database_user": source.get("RUNTIME_DATABASE_USER", ""),
            "expected_database": source.get("EXPECTED_DATABASE", ""),
            "instance_id": source.get("INSTANCE_ID", ""),
        }
        try:
            return cls.model_validate(values)
        except ValidationError as exc:
            fields = sorted(
                {
                    ".".join(str(part) for part in issue["loc"]) or "configuration"
                    for issue in exc.errors(include_input=False)
                }
            )
            raise RuntimeError(f"Invalid Digital Asset Platform migration configuration fields: {', '.join(fields)}") from None
