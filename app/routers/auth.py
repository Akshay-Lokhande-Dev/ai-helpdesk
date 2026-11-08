from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app import models
from app.db import get_db  
from app.schemas import LoginRequest, TokenOut, MeOut
from app.auth import create_access_token, verify_password, hash_password  
from app import deps

router = APIRouter(prefix="/auth", tags=["auth"])

DUMMY_HASH = hash_password("dummy_for_timing_attack_123") 

def invalid_credentials():
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

@router.post("/login", response_model=TokenOut)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    tenant = db.scalars(select(models.Tenant).where(models.Tenant.slug == payload.tenant_slug.strip().lower())).first()
    if not tenant:
        verify_password(payload.password, DUMMY_HASH)
        raise invalid_credentials()

    user = db.scalars(select(models.User).where(models.User.tenant_id == tenant.id, models.User.email == payload.email.strip().lower())).first()
    if not user:
        verify_password(payload.password, DUMMY_HASH)
        raise invalid_credentials()

    if not user.password_hash:
        verify_password(payload.password, DUMMY_HASH)
        raise invalid_credentials()

    if user.status != "active":
        verify_password(payload.password, user.password_hash)
        raise invalid_credentials()

    if not verify_password(payload.password, user.password_hash):
        raise invalid_credentials()

    return TokenOut(access_token=create_access_token(user), token_type="bearer")

@router.get("/me", response_model=MeOut)
def get_me(current_user: models.User = Depends(deps.get_current_user)):
    return current_user