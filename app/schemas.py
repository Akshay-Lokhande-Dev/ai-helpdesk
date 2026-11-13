from pydantic import BaseModel,ConfigDict,Field
import uuid
from typing import Optional
from datetime import datetime
from typing import Literal
import uuid
from pydantic import BaseModel, ConfigDict,field_validator

class TicketOut(BaseModel):
    id: uuid.UUID
    ticket_number: str
    title: str
    description: Optional[str] = None
    state: str
    priority: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class TicketCreate(BaseModel):
        title: str
        description: str | None = None
        priority: str = "medium"
        model_config = ConfigDict(extra="forbid")

class UserOut(BaseModel):
      id:uuid.UUID
      email:str
      name:str
      role:str
      created_at:datetime
      model_config=ConfigDict(from_attributes=True)

class UserCreate(BaseModel):
    tenant_id: uuid.UUID
    email: str
    name: str
    role: Literal["end_user", "agent", "admin"] = "end_user"
    password: str = Field(min_length=8)

    @field_validator("role",mode="before")
    @classmethod
    def lower_role(cls,v):
         if isinstance(v,str):
              return v.lower()
         return v
    

class LoginRequest(BaseModel):
    tenant_slug: str
    email: str
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    model_config=ConfigDict(from_attributes=True)

class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    tenant_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True) 
             
            
      
          