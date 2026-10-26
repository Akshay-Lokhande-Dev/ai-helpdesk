# ERRORS.md: bugs I hit and how I fixed them

## 1. OperationalError (connection refused)
When: Postgres was stopped (or laptop restarted) and an endpoint used the database.
Why: engine and session are lazy; the connection is only made at the first query.
How I found it: read the traceback from the last line upward.
Fix: start Docker and the container, check `docker compose ps`.

## 2. ModuleNotFoundError: No module named 'app'
When: I ran models.py with the editor's play button.
Why: running a file directly puts its own folder on the import path, not the project root.
Fix: do not run models.py; run `python -m scripts.smoke_test` or use uvicorn/Alembic from the root.

## 3. Alembic autogenerate made an empty migration (only `pass`)
Why: compare_server_default=True was missing in alembic/env.py.
Fix: add it in run_migrations_online(), then generate a new migration.
Lesson: read a migration before `upgrade head`; never delete one that is already applied.

## 4. Route became /tickets/tickets
Why: the router had prefix="/tickets" and the decorator also said "/tickets".
Fix: use @router.get("") inside the router.

## 5. ResponseValidationError: Input should be a valid list
Why: response_model was list[TicketOut] but the endpoint returned one ticket.
Fix: response_model=TicketOut for the single-ticket endpoint.

## 6. IntegrityError (ForeignKeyViolation) -> 500 on POST /tickets
When: I sent a tenant_id that does not exist in the tenants table.
Why: tickets.tenant_id has a foreign key to tenants.id. Postgres rejected the INSERT, SQLAlchemy raised IntegrityError, and FastAPI turned the unhandled exception into a 500.
How I found it: last line of the traceback named ForeignKeyViolation.
Lesson: a 500 means "server bug", but this was a client mistake, so the API should return a 4xx. Also, a foreign key only checks that the id exists, not that the user belongs to that tenant.
Fix: checked tenant and caller before insert; return 404 for missing or mismatched references.

## 7. TypeError: 'rol' is an invalid keyword argument for User
When: `user = models.User(rol="admin", ...)` - typo in column name.
Why: `models.User` is a SQLAlchemy class. Its `__init__` only accepts columns defined in models.py. This fails at APP level, DB is never hit.
How I found it: Python traceback directly said invalid keyword argument.
Lesson: Wrong column name = App level TypeError. Wrong column value = DB level error. `user` is an object of `User` class.
Fix: use correct field names `role`, `email` etc. as defined in `models.py`.

## 8. IntegrityError (UniqueViolation) -> 500 on POST /users
When: I sent same email twice for same tenant_id.
Why: constraint `users_tenant_id_email_key` on (tenant_id, email). Postgres rejected INSERT, SQLAlchemy raised `IntegrityError`, unhandled -> 500.
Fix: catch it and return 409:
```python
except IntegrityError as e:
    db.rollback()
    if "users_tenant_id_email_key" in str(e.orig):
        raise HTTPException(409, "Email already exists in this tenant")
