from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# Service-layer floor (schema ge=1 is the absolute floor; apply() enforces >= 2).
MIN_YEARS_OF_EXPERIENCE = 2


class HakeemSignupRequest(BaseModel):
    """Combines account creation + verification application in one submission."""

    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=120)

    national_id_number: str = Field(min_length=5, max_length=64)
    national_id_document_url: str
    license_number: str | None = None
    license_document_url: str

    specializations: list[str] = Field(min_length=1)
    years_of_experience: int = Field(ge=1, le=60)
    city: str = Field(min_length=1, max_length=120)
    languages_spoken: list[str] = Field(min_length=1)
    consultation_fee: float = Field(gt=0)
    bio: str = Field(min_length=20, max_length=1000)

    training_institute: str = Field(min_length=1, max_length=200)
    previous_practice_location: str | None = None
    reason_for_joining: str = Field(min_length=20, max_length=1000)
    reference_contact: str | None = None
    agrees_to_terms: bool

    @field_validator("agrees_to_terms")
    @classmethod
    def must_agree(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Must agree to platform terms to apply.")
        return v


class HakeemPublicProfileResponse(BaseModel):
    """Safe to show in Discover / profile screens — no sensitive fields."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    full_name: str | None = None
    avatar_url: str | None = None
    specializations: list[str] | None = None
    bio: str | None = None
    city: str | None = None
    years_of_experience: int | None = None
    languages_spoken: list[str] | None = None
    consultation_fee: float | None = None
    rating_avg: float | None = None
    rating_count: int
    is_verified_hakeem: bool


class HakeemAdminReviewResponse(BaseModel):
    """Admin-only view — includes sensitive verification data + signed doc URLs."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    email: EmailStr | None = None
    full_name: str | None = None
    specializations: list[str] | None = None
    bio: str | None = None
    city: str | None = None
    years_of_experience: int | None = None
    languages_spoken: list[str] | None = None
    consultation_fee: float | None = None
    national_id_number: str
    national_id_document_url: str
    license_number: str | None
    license_document_url: str
    training_institute: str | None
    previous_practice_location: str | None
    reason_for_joining: str | None
    reference_contact: str | None
    screening_answers_extra: dict[str, Any] | None = None
    verification_status: str
    verification_notes: str | None
    is_verified_hakeem: bool
    created_at: datetime
    reviewed_at: datetime | None = None


class HakeemReviewDecisionRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=1000)


class VerificationDocumentUploadResponse(BaseModel):
    document_url: str
    document_type: str
    key: str
