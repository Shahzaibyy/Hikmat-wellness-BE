"""add bookings, availability, transactions, payouts

Revision ID: d4e5f6a7b8c9
Revises: b7e8f9a0c1d2
Create Date: 2026-08-03 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "b7e8f9a0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bookings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("hakeem_user_id", sa.UUID(), nullable=False),
        sa.Column("patient_user_id", sa.UUID(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "duration_minutes",
            sa.Integer(),
            server_default="30",
            nullable=False,
        ),
        sa.Column(
            "appointment_type",
            sa.String(length=80),
            server_default="Consultation",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="confirmed",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["hakeem_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["patient_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bookings_hakeem_user_id", "bookings", ["hakeem_user_id"])
    op.create_index("ix_bookings_patient_user_id", "bookings", ["patient_user_id"])
    op.create_index("ix_bookings_scheduled_at", "bookings", ["scheduled_at"])
    op.create_index("ix_bookings_status", "bookings", ["status"])

    op.create_table(
        "hakeem_weekly_availability",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("hakeem_user_id", sa.UUID(), nullable=False),
        sa.Column("day_of_week", sa.SmallInteger(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column(
            "is_available",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["hakeem_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "hakeem_user_id",
            "day_of_week",
            "start_time",
            "end_time",
            name="uq_hakeem_weekly_slot",
        ),
    )
    op.create_index(
        "ix_hakeem_weekly_availability_hakeem_user_id",
        "hakeem_weekly_availability",
        ["hakeem_user_id"],
    )

    op.create_table(
        "hakeem_date_availability",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("hakeem_user_id", sa.UUID(), nullable=False),
        sa.Column("specific_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column(
            "is_available",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["hakeem_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "hakeem_user_id",
            "specific_date",
            "start_time",
            "end_time",
            name="uq_hakeem_date_slot",
        ),
    )
    op.create_index(
        "ix_hakeem_date_availability_hakeem_user_id",
        "hakeem_date_availability",
        ["hakeem_user_id"],
    )
    op.create_index(
        "ix_hakeem_date_availability_specific_date",
        "hakeem_date_availability",
        ["specific_date"],
    )

    op.create_table(
        "transactions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("hakeem_user_id", sa.UUID(), nullable=False),
        sa.Column("patient_user_id", sa.UUID(), nullable=True),
        sa.Column("booking_id", sa.UUID(), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=3),
            server_default="PKR",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["hakeem_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["patient_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_transactions_hakeem_user_id", "transactions", ["hakeem_user_id"]
    )
    op.create_index("ix_transactions_status", "transactions", ["status"])
    op.create_index("ix_transactions_created_at", "transactions", ["created_at"])

    op.create_table(
        "payout_batches",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("hakeem_user_id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=3),
            server_default="PKR",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="pending_review",
            nullable=False,
        ),
        sa.Column("reference", sa.String(length=40), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["hakeem_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reference"),
    )
    op.create_index(
        "ix_payout_batches_hakeem_user_id", "payout_batches", ["hakeem_user_id"]
    )
    op.create_index("ix_payout_batches_status", "payout_batches", ["status"])
    op.create_index(
        "ix_payout_batches_requested_at", "payout_batches", ["requested_at"]
    )


def downgrade() -> None:
    op.drop_table("payout_batches")
    op.drop_table("transactions")
    op.drop_table("hakeem_date_availability")
    op.drop_table("hakeem_weekly_availability")
    op.drop_table("bookings")
