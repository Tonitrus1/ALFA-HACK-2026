"""Initial persistent knowledge and candidate schema."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("created_at", sa.String, nullable=False),
    )
    op.create_table(
        "knowledge_versions",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column(
            "document_id", sa.String, sa.ForeignKey("knowledge_documents.id"), nullable=False
        ),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("state", sa.String, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("sha256", sa.String, nullable=False, index=True),
        sa.Column("original_path", sa.String, nullable=False),
        sa.Column("attributes", sa.JSON, nullable=False),
        sa.Column("created_at", sa.String, nullable=False),
        sa.Column("published_at", sa.String, nullable=True),
        sa.Column("error_code", sa.String, nullable=True),
        sa.UniqueConstraint("document_id", "version"),
    )
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column(
            "version_id",
            sa.String,
            sa.ForeignKey("knowledge_versions.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("page", sa.Integer, nullable=True),
        sa.Column("section", sa.String, nullable=True),
        sa.Column("ordinal", sa.Integer, nullable=False),
    )
    op.create_table(
        "web_candidates",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("session_id", sa.String, nullable=False, index=True),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("url", sa.String, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("sha256", sa.String, nullable=False),
        sa.Column("retrieved_at", sa.String, nullable=False),
        sa.Column("state", sa.String, nullable=False),
        sa.Column("knowledge_ref", sa.JSON, nullable=True),
    )


def downgrade():
    for name in ("web_candidates", "knowledge_chunks", "knowledge_versions", "knowledge_documents"):
        op.drop_table(name)
