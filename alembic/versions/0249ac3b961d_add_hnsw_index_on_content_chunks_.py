"""add hnsw index on content_chunks embedding

Revision ID: 0249ac3b961d
Revises: 3b0d47f96330
Create Date: 2026-11-25 08:25:53.466825

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0249ac3b961d'
down_revision: Union[str, Sequence[str], None] = '3b0d47f96330'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_content_chunks_embedding_hnsw
        ON content_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_content_chunks_embedding_hnsw;")