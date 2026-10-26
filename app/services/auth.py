import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.models.database import AppSetting, SessionLocal, User, get_db

TOKEN_TTL = timedelta(days=7)
JWT_ALGORITHM = "HS256"
MAX_PASSWORD_BYTES = 72  # bcrypt's hard limit

_secret_cache: str | None = None


def _get_secret() -> str:
    """JWT_SECRET from the environment, or — when unset — a random 256-bit secret
    generated once and stored in the database, so a deployment works without a
    manually configured secret and tokens survive restarts."""
    global _secret_cache
    env = os.getenv("JWT_SECRET")
    if env:
        return env
    if _secret_cache:
        return _secret_cache
    db = SessionLocal()
    try:
        row = db.get(AppSetting, "jwt_secret")
        if row is None:
            db.add(AppSetting(key="jwt_secret", value=secrets.token_hex(32)))
            try:
                db.commit()
            except Exception:
                db.rollback()  # another instance created it first
            row = db.get(AppSetting, "jwt_secret")
        _secret_cache = row.value
        return _secret_cache
    finally:
        db.close()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    if len(password.encode()) > MAX_PASSWORD_BYTES:
        return False
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_access_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + TOKEN_TTL,
    }
    return jwt.encode(payload, _get_secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> str:
    """Returns the user id encoded in a valid token, raises ValueError otherwise."""
    try:
        payload = jwt.decode(
            token, _get_secret(), algorithms=[JWT_ALGORITHM], options={"require": ["exp", "sub"]}
        )
    except jwt.PyJWTError as e:
        raise ValueError(f"invalid token: {e}") from e
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise ValueError("invalid token: bad subject")
    return sub


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "missing or malformed Authorization header")

    token = auth_header.removeprefix("Bearer ").strip()
    try:
        user_id = decode_access_token(token)
    except ValueError as e:
        raise HTTPException(401, str(e))

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(401, "user no longer exists")
    return user
