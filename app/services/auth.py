import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.models.database import User, get_db

TOKEN_TTL = timedelta(days=7)
JWT_ALGORITHM = "HS256"


def _get_secret() -> str:
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET is not set")
    return secret


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
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
        payload = jwt.decode(token, _get_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as e:
        raise ValueError(f"invalid token: {e}") from e
    return payload["sub"]


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
