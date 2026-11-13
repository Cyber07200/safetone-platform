"""encrypted chat history; row level security on PostgreSQL (Supabase)

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

TABLES = ("banks", "bank_settings", "products", "documents", "chunks", "processing_runs",
          "chat_conversations", "chat_messages", "alembic_version")


def upgrade() -> None:
    op.create_table(
        "chat_conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("bank_id", sa.String(36), sa.ForeignKey("banks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_hash", sa.String(64), nullable=False),
        sa.Column("title_enc", sa.Text(), nullable=False),
        sa.Column("summary_enc", sa.Text(), nullable=True),
        sa.Column("summarized_upto", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_chat_conv_owner", "chat_conversations", ["bank_id", "owner_hash", "updated_at"])
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(36), sa.ForeignKey("chat_conversations.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content_enc", sa.Text(), nullable=False),
        sa.Column("sources_enc", sa.Text(), nullable=True),
        sa.Column("mode", sa.String(8), nullable=True),
        sa.Column("model", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("conversation_id", "seq"),
    )
    if op.get_bind().dialect.name == "postgresql":
        # Supabase publishes the `public` schema through its REST API to the
        # anon/authenticated roles. SafeTone talks to the database only from
        # the backend (table owner), so: RLS on, no policies, no grants —
        # nothing is reachable with the public API keys.
        for t in TABLES:
            op.execute(f'ALTER TABLE public."{t}" ENABLE ROW LEVEL SECURITY')
        op.execute("""
            DO $$ BEGIN
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                EXECUTE 'REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated';
              END IF;
            END $$;""")


def downgrade() -> None:
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_conv_owner", table_name="chat_conversations")
    op.drop_table("chat_conversations")
