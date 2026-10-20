import uuid
from sqlalchemy import select
from app.db import session_local
from app import models

with session_local() as s:
    tenant = models.Tenant(name="Acme Corp", slug="acme-" + uuid.uuid4().hex[:6])
    s.add(tenant)
    s.flush()

    user = models.User(name="Akshay", tenant_id=tenant.id, email="akshay@test.com")
    s.add(user)
    s.flush()

    ticket = models.Ticket(
        tenant_id=tenant.id,
        ticket_number="T-001",
        title="Login not working",
        description="User cannot login with correct password",
        caller_id=user.id,
    )
    s.add(ticket)
    s.flush()                          # NAYA: comments ko ticket.id chahiye

    # NAYA: do comments, ek public, ek internal
    c1 = models.TicketComment(
        tenant_id=tenant.id, ticket_id=ticket.id, author_id=user.id,
        body="Mera login nahi chal raha, please dekhiye", visibility="public",
    )
    c2 = models.TicketComment(
        tenant_id=tenant.id, ticket_id=ticket.id, author_id=user.id,
        body="Account lock lag raha hai, DBA se check karo", visibility="internal",
    )
    s.add_all([c1, c2])                # dono ek saath add
    s.commit()                         # ek hi baar, sabse ant mein

    # NAYA: agent ko sab comments dikhte hain
    all_comments = s.scalars(
        select(models.TicketComment).where(models.TicketComment.ticket_id == ticket.id)
    ).all()

    # NAYA: end user ko sirf public wale
    public_comments = s.scalars(
        select(models.TicketComment).where(
            models.TicketComment.ticket_id == ticket.id,
            models.TicketComment.visibility == "public",
        )
    ).all()

    print("agent ko dikhega:", len(all_comments))
    print("end user ko dikhega:", len(public_comments))