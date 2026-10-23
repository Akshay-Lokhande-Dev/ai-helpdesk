import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.schemas import TicketCreate, TicketOut

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("", response_model=list[TicketOut])
def get_tickets(db: Session = Depends(get_db)):
    return db.scalars(
        select(models.Ticket).order_by(models.Ticket.created_at.desc()).limit(50)
    ).all()


@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: uuid.UUID, db: Session = Depends(get_db)):
    ticket = db.get(models.Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.post("", response_model=TicketOut, status_code=201)
def create_ticket(payload: TicketCreate, db: Session = Depends(get_db)):
    tenant = db.get(models.Tenant,payload.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404,detail="tenant or user not found")
    caller = db.get(models.User,payload.caller_id)
    if caller is None:
        raise HTTPException(status_code=404,detail="tenant or user not found")

    ticket = models.Ticket(
        tenant_id=payload.tenant_id,
        caller_id=payload.caller_id,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        ticket_number="T-" + uuid.uuid4().hex[:8].upper(),
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket