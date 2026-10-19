import uuid
from sqlalchemy import select
from app.db import Base,engine,session_local
from app import models

#Base.metadata.create_all(bind=engine)

with session_local() as s:
    tenant = models.Tenant(name="Acme Corp", slug="acme-" + uuid.uuid4().hex[:6])
    s.add(tenant)
    s.flush()                      # INSERT chala, ab tenant.id mil gaya
    print("flush ke baad tenant id:", tenant.id)

    user = models.User(name="Akshay", tenant_id=tenant.id, email="akshay@test.com")
    s.add(user)
    s.flush()                      # ab user.id mil gaya

    ticket = models.Ticket(
        tenant_id=tenant.id,
        ticket_number="T-001",
        title="Login not working",
        description="User cannot login with correct password",
        caller_id=user.id,
    )
    s.add(ticket)
    s.commit()                     # ek hi baar, sabse ant mein: teeno saath mein pakke

    row = s.scalars(select(models.Ticket)).first()
    print(row.id, row.ticket_number, row.state, row.priority, row.created_at)
