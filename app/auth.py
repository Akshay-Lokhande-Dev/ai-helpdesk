from passlib.context import CryptContext
import jwt
from datetime import datetime, timedelta, timezone
from app.db import require_env


pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def hash_password(password: str) -> str | None:
    if not password:
        return None
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    return pwd_context.verify(plain_password, hashed_password)




SECRET_KEY = require_env("SECRET_KEY")      
ALGORITHM = "HS256"

def create_access_token(user) -> str:
    payload = {
        "sub": str(user.id),                 
        "tenant_id": str(user.tenant_id),
        "role": user.role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])