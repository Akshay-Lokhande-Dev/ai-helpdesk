import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.queries import visible_tickets
from app.db import get_db
from app.deps import get_current_user,require_role
from app.schemas import TicketCreate, TicketOut,TicketUpdate
from datetime import datetime,timezone
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
    db.flush()                                       
    db.add(models.TicketEvent(
    tenant_id=current_user.tenant_id,
    ticket_id=ticket.id,
    actor_id=current_user.id,
    event_type="created",))
    
    db.commit()
    db.refresh(ticket)
    return ticket



@router.patch("/{ticket_id}", response_model=TicketOut)
def update_ticket(
    ticket_id: uuid.UUID,
    payload: TicketUpdate,
    current_user: models.User = Depends(require_role("agent", "admin")),
    db: Session = Depends(get_db),
):
    ticket = db.scalars(visible_tickets(current_user).where(models.Ticket.id == ticket_id)).first()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    changes = payload.model_dump(exclude_unset=True)       # sirf wahi jo client ne sach mein bheja

    # --- sab jaanch, kuch badalne se PEHLE ---
    new_assignee = changes.get("assignee_id")
    if new_assignee is not None:
        assignee = db.get(models.User, new_assignee)
        if (assignee is None or assignee.tenant_id != current_user.tenant_id
                or assignee.role not in ("agent", "admin") or assignee.status != "active"):
            raise HTTPException(status_code=422, detail="Invalid assignee")

    if changes.get("state") == "resolved":
        if not changes.get("resolution", ticket.resolution):
            raise HTTPException(status_code=422, detail="Resolution is required to resolve a ticket")

    # --- badlav aur events, ek hi transaction mein ---
    for field, new in changes.items():
        old = getattr(ticket, field)
        if new == old:
            continue
        db.add(models.TicketEvent(
            tenant_id=ticket.tenant_id,
            ticket_id=ticket.id,
            actor_id=current_user.id,
            event_type="updated",
            field=field,
            old_value=None if old is None else str(old),
            new_value=None if new is None else str(new),
        ))
        setattr(ticket, field, new)

    if "state" in changes:
        if ticket.state == "resolved" and ticket.resolved_at is None:
            ticket.resolved_at = datetime.now(timezone.utc)
        elif ticket.state in ("new", "in_progress", "on_hold"):
            ticket.resolved_at = None                       # reopen

    db.commit()
    db.refresh(ticket)
    return ticket