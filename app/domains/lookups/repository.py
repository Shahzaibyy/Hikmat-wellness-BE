from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.lookups.models import LookupOption


class LookupRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_by_type(self, lookup_type: str) -> list[LookupOption]:
        result = await self.session.execute(
            select(LookupOption)
            .where(
                LookupOption.type == lookup_type,
                LookupOption.is_active.is_(True),
            )
            .order_by(LookupOption.sort_order.asc(), LookupOption.label.asc())
        )
        return list(result.scalars().all())

    async def list_keys(self, lookup_type: str) -> set[str]:
        rows = await self.list_by_type(lookup_type)
        return {row.key for row in rows}
