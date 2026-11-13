from fastapi import APIRouter,Depends,HTTPException
from app.schemas import UserOut,UserCreate
from app.db import get_db
from sqlalchemy.orm import Session
from app import models
from app.auth import hash_password as hash_func
from sqlalchemy.exc import IntegrityError
import uuid
from app.deps import require_role



router = APIRouter(prefix="/users",tags=["users"])

@router.post("", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate,
                admin: models.User = Depends(require_role("admin")),
                db: Session = Depends(get_db)):
    password_hash = hash_func(payload.password) if payload.password else None

    user = models.User(
        tenant_id=admin.tenant_id,            # admin ke token wale tenant se, body se nahi
        email=payload.email.strip().lower(),
        name=payload.name,
        role=payload.role,
        password_hash=password_hash,
    )
    try:
        db.add(user)
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if "users_tenant_id_email_key" in str(e.orig):
            raise HTTPException(status_code=409, detail="email already exists for this tenant")
        raise
    db.refresh(user)
    return user


@router.get("/test/{user_id}", response_model=UserOut)
def test_user(user_id: uuid.UUID, db: Session = Depends(get_db)):
    user = db.get(models.User, user_id)
    return user

        

  

        









