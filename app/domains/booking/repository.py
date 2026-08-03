from datetime import date, datetime, time, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.booking.models import Booking, BookingStatus


class BookingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, booking: Booking) -> Booking:
        self.session.add(booking)
        await self.session.flush()
        await self.session.refresh(booking)
        return booking

    async def get_by_id(self, booking_id: UUID) -> Booking | None:
        result = await self.session.execute(
            select(Booking).where(Booking.id == booking_id)
        )
        return result.scalar_one_or_none()

    async def list_for_hakeem_on_date(
        self, hakeem_user_id: UUID, day: date
    ) -> list[Booking]:
        start = datetime.combine(day, time.min, tzinfo=timezone.utc)
        end = datetime.combine(day, time.max, tzinfo=timezone.utc)
        result = await self.session.execute(
            select(Booking)
            .where(
                Booking.hakeem_user_id == hakeem_user_id,
                Booking.scheduled_at >= start,
                Booking.scheduled_at <= end,
                Booking.status.in_(
                    [
                        BookingStatus.PENDING.value,
                        BookingStatus.CONFIRMED.value,
                        BookingStatus.COMPLETED.value,
                    ]
                ),
            )
            .order_by(Booking.scheduled_at.asc())
        )
        return list(result.scalars().all())

    async def list_for_hakeem_in_month(
        self, hakeem_user_id: UUID, year: int, month: int
    ) -> list[Booking]:
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
        result = await self.session.execute(
            select(Booking)
            .where(
                Booking.hakeem_user_id == hakeem_user_id,
                Booking.scheduled_at >= start,
                Booking.scheduled_at < end,
                Booking.status.in_(
                    [BookingStatus.PENDING.value, BookingStatus.CONFIRMED.value]
                ),
            )
            .order_by(Booking.scheduled_at.asc())
        )
        return list(result.scalars().all())

    async def count_for_hakeem_between(
        self, hakeem_user_id: UUID, start: datetime, end: datetime
    ) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(Booking)
            .where(
                Booking.hakeem_user_id == hakeem_user_id,
                Booking.scheduled_at >= start,
                Booking.scheduled_at < end,
                Booking.status.in_(
                    [
                        BookingStatus.CONFIRMED.value,
                        BookingStatus.COMPLETED.value,
                    ]
                ),
            )
        )
        return int(result.scalar_one())

    async def has_confirmed_on_date(
        self, hakeem_user_id: UUID, day: date
    ) -> bool:
        rows = await self.list_for_hakeem_on_date(hakeem_user_id, day)
        return any(b.status == BookingStatus.CONFIRMED.value for b in rows)

    async def list_confirmed_overlapping(
        self,
        hakeem_user_id: UUID,
        day: date,
        start_t: time,
        end_t: time,
    ) -> list[Booking]:
        """Bookings on `day` whose [scheduled_at, scheduled_at+duration) overlaps [start_t, end_t)."""
        day_bookings = await self.list_for_hakeem_on_date(hakeem_user_id, day)
        window_start = datetime.combine(day, start_t, tzinfo=timezone.utc)
        window_end = datetime.combine(day, end_t, tzinfo=timezone.utc)
        overlaps: list[Booking] = []
        for b in day_bookings:
            if b.status != BookingStatus.CONFIRMED.value:
                continue
            b_start = b.scheduled_at
            if b_start.tzinfo is None:
                b_start = b_start.replace(tzinfo=timezone.utc)
            from datetime import timedelta

            b_end = b_start + timedelta(minutes=b.duration_minutes)
            if b_start < window_end and b_end > window_start:
                overlaps.append(b)
        return overlaps
