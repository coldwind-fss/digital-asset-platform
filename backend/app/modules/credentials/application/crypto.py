from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import Settings
from app.platform.http.errors import ApiException


@dataclass(frozen=True)
class EncryptedSecret:
    ciphertext: bytes
    nonce: bytes
    key_version: str


def _key(settings: Settings, version: str | None=None) -> bytes:
    material = settings.credential_master_key if version in {None,settings.credential_key_version} else settings.credential_read_keys.get(version)
    if not material:
        raise ApiException(
            503,
            "DEPENDENCY_UNAVAILABLE",
            "凭据主密钥尚未配置",
            retryable=True,
        )
    try:
        key = base64.urlsafe_b64decode(material.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        raise ApiException(503, "DEPENDENCY_UNAVAILABLE", "凭据加密配置不可用", retryable=True) from None
    if len(key) != 32:
        raise ApiException(503, "DEPENDENCY_UNAVAILABLE", "凭据加密配置不可用", retryable=True)
    return key


def encrypt_secret(settings: Settings, value: str, *, associated_data: bytes) -> EncryptedSecret:
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(_key(settings)).encrypt(nonce, value.encode("utf-8"), associated_data)
    return EncryptedSecret(ciphertext=ciphertext, nonce=nonce, key_version=settings.credential_key_version)


def decrypt_secret(
    settings: Settings,
    *,
    ciphertext: bytes,
    nonce: bytes,
    key_version: str,
    associated_data: bytes,
) -> str:
    try:
        plaintext = AESGCM(_key(settings,key_version)).decrypt(nonce, ciphertext, associated_data)
    except (InvalidTag, ValueError):
        raise ApiException(503, "DEPENDENCY_UNAVAILABLE", "凭据解密失败", retryable=True) from None
    return plaintext.decode("utf-8")


def new_stage_token() -> str:
    return secrets.token_urlsafe(32)


def hash_stage_token(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()
