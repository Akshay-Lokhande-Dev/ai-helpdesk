from pydantic import BaseModel,ConfigDict
import uuid
from typing import Optional
from datetime import datetime


class TicketOut(BaseModel):
    id: uuid.UUID
    ticket_number: str
    title: str
    description: Optional[str] = None
    state: str
    priority: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
    