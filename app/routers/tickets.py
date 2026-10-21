from fastapi import APIRouter,Depends,HTTPException
from app import models
from app.schemas import TicketOut
from sqlalchemy.orm import Session
from app.db import get_db
from sqlalchemy import select
import uuid


router = APIRouter(prefix="/tickets", tags=["tickets"])

@router.get("",response_model=list[TicketOut])
def get_tickets(db:Session=Depends(get_db)):
    
    tickets = db.scalars(select(models.Ticket).limit(50)).all()

    return tickets

@router.get("/{ticket_id}",response_model=list[TicketOut])
def get_tickets(ticket_id:uuid.UUID, db:Session=Depends(get_db)):

    ticket = db.get(models.Ticket, ticket_id)

    if ticket is None:
        raise HTTPException(status_code=404,detail= "ticket not found in database")
    return [ticket]
    
