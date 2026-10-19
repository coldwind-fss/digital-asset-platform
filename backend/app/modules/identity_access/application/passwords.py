"""Password verification and opaque one-time tokens using the standard library."""
import base64
import hashlib
import hmac
import secrets

N, R, P = 32768, 8, 3


def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=N, r=R, p=P, maxmem=64 * 1024 * 1024, dklen=32)
    return "scrypt$32768$8$3$" + base64.urlsafe_b64encode(salt).decode() + "$" + base64.urlsafe_b64encode(digest).decode()


def password_matches(password: str, encoded: str | None) -> bool:
    try:
        algorithm, n, r, p, salt, expected = (encoded or "").split("$")
        if (algorithm, n, r, p) != ("scrypt", "32768", "8", "3"):
            return False
        actual = hashlib.scrypt(password.encode("utf-8"), salt=base64.urlsafe_b64decode(salt), n=N, r=R, p=P, maxmem=64 * 1024 * 1024, dklen=32)
        return hmac.compare_digest(actual, base64.urlsafe_b64decode(expected))
    except (ValueError, TypeError):
        return False


def opaque_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


def csrf_token(session_token: str) -> str:
    return hmac.new(session_token.encode("utf-8"), b"dap-csrf-v1", hashlib.sha256).hexdigest()
