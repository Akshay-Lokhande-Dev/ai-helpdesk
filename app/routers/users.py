from fastapi import APIRouter,Depends,HTTPException
from app.schemas import UserOut,UserCreate
from app.db import get_db
from sqlalchemy.orm import Session
from app import models
from app.auth import hash_password as hash_func
from sqlalchemy.exc import IntegrityError



router = APIRouter(prefix="/users",tags=["users"])

@router.post("",response_model=UserOut,status_code=201)
def UserCreate(Payload:UserCreate,db:Session=Depends(get_db)):
    tenant = db.get(models.Tenant,Payload.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404,detail="tenant not found")
    
    password_hash = hash_func(Payload.password) if Payload.password else None
    email = Payload.email.strip().lower()

    user = models.User(
    tenant_id = Payload.tenant_id,
    email = email,
    name = Payload.name,
    role = Payload.role,
    password_hash = password_hash)
    try:
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError as e:
        db.rollback()
        if "users_tenant_id_email_key" in str(e.orig):
            raise HTTPException(status_code=409, detail="email already exists for this tenant")
        raise

    
        

  

        









