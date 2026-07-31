import enum
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Gender(str, enum.Enum):
    MALE = "Male"
    FEMALE = "Female"
    PREFER_NOT_TO_SAY = "Prefer not to say"


class DietPreference(str, enum.Enum):
    VEGETARIAN = "Vegetarian"
    NON_VEGETARIAN = "Non-Vegetarian"
    VEGAN = "Vegan"
    EGGETARIAN = "Eggetarian"


class ActivityLevel(str, enum.Enum):
    LOW = "Low"
    MODERATE = "Moderate"
    ACTIVE = "Active"


class MizajType(str, enum.Enum):
    """Canonical Unani temperament keys (display names live in lookups metadata)."""

    DAMVI = "damvi"
    SAFRAVI = "safravi"
    BALGHAMI = "balghami"
    SAUDAVI = "saudavi"


class PreferredLanguage(str, enum.Enum):
    URDU = "urdu"
    ENGLISH = "english"
    PUNJABI = "punjabi"


class HakeemGenderPreference(str, enum.Enum):
    NO_PREFERENCE = "no_preference"
    MALE = "male"
    FEMALE = "female"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    full_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(40), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    diet_preference: Mapped[str | None] = mapped_column(String(40), nullable=True)
    activity_level: Mapped[str | None] = mapped_column(String(40), nullable=True)
    mizaj_hint: Mapped[str | None] = mapped_column(String(80), nullable=True)
    mizaj_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    mizaj_assessment_answers: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    preferred_language: Mapped[str | None] = mapped_column(String(40), nullable=True)
    preferred_hakeem_gender: Mapped[str | None] = mapped_column(String(40), nullable=True)
    health_interests: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    health_flags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
