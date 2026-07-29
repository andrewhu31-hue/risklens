from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.services.auth import (
    JWT_ALGORITHM,
    _get_secret,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_password_round_trips():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed)


def test_hash_password_rejects_wrong_password():
    hashed = hash_password("correct horse battery staple")
    assert not verify_password("wrong password", hashed)


def test_hash_password_produces_different_hashes_for_same_input():
    # bcrypt salts each hash, so hashing the same password twice should
    # never produce identical output.
    a = hash_password("same password")
    b = hash_password("same password")
    assert a != b


def test_access_token_round_trips():
    token = create_access_token("user-123")
    assert decode_access_token(token) == "user-123"


def test_decode_rejects_tampered_token():
    token = create_access_token("user-123")
    tampered = token[:-4] + "abcd"
    with pytest.raises(ValueError):
        decode_access_token(tampered)


def test_decode_rejects_expired_token():
    expired_payload = {
        "sub": "user-123",
        "exp": datetime.now(timezone.utc) - timedelta(days=1),
    }
    expired_token = jwt.encode(expired_payload, _get_secret(), algorithm=JWT_ALGORITHM)
    with pytest.raises(ValueError):
        decode_access_token(expired_token)


def test_decode_rejects_wrong_secret():
    forged = jwt.encode({"sub": "user-123", "exp": datetime.now(timezone.utc) + timedelta(days=1)}, "wrong-secret", algorithm=JWT_ALGORITHM)
    with pytest.raises(ValueError):
        decode_access_token(forged)
