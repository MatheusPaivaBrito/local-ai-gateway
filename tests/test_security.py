from app.core.security import generate_api_key, hash_api_key, verify_api_key


def test_api_key_hashing_and_validation() -> None:
    key = generate_api_key()
    hashed = hash_api_key(key)
    assert key.startswith("sk-local-")
    assert key not in hashed
    assert verify_api_key(key, hashed)
    assert not verify_api_key(f"{key}x", hashed)
