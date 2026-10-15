import uuid
from sqlalchemy import select
from app.db import Base,engine,session_local
from app import models

#Base.metadata.create_all(bind=engine)

with session_local() as s:
    tenant = models.Tenant(name="Acme Corp", slug="acme-" + uuid.uuid4().hex[:6])
    print("commit se pehle id:", tenant.id)
    s.add(tenant)
    s.commit()

    print("commit ke baad:",tenant.id)
    rows = s.scalars(select(models.Tenant)).all()
    for t in rows:
        print(t.id, t.name, t.slug, t.status, t.created_at)
