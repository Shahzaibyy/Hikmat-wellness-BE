from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.connections.models import Block, Connection, ConnectionStatus


class ConnectionsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_connection(
        self, *, requester_id: UUID, recipient_id: UUID
    ) -> Connection:
        conn = Connection(
            requester_id=requester_id,
            recipient_id=recipient_id,
            status=ConnectionStatus.PENDING.value,
        )
        self.session.add(conn)
        await self.session.flush()
        await self.session.refresh(conn)
        return conn

    async def get_by_id(self, connection_id: UUID) -> Connection | None:
        result = await self.session.execute(
            select(Connection).where(Connection.id == connection_id)
        )
        return result.scalar_one_or_none()

    async def find_between(
        self, user_a: UUID, user_b: UUID
    ) -> Connection | None:
        result = await self.session.execute(
            select(Connection).where(
                or_(
                    and_(
                        Connection.requester_id == user_a,
                        Connection.recipient_id == user_b,
                    ),
                    and_(
                        Connection.requester_id == user_b,
                        Connection.recipient_id == user_a,
                    ),
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self, user_id: UUID, *, status: str | None = None
    ) -> list[Connection]:
        stmt = select(Connection).where(
            or_(
                Connection.requester_id == user_id,
                Connection.recipient_id == user_id,
            )
        )
        if status is not None:
            stmt = stmt.where(Connection.status == status)
        stmt = stmt.order_by(Connection.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def save(self, connection: Connection) -> Connection:
        self.session.add(connection)
        await self.session.flush()
        await self.session.refresh(connection)
        return connection

    async def cancel_pending_between(self, user_a: UUID, user_b: UUID) -> int:
        result = await self.session.execute(
            update(Connection)
            .where(
                Connection.status == ConnectionStatus.PENDING.value,
                or_(
                    and_(
                        Connection.requester_id == user_a,
                        Connection.recipient_id == user_b,
                    ),
                    and_(
                        Connection.requester_id == user_b,
                        Connection.recipient_id == user_a,
                    ),
                ),
            )
            .values(
                status=ConnectionStatus.CANCELLED.value,
                responded_at=datetime.now(timezone.utc),
            )
        )
        return result.rowcount or 0

    # ── Blocks ──────────────────────────────────────────────────────────

    async def create_block(self, *, blocker_id: UUID, blocked_id: UUID) -> Block:
        block = Block(blocker_id=blocker_id, blocked_id=blocked_id)
        self.session.add(block)
        await self.session.flush()
        return block

    async def get_block(
        self, *, blocker_id: UUID, blocked_id: UUID
    ) -> Block | None:
        result = await self.session.execute(
            select(Block).where(
                Block.blocker_id == blocker_id,
                Block.blocked_id == blocked_id,
            )
        )
        return result.scalar_one_or_none()

    async def is_blocked_either_way(self, user_a: UUID, user_b: UUID) -> bool:
        result = await self.session.execute(
            select(Block).where(
                or_(
                    and_(Block.blocker_id == user_a, Block.blocked_id == user_b),
                    and_(Block.blocker_id == user_b, Block.blocked_id == user_a),
                )
            ).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def delete_block(self, *, blocker_id: UUID, blocked_id: UUID) -> bool:
        result = await self.session.execute(
            delete(Block).where(
                Block.blocker_id == blocker_id,
                Block.blocked_id == blocked_id,
            )
        )
        return (result.rowcount or 0) > 0

    async def list_blocked_by(self, blocker_id: UUID) -> list[Block]:
        result = await self.session.execute(
            select(Block)
            .where(Block.blocker_id == blocker_id)
            .order_by(Block.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_blocked_ids_by(self, blocker_id: UUID) -> set[UUID]:
        result = await self.session.execute(
            select(Block.blocked_id).where(Block.blocker_id == blocker_id)
        )
        return set(result.scalars().all())
