"""add hakeem profiles, roles, and verification workflow

Revision ID: b7e8f9a0c1d2
Revises: a1b2c3d4e5f6
Create Date: 2026-08-03 15:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b7e8f9a0c1d2"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing rows safely default to patient.
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.String(length=20),
            server_default="patient",
            nullable=False,
        ),
    )

    op.create_table(
        "hakeem_profiles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("specializations", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("years_of_experience", sa.Integer(), nullable=True),
        sa.Column("languages_spoken", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("consultation_fee", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("rating_avg", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column(
            "rating_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("national_id_number", sa.String(length=64), nullable=False),
        sa.Column("national_id_document_url", sa.String(length=500), nullable=False),
        sa.Column("license_number", sa.String(length=100), nullable=True),
        sa.Column("license_document_url", sa.String(length=500), nullable=False),
        sa.Column("training_institute", sa.String(length=200), nullable=True),
        sa.Column("previous_practice_location", sa.String(length=200), nullable=True),
        sa.Column("reason_for_joining", sa.Text(), nullable=True),
        sa.Column("reference_contact", sa.String(length=120), nullable=True),
        sa.Column(
            "screening_answers_extra",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "verification_status",
            sa.String(length=30),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("verification_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_by_admin_id", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_verified_hakeem",
            sa.Boolean(),
            server_default="false",
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
        sa.ForeignKeyConstraint(["reviewed_by_admin_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(
        op.f("ix_hakeem_profiles_user_id"), "hakeem_profiles", ["user_id"], unique=True
    )
    op.create_index(
        op.f("ix_hakeem_profiles_verification_status"),
        "hakeem_profiles",
        ["verification_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_hakeem_profiles_verification_status"), table_name="hakeem_profiles"
    )
    op.drop_index(op.f("ix_hakeem_profiles_user_id"), table_name="hakeem_profiles")
    op.drop_table("hakeem_profiles")
    op.drop_column("users", "role")
