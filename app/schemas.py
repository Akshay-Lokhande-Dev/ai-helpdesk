from pydantic import BaseModel,ConfigDict,Field
import uuid
from typing import Optional
from datetime import datetime
from typing import Literal


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
        tenant_id: uuid.UUID
        caller_id: uuid.UUID

class UserOut(BaseModel):
      id:uuid.UUID
      email:str
      name:str
      role:str
      created_at:datetime

class UserCreate(BaseModel):
    tenant_id: uuid.UUID
    email: str
    name: str
    role: Literal["end_user", "agent", "admin"] = "end_user"
    password: str = Field(min_length=8)

      
            
      
          