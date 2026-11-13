import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.deps import get_current_user
from app.schemas import TicketCreate, TicketOut

router = APIRouter(prefix="/tickets", tags=["tickets"])

def _visible_tickets(current_user: models.User):
    query = select(models.Ticket).where(models.Ticket.tenant_id == current_user.tenant_id)
    if current_user.role == "end_user":
        query = query.where(models.Ticket.caller_id == current_user.id)
    return query

@router.get("", response_model=list[TicketOut])
def get_tickets(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = _visible_tickets(current_user).order_by(models.Ticket.created_at.desc()).limit(50)
    return db.scalars(query).all()

@router.get("/{ticket_number}", response_model=TicketOut)
def get_ticket_by_number(ticket_number: str, current_user: models.User = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    query = _visible_tickets(current_user).where(models.Ticket.ticket_number == ticket_number.strip().upper())
    ticket = db.scalars(query).first()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket

@router.post("", response_model=TicketOut, status_code=201)
def create_ticket(payload: TicketCreate, current_user: models.User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    ticket = models.Ticket(
        tenant_id=current_user.tenant_id,
        caller_id=current_user.id,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        ticket_number="T-" + uuid.uuid4().hex[:8].upper(),
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket