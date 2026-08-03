import enum
import uuid
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class HakeemVerificationStatus(str, enum.Enum):
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    NEEDS_MORE_INFO = "needs_more_info"
    APPROVED = "approved"
    REJECTED = "rejected"


class HakeemProfile(Base):
    __tablename__ = "hakeem_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # Public profile fields (shown once approved)
    specializations: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    years_of_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    languages_spoken: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    consultation_fee: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    rating_avg: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    rating_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )

    # Sensitive verification data — never exposed in public schemas
    national_id_number: Mapped[str] = mapped_column(String(64), nullable=False)
    national_id_document_url: Mapped[str] = mapped_column(String(500), nullable=False)
    license_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    license_document_url: Mapped[str] = mapped_column(String(500), nullable=False)

    # Screening question answers
    training_institute: Mapped[str | None] = mapped_column(String(200), nullable=True)
    previous_practice_location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reason_for_joining: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_contact: Mapped[str | None] = mapped_column(String(120), nullable=True)
    screening_answers_extra: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Verification workflow state
    verification_status: Mapped[str] = mapped_column(
        String(30),
        default=HakeemVerificationStatus.PENDING.value,
        server_default="pending",
        nullable=False,
        index=True,
    )
    verification_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    is_verified_hakeem: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class HakeemWeeklyAvailability(Base):
    """Recurring weekly default slots (day_of_week: 0=Monday … 6=Sunday)."""

    __tablename__ = "hakeem_weekly_availability"
    __table_args__ = (
        UniqueConstraint(
            "hakeem_user_id",
            "day_of_week",
            "start_time",
            "end_time",
            name="uq_hakeem_weekly_slot",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    hakeem_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    day_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_available: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )


class HakeemDateAvailability(Base):
    """Per-date override of the weekly default (including explicit unavailable days)."""

    __tablename__ = "hakeem_date_availability"
    __table_args__ = (
        UniqueConstraint(
            "hakeem_user_id",
            "specific_date",
            "start_time",
            "end_time",
            name="uq_hakeem_date_slot",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    hakeem_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    specific_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_available: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
