"""documents attached to chat messages (encrypted) and their check results

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("chat_messages") as b:
        b.add_column(sa.Column("attachment_enc", sa.Text(), nullable=True))
        b.add_column(sa.Column("findings_enc", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("chat_messages") as b:
        b.drop_column("findings_enc")
        b.drop_column("attachment_enc")
