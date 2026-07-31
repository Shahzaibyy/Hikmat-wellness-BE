"""create users and lookups tables

Revision ID: 90cded402778
Revises: 
Create Date: 2026-07-30 13:21:29.752043

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '90cded402778'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

HEALTH_INTERESTS = [
    "Digestion",
    "Skin & Beauty",
    "Immunity",
    "Weight Management",
    "Stress & Sleep",
    "Joint & Bone Health",
    "Hair Care",
    "Blood Sugar Balance",
    "Heart Health",
    "Women's Health",
    "Men's Health",
]

HEALTH_FLAGS = [
    ("allergies", "Allergies"),
    ("medication", "Currently on medication"),
    ("pregnant", "Pregnant/breastfeeding"),
    ("chronic", "Chronic condition"),
]


def upgrade() -> None:
    op.create_table('lookup_options',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('type', sa.String(length=64), nullable=False),
    sa.Column('key', sa.String(length=120), nullable=False),
    sa.Column('label', sa.String(length=160), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('icon', sa.String(length=64), nullable=True),
    sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('type', 'key', name='uq_lookup_type_key')
    )
    op.create_index(op.f('ix_lookup_options_type'), 'lookup_options', ['type'], unique=False)
    op.create_table('users',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('hashed_password', sa.String(length=255), nullable=False),
    sa.Column('full_name', sa.String(length=120), nullable=True),
    sa.Column('gender', sa.String(length=40), nullable=True),
    sa.Column('date_of_birth', sa.Date(), nullable=True),
    sa.Column('city', sa.String(length=120), nullable=True),
    sa.Column('avatar_url', sa.String(length=500), nullable=True),
    sa.Column('diet_preference', sa.String(length=40), nullable=True),
    sa.Column('activity_level', sa.String(length=40), nullable=True),
    sa.Column('mizaj_hint', sa.String(length=80), nullable=True),
    sa.Column('health_interests', postgresql.ARRAY(sa.String()), nullable=True),
    sa.Column('health_flags', postgresql.ARRAY(sa.String()), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('onboarding_completed', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    lookup_table = sa.table(
        'lookup_options',
        sa.column('id', sa.UUID()),
        sa.column('type', sa.String()),
        sa.column('key', sa.String()),
        sa.column('label', sa.String()),
        sa.column('description', sa.Text()),
        sa.column('icon', sa.String()),
        sa.column('sort_order', sa.Integer()),
        sa.column('is_active', sa.Boolean()),
    )
    interest_rows = [
        {
            'id': uuid.uuid4(),
            'type': 'health_interest',
            'key': label,
            'label': label,
            'description': None,
            'icon': None,
            'sort_order': idx,
            'is_active': True,
        }
        for idx, label in enumerate(HEALTH_INTERESTS)
    ]
    flag_rows = [
        {
            'id': uuid.uuid4(),
            'type': 'health_flag',
            'key': key,
            'label': label,
            'description': None,
            'icon': None,
            'sort_order': idx,
            'is_active': True,
        }
        for idx, (key, label) in enumerate(HEALTH_FLAGS)
    ]
    op.bulk_insert(lookup_table, interest_rows + flag_rows)


def downgrade() -> None:
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_lookup_options_type'), table_name='lookup_options')
    op.drop_table('lookup_options')
