from __future__ import annotations

import calendar
from datetime import date, time
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.booking.service import BookingService
from app.domains.hakeem.availability_repository import AvailabilityRepository
from app.domains.hakeem.dashboard_schemas import (
    CalendarDayIndicator,
    CalendarMonthResponse,
    DateAvailabilityPatchRequest,
    DateAvailabilityResponse,
    DateSlotResponse,
    TimeSlot,
    WeeklyDefaultRequest,
    WeeklySlotResponse,
)
from app.domains.hakeem.exceptions import AvailabilityConflictError, InvalidHakeemApplicationError
from app.domains.hakeem.models import HakeemDateAvailability, HakeemWeeklyAvailability


class AvailabilityService:
    """Owns recurring weekly defaults + per-date overrides for a hakeem."""

    def __init__(self, session: AsyncSession) -> None:
        self.repo = AvailabilityRepository(session)
        self.bookings = BookingService(session)

    async def get_calendar_month(
        self, hakeem_user_id: UUID, year: int, month: int
    ) -> CalendarMonthResponse:
        if month < 1 or month > 12:
            raise InvalidHakeemApplicationError(
                "month must be 1–12.", field="month", value=str(month)
            )
        last_day = calendar.monthrange(year, month)[1]
        start = date(year, month, 1)
        end = date(year, month, last_day)

        weekly = await self.repo.list_weekly(hakeem_user_id)
        overrides = await self.repo.list_date_overrides_in_range(
            hakeem_user_id, start, end
        )
        appt_dates = await self.bookings.dates_with_appointments(
            hakeem_user_id, year, month
        )

        overrides_by_date: dict[date, list[HakeemDateAvailability]] = {}
        for row in overrides:
            overrides_by_date.setdefault(row.specific_date, []).append(row)

        weekly_by_dow: dict[int, list[HakeemWeeklyAvailability]] = {}
        for row in weekly:
            weekly_by_dow.setdefault(row.day_of_week, []).append(row)

        days: list[CalendarDayIndicator] = []
        for day_num in range(1, last_day + 1):
            d = date(year, month, day_num)
            has_avail = self._day_has_availability(d, weekly_by_dow, overrides_by_date)
            days.append(
                CalendarDayIndicator(
                    date=d,
                    has_availability=has_avail,
                    has_appointment=d in appt_dates,
                )
            )

        upcoming = await self.bookings.list_month_for_hakeem(hakeem_user_id, year, month)
        return CalendarMonthResponse(
            year=year,
            month=month,
            days=days,
            upcoming=upcoming,
        )

    async def set_weekly_default(
        self, hakeem_user_id: UUID, payload: WeeklyDefaultRequest
    ) -> list[WeeklySlotResponse]:
        rows: list[HakeemWeeklyAvailability] = []
        for day in payload.days:
            if not day.is_available:
                # Store a sentinel full-day unavailable marker for clarity in the weekly table.
                rows.append(
                    HakeemWeeklyAvailability(
                        hakeem_user_id=hakeem_user_id,
                        day_of_week=day.day_of_week,
                        start_time=time(0, 0),
                        end_time=time(23, 59),
                        is_available=False,
                    )
                )
                continue
            for slot in day.slots:
                rows.append(
                    HakeemWeeklyAvailability(
                        hakeem_user_id=hakeem_user_id,
                        day_of_week=day.day_of_week,
                        start_time=slot.start_time,
                        end_time=slot.end_time,
                        is_available=True,
                    )
                )
        saved = await self.repo.replace_weekly(hakeem_user_id, rows)
        return [
            WeeklySlotResponse(
                day_of_week=r.day_of_week,
                start_time=r.start_time,
                end_time=r.end_time,
                is_available=r.is_available,
            )
            for r in saved
        ]

    async def patch_date(
        self,
        hakeem_user_id: UUID,
        day: date,
        payload: DateAvailabilityPatchRequest,
    ) -> DateAvailabilityResponse:
        if not payload.is_available:
            # Conflict if any confirmed booking exists that day.
            if await self.bookings.has_confirmed_overlap(
                hakeem_user_id, day, time(0, 0), time(23, 59)
            ):
                raise AvailabilityConflictError(
                    f"Cannot mark {day.isoformat()} unavailable — a confirmed booking exists."
                )
            rows = [
                HakeemDateAvailability(
                    hakeem_user_id=hakeem_user_id,
                    specific_date=day,
                    start_time=time(0, 0),
                    end_time=time(23, 59),
                    is_available=False,
                )
            ]
        else:
            for slot in payload.slots:
                # Soft check: marking available is fine even with bookings;
                # only shrinking/removing coverage over a booking is blocked via unavailable path.
                pass
            rows = [
                HakeemDateAvailability(
                    hakeem_user_id=hakeem_user_id,
                    specific_date=day,
                    start_time=s.start_time,
                    end_time=s.end_time,
                    is_available=True,
                )
                for s in payload.slots
            ]
            # If slots don't cover an existing confirmed booking window, reject.
            await self._assert_slots_cover_bookings(hakeem_user_id, day, payload.slots)

        saved = await self.repo.replace_date_overrides(hakeem_user_id, day, rows)
        is_available = any(r.is_available for r in saved)
        return DateAvailabilityResponse(
            date=day,
            is_available=is_available,
            slots=[
                DateSlotResponse(
                    date=r.specific_date,
                    start_time=r.start_time,
                    end_time=r.end_time,
                    is_available=r.is_available,
                )
                for r in saved
            ],
        )

    async def _assert_slots_cover_bookings(
        self, hakeem_user_id: UUID, day: date, slots: list[TimeSlot]
    ) -> None:
        from datetime import datetime, timedelta, timezone

        bookings = await self.bookings.list_confirmed_on_date(hakeem_user_id, day)
        for b in bookings:
            start = b.scheduled_at
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            end = start + timedelta(minutes=b.duration_minutes)
            b_start_t = start.timetz().replace(tzinfo=None)
            b_end_t = end.timetz().replace(tzinfo=None)
            covered = any(
                s.start_time <= b_start_t and s.end_time >= b_end_t for s in slots
            )
            if not covered:
                raise AvailabilityConflictError(
                    f"Availability slots on {day.isoformat()} must cover the confirmed "
                    f"booking at {start.isoformat()}."
                )

    @staticmethod
    def _day_has_availability(
        d: date,
        weekly_by_dow: dict[int, list[HakeemWeeklyAvailability]],
        overrides_by_date: dict[date, list[HakeemDateAvailability]],
    ) -> bool:
        if d in overrides_by_date:
            return any(r.is_available for r in overrides_by_date[d])
        dow = d.weekday()  # Monday=0
        rows = weekly_by_dow.get(dow, [])
        return any(r.is_available for r in rows)
