import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func,Text,Index,UUID,Computed,Integer
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column,relationship
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector



from app.db import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    slug: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String,server_default="active", default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "email"),)   

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"))
    email: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(30),server_default="end_user", default="end_user")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active")
    password_hash: Mapped[str | None] = mapped_column(String(255))

class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (UniqueConstraint("tenant_id", "ticket_number"),Index("idx_tickets_caller_id", "caller_id"),
        Index("idx_tickets_assignee_id", "assignee_id"),UniqueConstraint("tenant_id", "source_system", "source_id", name="uq_tickets_source"))


    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"))
    ticket_number: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(20), default="new", server_default="new")
    priority: Mapped[str] = mapped_column(String(20), default="medium", server_default="medium")
    caller_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolution:Mapped[str|None] = mapped_column(Text,nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    source_system: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class TicketComment(Base):
    __tablename__ = "ticket_comments"
    __table_args__ = (Index("idx_ticket_comments_ticket_id", "ticket_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"))
    ticket_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tickets.id"))
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    visibility: Mapped[str] = mapped_column(String(20), default="internal", server_default="internal")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class TicketEvent(Base):
    __tablename__ = "ticket_events"
    __table_args__ = (Index("idx_ticket_events_ticket_id", "ticket_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"))
    ticket_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tickets.id"))
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))      

    event_type: Mapped[str] = mapped_column(String(30))                      
    field: Mapped[str | None] = mapped_column(String(50))
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KBArticle(Base):
    __tablename__ = "kb_articles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="draft", server_default="draft")

    source_ticket_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tickets.id"))
    source_system: Mapped[str | None] = mapped_column(String(50))
    source_id: Mapped[str | None] = mapped_column(String(255))

    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "source_system", "source_id", name="uq_kb_tenant_source"),
        Index("ix_kb_tenant_status", "tenant_id", "status"),
    )

class ContentChunk(Base):
    __tablename__ = "content_chunks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"))

    parent_type: Mapped[str] = mapped_column(String(20))
    parent_id: Mapped[uuid.UUID] = mapped_column()
    chunk_index: Mapped[int] = mapped_column(Integer)

    content_masked: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    visibility: Mapped[str] = mapped_column(String(20), default="public", server_default="public")

    tsv: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', content_masked)", persisted=True),
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384))
    embedding_model: Mapped[str | None] = mapped_column(String(100))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "parent_type", "parent_id", "chunk_index", name="uq_chunk_position"),
        Index("ix_chunks_tenant_parent", "tenant_id", "parent_type", "parent_id"),
        Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),
    )    
