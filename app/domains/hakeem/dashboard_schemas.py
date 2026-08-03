from __future__ import annotations

from datetime import date, time
from uuid import UUID

from app.domains.booking.schemas import BookingResponse
from pydantic import BaseModel, Field, field_validator, model_validator


class TimeSlot(BaseModel):
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def end_after_start(self) -> TimeSlot:
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time.")
        return self


class WeeklyDaySlots(BaseModel):
    day_of_week: int = Field(ge=0, le=6, description="0=Monday … 6=Sunday")
    is_available: bool = True
    slots: list[TimeSlot] = Field(default_factory=list)

    @model_validator(mode="after")
    def slots_when_available(self) -> WeeklyDaySlots:
        if self.is_available and not self.slots:
            raise ValueError("Available days must include at least one time slot.")
        if not self.is_available:
            self.slots = []
        return self


class WeeklyDefaultRequest(BaseModel):
    days: list[WeeklyDaySlots] = Field(min_length=1)


class DateAvailabilityPatchRequest(BaseModel):
    """Bottom-sheet-per-date toggle: mark day available/unavailable + optional slots."""

    is_available: bool
    slots: list[TimeSlot] = Field(default_factory=list)

    @model_validator(mode="after")
    def slots_when_available(self) -> DateAvailabilityPatchRequest:
        if self.is_available and not self.slots:
            raise ValueError("When marking a date available, provide at least one slot.")
        if not self.is_available:
            self.slots = []
        return self


class CalendarDayIndicator(BaseModel):
    date: date
    has_availability: bool
    has_appointment: bool


class CalendarMonthResponse(BaseModel):
    year: int
    month: int
    days: list[CalendarDayIndicator]
    upcoming: list[BookingResponse]


class WeeklySlotResponse(BaseModel):
    day_of_week: int
    start_time: time
    end_time: time
    is_available: bool


class DateSlotResponse(BaseModel):
    date: date
    start_time: time
    end_time: time
    is_available: bool


class DateAvailabilityResponse(BaseModel):
    date: date
    is_available: bool
    slots: list[DateSlotResponse]


# ── Dashboard ──────────────────────────────────────────────────────────────


class DashboardQuickStats(BaseModel):
    consultations_this_week: int
    average_rating: float | None = None
    response_rate: float = Field(description="% of connection requests responded within 24h")


class DashboardConsultationItem(BaseModel):
    id: UUID
    patient_id: UUID
    patient_name: str | None = None
    patient_avatar_url: str | None = None
    scheduled_at: str  # ISO datetime — frontend formats locally
    appointment_type: str
    can_join: bool
    status: str


class DashboardConnectionRequest(BaseModel):
    id: UUID
    requester_id: UUID
    requester_name: str | None = None
    requester_avatar_url: str | None = None
    note: str | None = None
    created_at: str


class HakeemDashboardResponse(BaseModel):
    greeting_name: str | None = None
    consultations_today_count: int
    quick_stats: DashboardQuickStats
    todays_schedule: list[DashboardConsultationItem]
    pending_connection_requests: list[DashboardConnectionRequest]


# ── Self profile ───────────────────────────────────────────────────────────


class HakeemMeProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    full_name: str | None = None
    avatar_url: str | None = None
    email: str | None = None
    specializations: list[str] | None = None
    bio: str | None = None
    city: str | None = None
    years_of_experience: int | None = None
    languages_spoken: list[str] | None = None
    consultation_fee: float | None = None
    rating_avg: float | None = None
    rating_count: int = 0
    is_verified_hakeem: bool
    verification_status: str
    # Approximate patient count from accepted connections where hakeem is recipient/peer.
    patients_count: int = 0


class HakeemMeProfileUpdateRequest(BaseModel):
    bio: str | None = Field(default=None, min_length=20, max_length=1000)
    specializations: list[str] | None = Field(default=None, min_length=1)
    consultation_fee: float | None = Field(default=None, gt=0)
    languages_spoken: list[str] | None = Field(default=None, min_length=1)
    city: str | None = Field(default=None, min_length=1, max_length=120)

    @field_validator("bio")
    @classmethod
    def strip_bio(cls, v: str | None) -> str | None:
        return v.strip() if v is not None else v

    @field_validator("city")
    @classmethod
    def strip_city(cls, v: str | None) -> str | None:
        return v.strip() if v is not None else v
