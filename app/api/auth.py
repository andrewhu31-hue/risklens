from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.limiter import limiter
from app.models.database import User, get_db
from app.services.auth import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/register", response_model=TokenResponse)
@limiter.limit("10/minute")
def register(request: Request, body: AuthBody, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.query(User).filter(User.email == email).first() is not None:
        raise HTTPException(409, "an account with this email already exists")

    user = User(email=email, hashed_password=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(request: Request, body: AuthBody, db: Session = Depends(get_db)):
    email = body.email.lower()
    user = db.query(User).filter(User.email == email).first()
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(401, "invalid email or password")
    return TokenResponse(access_token=create_access_token(user.id))
