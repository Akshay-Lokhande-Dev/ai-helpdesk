from pydantic import BaseModel,ConfigDict,Field
import uuid
from typing import Optional
from datetime import datetime
from typing import Literal
import uuid
from uuid import UUID
from pydantic import BaseModel, ConfigDict,field_validator

class TicketOut(BaseModel):
    id: uuid.UUID
    ticket_number: str
    title: str
    description: Optional[str] = None
    state: str
    priority: str
    created_at: datetime
    resolution: str | None = None
    resolved_at: datetime | None = None
    updated_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)

class TicketCreate(BaseModel):
        title: str
        description: str | None = None
        priority: str = "medium"
        model_config = ConfigDict(extra="forbid")

class TicketUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    state: Literal["new", "in_progress", "on_hold", "resolved", "closed", "cancelled"] | None = None
    priority: Literal["low", "medium", "high", "critical"] | None = None
    assignee_id: uuid.UUID | None = None            # explicit null bhejne par unassign
    resolution: str | None = Field(default=None, min_length=1, max_length=5000)       

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

class CommentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)      
    body: str = Field(min_length=1, max_length=5000)
    visibility: Literal["public", "internal"] = "internal"     


class CommentOut(BaseModel):
    id: uuid.UUID
    author_id: uuid.UUID
    body: str
    visibility: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ActorOut(BaseModel):
    id: uuid.UUID
    name: str
    model_config = ConfigDict(from_attributes=True)

class TimelineEntry(BaseModel):
    kind: Literal["comment", "event"]
    at: datetime
    actor: ActorOut
    # comment fields
    body: str | None = None
    visibility: str | None = None
    # event fields
    event_type: str | None = None
    field: str | None = None
    old_value: str | None = None
    new_value: str | None = None

class AiAskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)

    @field_validator("question", mode="before")
    @classmethod
    def strip_question(cls, value):
        return value.strip() if isinstance(value, str) else value

class AiCitation(BaseModel):
    parent_type: str
    parent_id: str
    title: str | None = None
    chunk_index: int

class AiAskResponse(BaseModel):
    answer: str
    citations: list[AiCitation]
    similarity: float | None
    degraded: bool  