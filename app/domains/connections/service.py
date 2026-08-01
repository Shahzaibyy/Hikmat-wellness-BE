from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.chat.service import ChatService
from app.domains.connections.exceptions import (
    CannotConnectSelfError,
    ConnectionBlockedError,
    ConnectionConflictError,
    ConnectionForbiddenError,
    ConnectionNotFoundError,
    InvalidConnectionStateError,
)
from app.domains.connections.models import Connection, ConnectionStatus
from app.domains.connections.repository import ConnectionsRepository
from app.domains.connections.schemas import (
    BlockCreateRequest,
    BlockResponse,
    ConnectionRequestCreate,
    ConnectionResponse,
    ConnectionStatusEnum,
    ConnectionUserPreview,
    RelationshipStatus,
    RelationshipStatusResponse,
)
from app.domains.users.models import User
from app.domains.users.service import UserService


class ConnectionsService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = ConnectionsRepository(session)
        self.users = UserService(session)
        self.chat = ChatService(session)
        self.chat.set_block_checker(self.is_blocked_either_way)

    async def is_blocked_either_way(self, user_a: UUID, user_b: UUID) -> bool:
        return await self.repo.is_blocked_either_way(user_a, user_b)

    async def request_connection(
        self, requester: User, payload: ConnectionRequestCreate
    ) -> ConnectionResponse:
        if requester.id == payload.recipient_id:
            raise CannotConnectSelfError()
        recipient = await self.users.get_by_id(payload.recipient_id)

        if await self.repo.is_blocked_either_way(requester.id, recipient.id):
            raise ConnectionBlockedError()

        existing = await self.repo.find_between(requester.id, recipient.id)
        if existing is not None:
            if existing.status in {
                ConnectionStatus.PENDING.value,
                ConnectionStatus.ACCEPTED.value,
            }:
                raise ConnectionConflictError(
                    f"Connection already {existing.status}."
                )
            # Re-open a rejected/cancelled pair as a fresh pending request.
            existing.requester_id = requester.id
            existing.recipient_id = recipient.id
            existing.status = ConnectionStatus.PENDING.value
            existing.responded_at = None
            saved = await self.repo.save(existing)
            return await self._to_connection_response(saved)

        created = await self.repo.create_connection(
            requester_id=requester.id, recipient_id=recipient.id
        )
        return await self._to_connection_response(created)

    async def accept(self, actor: User, connection_id: UUID) -> ConnectionResponse:
        conn = await self._get(connection_id)
        if conn.recipient_id != actor.id:
            raise ConnectionForbiddenError("Only the recipient can accept.")
        if conn.status != ConnectionStatus.PENDING.value:
            raise InvalidConnectionStateError("Connection is not pending.")
        if await self.repo.is_blocked_either_way(conn.requester_id, conn.recipient_id):
            raise ConnectionBlockedError()

        conn.status = ConnectionStatus.ACCEPTED.value
        conn.responded_at = datetime.now(timezone.utc)
        saved = await self.repo.save(conn)

        conversation = await self.chat.get_or_create_direct_conversation(
            saved.requester_id, saved.recipient_id
        )
        response = await self._to_connection_response(saved)
        response.conversation_id = conversation.id
        return response

    async def reject(self, actor: User, connection_id: UUID) -> ConnectionResponse:
        conn = await self._get(connection_id)
        if conn.recipient_id != actor.id:
            raise ConnectionForbiddenError("Only the recipient can reject.")
        if conn.status != ConnectionStatus.PENDING.value:
            raise InvalidConnectionStateError("Connection is not pending.")
        conn.status = ConnectionStatus.REJECTED.value
        conn.responded_at = datetime.now(timezone.utc)
        saved = await self.repo.save(conn)
        return await self._to_connection_response(saved)

    async def cancel(self, actor: User, connection_id: UUID) -> ConnectionResponse:
        conn = await self._get(connection_id)
        if conn.requester_id != actor.id:
            raise ConnectionForbiddenError("Only the requester can cancel.")
        if conn.status != ConnectionStatus.PENDING.value:
            raise InvalidConnectionStateError("Connection is not pending.")
        conn.status = ConnectionStatus.CANCELLED.value
        conn.responded_at = datetime.now(timezone.utc)
        saved = await self.repo.save(conn)
        return await self._to_connection_response(saved)

    async def list_connections(
        self, viewer: User, *, status: ConnectionStatusEnum | None = None
    ) -> list[ConnectionResponse]:
        rows = await self.repo.list_for_user(
            viewer.id, status=status.value if status else None
        )
        return [await self._to_connection_response(r) for r in rows]

    async def block(
        self, blocker: User, payload: BlockCreateRequest
    ) -> BlockResponse:
        if blocker.id == payload.user_id:
            raise CannotConnectSelfError()
        blocked = await self.users.get_by_id(payload.user_id)

        existing = await self.repo.get_block(
            blocker_id=blocker.id, blocked_id=blocked.id
        )
        if existing is None:
            existing = await self.repo.create_block(
                blocker_id=blocker.id, blocked_id=blocked.id
            )
        await self.repo.cancel_pending_between(blocker.id, blocked.id)
        return BlockResponse(
            blocker_id=existing.blocker_id,
            blocked_id=existing.blocked_id,
            blocked_user=ConnectionUserPreview(
                id=blocked.id,
                full_name=blocked.full_name,
                avatar_url=blocked.avatar_url,
            ),
            created_at=existing.created_at,
        )

    async def unblock(self, blocker: User, user_id: UUID) -> None:
        removed = await self.repo.delete_block(
            blocker_id=blocker.id, blocked_id=user_id
        )
        if not removed:
            raise ConnectionNotFoundError()

    async def list_blocked(self, blocker: User) -> list[BlockResponse]:
        blocks = await self.repo.list_blocked_by(blocker.id)
        out: list[BlockResponse] = []
        for b in blocks:
            user = await self.users.get_by_id(b.blocked_id)
            out.append(
                BlockResponse(
                    blocker_id=b.blocker_id,
                    blocked_id=b.blocked_id,
                    blocked_user=ConnectionUserPreview(
                        id=user.id,
                        full_name=user.full_name,
                        avatar_url=user.avatar_url,
                    ),
                    created_at=b.created_at,
                )
            )
        return out

    async def get_relationship_status(
        self, viewer: User, other_user_id: UUID
    ) -> RelationshipStatusResponse:
        """Expose for Discover / profile badges without extra list round-trips."""
        if viewer.id == other_user_id:
            return RelationshipStatusResponse(
                user_id=other_user_id, status=RelationshipStatus.none
            )

        if await self.repo.get_block(blocker_id=viewer.id, blocked_id=other_user_id):
            return RelationshipStatusResponse(
                user_id=other_user_id, status=RelationshipStatus.blocked
            )
        if await self.repo.get_block(blocker_id=other_user_id, blocked_id=viewer.id):
            return RelationshipStatusResponse(
                user_id=other_user_id, status=RelationshipStatus.blocked_by_them
            )

        conn = await self.repo.find_between(viewer.id, other_user_id)
        if conn is None:
            return RelationshipStatusResponse(
                user_id=other_user_id, status=RelationshipStatus.none
            )
        if conn.status == ConnectionStatus.ACCEPTED.value:
            return RelationshipStatusResponse(
                user_id=other_user_id,
                status=RelationshipStatus.connected,
                connection_id=conn.id,
            )
        if conn.status == ConnectionStatus.PENDING.value:
            status = (
                RelationshipStatus.pending_outgoing
                if conn.requester_id == viewer.id
                else RelationshipStatus.pending_incoming
            )
            return RelationshipStatusResponse(
                user_id=other_user_id, status=status, connection_id=conn.id
            )
        return RelationshipStatusResponse(
            user_id=other_user_id, status=RelationshipStatus.none, connection_id=conn.id
        )

    async def _get(self, connection_id: UUID) -> Connection:
        conn = await self.repo.get_by_id(connection_id)
        if conn is None:
            raise ConnectionNotFoundError()
        return conn

    async def _to_connection_response(self, conn: Connection) -> ConnectionResponse:
        requester = await self.users.get_by_id(conn.requester_id)
        recipient = await self.users.get_by_id(conn.recipient_id)
        conversation_id = None
        if conn.status == ConnectionStatus.ACCEPTED.value:
            existing = await self.chat.repo.find_direct_conversation(
                conn.requester_id, conn.recipient_id
            )
            if existing is not None:
                conversation_id = existing.id
        return ConnectionResponse(
            id=conn.id,
            requester=ConnectionUserPreview(
                id=requester.id,
                full_name=requester.full_name,
                avatar_url=requester.avatar_url,
            ),
            recipient=ConnectionUserPreview(
                id=recipient.id,
                full_name=recipient.full_name,
                avatar_url=recipient.avatar_url,
            ),
            status=ConnectionStatusEnum(conn.status),
            created_at=conn.created_at,
            responded_at=conn.responded_at,
            conversation_id=conversation_id,
        )
