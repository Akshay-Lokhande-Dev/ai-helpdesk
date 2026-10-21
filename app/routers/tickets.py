from fastapi import APIRouter,Depends
from app import models
from app.schemas import TicketOut
from sqlalchemy.orm import Session
from app.db import get_db
from sqlalchemy import select


router = APIRouter(prefix="/tickets", tags=["tickets"])

@router.get("",response_model=list[TicketOut])
def get_tickets(db:Session=Depends(get_db)):
    
    tickets = db.scalars(select(models.Ticket).limit(50)).all()

    return tickets