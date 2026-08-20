"""Auth endpoints: register, login (JWT), and current user."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import create_token, get_current_user, hash_password, verify_password
from ..database import get_db
from ..models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Credentials(BaseModel):
    email: str
    password: str


class AuthOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str
    role: str


class UserOut(BaseModel):
    id: int
    email: str
    role: str

    model_config = {"from_attributes": True}


@router.post("/register", response_model=AuthOut)
def register(body: Credentials, db: Session = Depends(get_db)) -> AuthOut:
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(400, "An account with that email already exists")
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    user = User(email=body.email, hashed_password=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return AuthOut(access_token=create_token(user.id), email=user.email, role=user.role)


@router.post("/login", response_model=AuthOut)
def login(body: Credentials, db: Session = Depends(get_db)) -> AuthOut:
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(401, "Incorrect email or password")
    return AuthOut(access_token=create_token(user.id), email=user.email, role=user.role)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
