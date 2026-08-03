from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BookingPatientPreview(BaseModel):
    id: UUID
    full_name: str | None = None
    avatar_url: str | None = None


class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    hakeem_user_id: UUID
    patient: BookingPatientPreview
    scheduled_at: datetime
    duration_minutes: int
    appointment_type: str
    status: str
    can_join: bool = False


class BookingCreateRequest(BaseModel):
    """Minimal create for seeding / future patient booking flow."""

    hakeem_user_id: UUID
    patient_user_id: UUID
    scheduled_at: datetime
    duration_minutes: int = Field(default=30, ge=15, le=180)
    appointment_type: str = Field(default="Consultation", max_length=80)
    status: str = "confirmed"
