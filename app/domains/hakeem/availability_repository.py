from datetime import date
from uuid import UUID

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.hakeem.models import HakeemDateAvailability, HakeemWeeklyAvailability


class AvailabilityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_weekly(self, hakeem_user_id: UUID) -> list[HakeemWeeklyAvailability]:
        result = await self.session.execute(
            select(HakeemWeeklyAvailability)
            .where(HakeemWeeklyAvailability.hakeem_user_id == hakeem_user_id)
            .order_by(
                HakeemWeeklyAvailability.day_of_week,
                HakeemWeeklyAvailability.start_time,
            )
        )
        return list(result.scalars().all())

    async def replace_weekly(
        self, hakeem_user_id: UUID, rows: list[HakeemWeeklyAvailability]
    ) -> list[HakeemWeeklyAvailability]:
        await self.session.execute(
            delete(HakeemWeeklyAvailability).where(
                HakeemWeeklyAvailability.hakeem_user_id == hakeem_user_id
            )
        )
        for row in rows:
            self.session.add(row)
        await self.session.flush()
        return await self.list_weekly(hakeem_user_id)

    async def list_date_overrides_in_range(
        self, hakeem_user_id: UUID, start: date, end: date
    ) -> list[HakeemDateAvailability]:
        result = await self.session.execute(
            select(HakeemDateAvailability)
            .where(
                HakeemDateAvailability.hakeem_user_id == hakeem_user_id,
                HakeemDateAvailability.specific_date >= start,
                HakeemDateAvailability.specific_date <= end,
            )
            .order_by(
                HakeemDateAvailability.specific_date,
                HakeemDateAvailability.start_time,
            )
        )
        return list(result.scalars().all())

    async def list_date_overrides_for_day(
        self, hakeem_user_id: UUID, day: date
    ) -> list[HakeemDateAvailability]:
        result = await self.session.execute(
            select(HakeemDateAvailability)
            .where(
                HakeemDateAvailability.hakeem_user_id == hakeem_user_id,
                HakeemDateAvailability.specific_date == day,
            )
            .order_by(HakeemDateAvailability.start_time)
        )
        return list(result.scalars().all())

    async def replace_date_overrides(
        self, hakeem_user_id: UUID, day: date, rows: list[HakeemDateAvailability]
    ) -> list[HakeemDateAvailability]:
        await self.session.execute(
            delete(HakeemDateAvailability).where(
                and_(
                    HakeemDateAvailability.hakeem_user_id == hakeem_user_id,
                    HakeemDateAvailability.specific_date == day,
                )
            )
        )
        for row in rows:
            self.session.add(row)
        await self.session.flush()
        return await self.list_date_overrides_for_day(hakeem_user_id, day)
