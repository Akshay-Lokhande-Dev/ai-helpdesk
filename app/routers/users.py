import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.auth import hash_password as hash_func
from app.db import get_db
from app.deps import require_role
from app.schemas import UserCreate, UserOut


router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate,
    admin: models.User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    user = models.User(
        tenant_id=admin.tenant_id,
        email=payload.email.strip().lower(),
        name=payload.name,
        role=payload.role,
        password_hash=hash_func(payload.password),
    )
    try:
        db.add(user)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if "users_tenant_id_email_key" in str(exc.orig):
            raise HTTPException(
                status_code=409,
                detail="email already exists for this tenant",
            ) from exc
        raise

    db.refresh(user)
    return user


@router.get("/test/{user_id}", response_model=UserOut)
def test_user(
    user_id: uuid.UUID,
    admin: models.User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    # Restrict this diagnostic lookup to the authenticated admin's tenant.
    user = (
        db.query(models.User)
        .filter(
            models.User.id == user_id,
            models.User.tenant_id == admin.tenant_id,
        )
        .first()
    )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user
