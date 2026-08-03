from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    role: str
    full_name: str | None = None
    gender: str | None = None
    date_of_birth: date | None = None
    city: str | None = None
    avatar_url: str | None = None
    diet_preference: str | None = None
    activity_level: str | None = None
    mizaj_hint: str | None = None
    mizaj_type: str | None = None
    mizaj_assessment_answers: dict[str, Any] | None = None
    preferred_language: str | None = None
    preferred_hakeem_gender: str | None = None
    health_interests: list[str] | None = None
    health_flags: list[str] | None = None
    notes: str | None = None
    onboarding_completed: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # Populated for role=hakeem from HakeemProfile (null for patients/admins).
    is_verified_hakeem: bool | None = None
    verification_status: str | None = None


class OnboardingUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    gender: str | None = None
    date_of_birth: date | None = None
    city: str | None = Field(default=None, max_length=120)
    avatar_url: str | None = Field(default=None, max_length=500)
    diet_preference: str | None = None
    activity_level: str | None = None
    mizaj_hint: str | None = None
    mizaj_type: str | None = None
    mizaj_assessment_answers: dict[str, Any] | None = None
    preferred_language: str | None = None
    preferred_hakeem_gender: str | None = None
    health_interests: list[str] | None = None
    health_flags: list[str] | None = None
    notes: str | None = Field(default=None, max_length=2000)
    complete: bool = True
