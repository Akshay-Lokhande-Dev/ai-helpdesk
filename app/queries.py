from sqlalchemy import select

from app import models


def visible_tickets(current_user):
    
    query = select(models.Ticket).where(models.Ticket.tenant_id == current_user.tenant_id)
    if current_user.role == "end_user":
        query = query.where(models.Ticket.caller_id == current_user.id)
    return query