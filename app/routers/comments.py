import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.deps import get_current_user
from app.queries import visible_tickets
from app.schemas import CommentCreate, CommentOut

router = APIRouter(prefix="/tickets/{ticket_id}/comments", tags=["comments"])


def _get_visible_ticket(db: Session, current_user: models.User, ticket_id: uuid.UUID) -> models.Ticket:
    ticket = db.scalars(visible_tickets(current_user).where(models.Ticket.id == ticket_id)).first()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.post("", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
def add_comment(
    ticket_id: uuid.UUID,
    payload: CommentCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_visible_ticket(db, current_user, ticket_id)

    visibility = "public" if current_user.role == "end_user" else payload.visibility

    comment = models.TicketComment(
        tenant_id=current_user.tenant_id,     
        ticket_id=ticket_id,
        author_id=current_user.id,
        body=payload.body,
        visibility=visibility,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@router.get("", response_model=list[CommentOut])
def list_comments(
    ticket_id: uuid.UUID,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_visible_ticket(db, current_user, ticket_id)

    query = select(models.TicketComment).where(
        models.TicketComment.ticket_id == ticket_id,
        models.TicketComment.tenant_id == current_user.tenant_id,
    )
    if current_user.role == "end_user":
        query = query.where(models.TicketComment.visibility == "public")

    return db.scalars(query.order_by(models.TicketComment.created_at.asc())).all()