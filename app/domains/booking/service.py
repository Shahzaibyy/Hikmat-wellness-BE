from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.booking.models import Booking, BookingStatus
from app.domains.booking.repository import BookingRepository
from app.domains.booking.schemas import BookingCreateRequest, BookingPatientPreview, BookingResponse
from app.domains.users.service import UserService

JOIN_WINDOW_BEFORE_MINUTES = 15


class BookingService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = BookingRepository(session)
        self.users = UserService(session)

    async def create(self, payload: BookingCreateRequest) -> BookingResponse:
        booking = Booking(
            hakeem_user_id=payload.hakeem_user_id,
            patient_user_id=payload.patient_user_id,
            scheduled_at=payload.scheduled_at,
            duration_minutes=payload.duration_minutes,
            appointment_type=payload.appointment_type,
            status=payload.status,
        )
        created = await self.repo.create(booking)
        return await self._to_response(created)

    async def list_today_for_hakeem(self, hakeem_user_id: UUID) -> list[BookingResponse]:
        today = datetime.now(timezone.utc).date()
        rows = await self.repo.list_for_hakeem_on_date(hakeem_user_id, today)
        return [await self._to_response(b) for b in rows]

    async def list_month_for_hakeem(
        self, hakeem_user_id: UUID, year: int, month: int
    ) -> list[BookingResponse]:
        rows = await self.repo.list_for_hakeem_in_month(hakeem_user_id, year, month)
        return [await self._to_response(b) for b in rows]

    async def dates_with_appointments(
        self, hakeem_user_id: UUID, year: int, month: int
    ) -> set[date]:
        rows = await self.repo.list_for_hakeem_in_month(hakeem_user_id, year, month)
        return {b.scheduled_at.astimezone(timezone.utc).date() for b in rows}

    async def count_this_week(self, hakeem_user_id: UUID) -> int:
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)
        return await self.repo.count_for_hakeem_between(hakeem_user_id, start, end)

    async def has_confirmed_overlap(
        self,
        hakeem_user_id: UUID,
        day: date,
        start_t,
        end_t,
    ) -> bool:
        overlaps = await self.repo.list_confirmed_overlapping(
            hakeem_user_id, day, start_t, end_t
        )
        return len(overlaps) > 0

    async def list_confirmed_on_date(
        self, hakeem_user_id: UUID, day: date
    ) -> list[Booking]:
        rows = await self.repo.list_for_hakeem_on_date(hakeem_user_id, day)
        return [b for b in rows if b.status == BookingStatus.CONFIRMED.value]

    async def _to_response(self, booking: Booking) -> BookingResponse:
        patient = await self.users.get_by_id(booking.patient_user_id)
        return BookingResponse(
            id=booking.id,
            hakeem_user_id=booking.hakeem_user_id,
            patient=BookingPatientPreview(
                id=patient.id,
                full_name=patient.full_name,
                avatar_url=patient.avatar_url,
            ),
            scheduled_at=booking.scheduled_at,
            duration_minutes=booking.duration_minutes,
            appointment_type=booking.appointment_type,
            status=booking.status,
            can_join=self._can_join(booking),
        )

    @staticmethod
    def _can_join(booking: Booking) -> bool:
        if booking.status not in {
            BookingStatus.CONFIRMED.value,
            BookingStatus.PENDING.value,
        }:
            return False
        now = datetime.now(timezone.utc)
        start = booking.scheduled_at
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        end = start + timedelta(minutes=booking.duration_minutes)
        join_from = start - timedelta(minutes=JOIN_WINDOW_BEFORE_MINUTES)
        return join_from <= now <= end
