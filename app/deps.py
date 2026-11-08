import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app import models
from app.auth import decode_access_token
from app.db import get_db

bearer = HTTPBearer()
def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> models.User:
   
    try:
        data = decode_access_token(creds.credentials)
    except jwt.InvalidTokenError:           
        raise _unauthorized()

    
    try:
        user_id = uuid.UUID(data["sub"])
    except (KeyError, ValueError):
        raise _unauthorized()

   
    user = db.get(models.User, user_id)
    if user is None or user.status != "active":
        raise _unauthorized()

    
    if data.get("tenant_id") != str(user.tenant_id):
        raise _unauthorized()

    return user


def require_role(*allowed: str):

    def checker(user: models.User = Depends(get_current_user)) -> models.User:
        if user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user

    return checker