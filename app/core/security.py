import hashlib
import hmac
import secrets

KEY_PREFIX_TEXT = "sk-local-"


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def api_key_prefix(api_key: str) -> str:
    return api_key[:18]


def verify_api_key(api_key: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_api_key(api_key), expected_hash)


def generate_api_key() -> str:
    return f"{KEY_PREFIX_TEXT}{secrets.token_urlsafe(32)}"
