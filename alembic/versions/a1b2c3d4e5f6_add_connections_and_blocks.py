"""add connections and blocks

Revision ID: a1b2c3d4e5f6
Revises: 9dc1fd3c2ca2
Create Date: 2026-08-01 16:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "9dc1fd3c2ca2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "connections",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("requester_id", sa.UUID(), nullable=False),
        sa.Column("recipient_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requester_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "requester_id", "recipient_id", name="uq_connections_requester_recipient"
        ),
    )
    op.create_index(op.f("ix_connections_recipient_id"), "connections", ["recipient_id"])
    op.create_index(op.f("ix_connections_requester_id"), "connections", ["requester_id"])
    op.create_index(op.f("ix_connections_status"), "connections", ["status"])

    op.create_table(
        "blocks",
        sa.Column("blocker_id", sa.UUID(), nullable=False),
        sa.Column("blocked_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["blocked_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["blocker_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("blocker_id", "blocked_id"),
        sa.UniqueConstraint(
            "blocker_id", "blocked_id", name="uq_blocks_blocker_blocked"
        ),
    )


def downgrade() -> None:
    op.drop_table("blocks")
    op.drop_index(op.f("ix_connections_status"), table_name="connections")
    op.drop_index(op.f("ix_connections_requester_id"), table_name="connections")
    op.drop_index(op.f("ix_connections_recipient_id"), table_name="connections")
    op.drop_table("connections")
