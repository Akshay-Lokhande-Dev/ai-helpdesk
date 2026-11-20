from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app import models
from app.queries import visible_tickets
from app.db import get_db
from app.deps import get_current_user
from app.schemas import TimelineEntry, ActorOut

router = APIRouter(tags=["timeline"])

@router.get("/tickets/{ticket_id}/timeline", response_model=list[TimelineEntry])
def get_timeline(
    ticket_id: UUID,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 1. visible wali list me se apna ticket nikal
    ticket = db.scalars(
        visible_tickets(current_user).where(models.Ticket.id == ticket_id)
    ).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="ticket not found")

    is_end_user = current_user.role == "end_user"
    timeline = []

    # 2. comments nikal
    comment_query = (
        select(models.TicketComment, models.User)
        .join(models.User, models.User.id == models.TicketComment.author_id)
        .where(
            models.TicketComment.ticket_id == ticket_id,
            models.TicketComment.tenant_id == current_user.tenant_id,
        )
    )
    if is_end_user:
        comment_query = comment_query.where(models.TicketComment.visibility == "public")

    for comment, user in db.execute(comment_query).all():
        timeline.append(TimelineEntry(
            kind="comment",
            at=comment.created_at,
            actor=ActorOut(id=user.id, name=user.name),
            body=comment.body,
            visibility=comment.visibility,
        ))

    # 3. events nikal
    event_query = (
        select(models.TicketEvent, models.User)
        .join(models.User, models.User.id == models.TicketEvent.actor_id)
        .where(
            models.TicketEvent.ticket_id == ticket_id,
            models.TicketEvent.tenant_id == current_user.tenant_id,
        )
    )
    if is_end_user:
        event_query = event_query.where(
            or_(
                models.TicketEvent.event_type == "created",
                models.TicketEvent.field.in_(["state", "resolution"])
            )
        )

    for event, user in db.execute(event_query).all():
        timeline.append(TimelineEntry(
            kind="event",
            at=event.created_at,
            actor=ActorOut(id=user.id, name=user.name),
            event_type=event.event_type,
            field=event.field,
            old_value=event.old_value,
            new_value=event.new_value,
        ))

    # 4. time se sort kar, same time pe kind se fix order
    timeline.sort(key=lambda x: (x.at, x.kind))
    return timeline