from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.hakeem.models import HakeemProfile


class HakeemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, profile: HakeemProfile) -> HakeemProfile:
        self.session.add(profile)
        await self.session.flush()
        await self.session.refresh(profile)
        return profile

    async def get_by_id(self, profile_id: UUID) -> HakeemProfile | None:
        result = await self.session.execute(
            select(HakeemProfile).where(HakeemProfile.id == profile_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: UUID) -> HakeemProfile | None:
        result = await self.session.execute(
            select(HakeemProfile).where(HakeemProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_by_status(
        self,
        status: str,
        *,
        limit: int,
        cursor_created_at=None,
        cursor_id: UUID | None = None,
    ) -> list[HakeemProfile]:
        from datetime import datetime

        from sqlalchemy import and_, or_

        stmt = (
            select(HakeemProfile)
            .where(HakeemProfile.verification_status == status)
            .order_by(HakeemProfile.created_at.desc(), HakeemProfile.id.desc())
            .limit(limit)
        )
        if cursor_created_at is not None and cursor_id is not None:
            stmt = stmt.where(
                or_(
                    HakeemProfile.created_at < cursor_created_at,
                    and_(
                        HakeemProfile.created_at == cursor_created_at,
                        HakeemProfile.id < cursor_id,
                    ),
                )
            )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_verified_user_ids(self, user_ids: list[UUID]) -> set[UUID]:
        if not user_ids:
            return set()
        result = await self.session.execute(
            select(HakeemProfile.user_id).where(
                HakeemProfile.user_id.in_(user_ids),
                HakeemProfile.is_verified_hakeem.is_(True),
            )
        )
        return set(result.scalars().all())

    async def save(self, profile: HakeemProfile) -> HakeemProfile:
        self.session.add(profile)
        await self.session.flush()
        await self.session.refresh(profile)
        return profile
