import hashlib
import hmac
import secrets


def fixed_digest(value: str) -> bytes:
    return hashlib.sha256(value.encode("utf-8")).digest()


def constant_time_token_matches(candidate: str, expected: str) -> bool:
    return secrets.compare_digest(fixed_digest(candidate), fixed_digest(expected))


def keyed_digest(value: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def auth_epoch(admin_token: str) -> str:
    return hashlib.sha256(admin_token.encode("utf-8")).hexdigest()


def random_opaque_token() -> str:
    return secrets.token_urlsafe(32)
