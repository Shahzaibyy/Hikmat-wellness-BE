from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import Select, and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.domains.chat.models import (
    TOMBSTONE_BODY,
    Conversation,
    ConversationParticipant,
    Message,
    MessageHiddenForUser,
    MessageReaction,
)


class ChatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── Conversations ───────────────────────────────────────────────────

    async def create_conversation(
        self, *, participant_ids: list[UUID]
    ) -> Conversation:
        conversation = Conversation()
        self.session.add(conversation)
        await self.session.flush()
        for user_id in participant_ids:
            self.session.add(
                ConversationParticipant(
                    conversation_id=conversation.id,
                    user_id=user_id,
                )
            )
        await self.session.flush()
        return await self.get_conversation(conversation.id)  # type: ignore[return-value]

    async def get_conversation(self, conversation_id: UUID) -> Conversation | None:
        result = await self.session.execute(
            select(Conversation)
            .options(
                selectinload(Conversation.participants).joinedload(
                    ConversationParticipant.user
                )
            )
            .where(Conversation.id == conversation_id)
        )
        return result.scalar_one_or_none()

    async def find_direct_conversation(
        self, user_a: UUID, user_b: UUID
    ) -> Conversation | None:
        """Find a 1:1 conversation that contains exactly these two users."""
        cp = ConversationParticipant
        sub_a = select(cp.conversation_id).where(cp.user_id == user_a)
        sub_b = select(cp.conversation_id).where(cp.user_id == user_b)
        result = await self.session.execute(
            select(Conversation)
            .options(
                selectinload(Conversation.participants).joinedload(
                    ConversationParticipant.user
                )
            )
            .where(
                Conversation.id.in_(sub_a),
                Conversation.id.in_(sub_b),
            )
        )
        for conv in result.scalars().unique().all():
            if len(conv.participants) == 2:
                return conv
        return None

    async def list_user_conversations(self, user_id: UUID) -> list[Conversation]:
        result = await self.session.execute(
            select(Conversation)
            .join(ConversationParticipant)
            .options(
                selectinload(Conversation.participants).joinedload(
                    ConversationParticipant.user
                )
            )
            .where(ConversationParticipant.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
        )
        return list(result.scalars().unique().all())

    async def get_participant(
        self, *, conversation_id: UUID, user_id: UUID
    ) -> ConversationParticipant | None:
        result = await self.session.execute(
            select(ConversationParticipant).where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_participant_user_ids(self, conversation_id: UUID) -> list[UUID]:
        result = await self.session.execute(
            select(ConversationParticipant.user_id).where(
                ConversationParticipant.conversation_id == conversation_id
            )
        )
        return list(result.scalars().all())

    async def list_conversation_ids_for_user(self, user_id: UUID) -> list[UUID]:
        result = await self.session.execute(
            select(ConversationParticipant.conversation_id).where(
                ConversationParticipant.user_id == user_id
            )
        )
        return list(result.scalars().all())

    async def touch_conversation(self, conversation_id: UUID) -> None:
        await self.session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(updated_at=func.now())
        )

    async def update_last_read(
        self, *, conversation_id: UUID, user_id: UUID, read_at: datetime
    ) -> None:
        await self.session.execute(
            update(ConversationParticipant)
            .where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.user_id == user_id,
            )
            .values(last_read_at=read_at)
        )

    # ── Messages ────────────────────────────────────────────────────────

    def _message_load_options(self):
        return (
            joinedload(Message.sender),
            joinedload(Message.reply_to).joinedload(Message.sender),
            selectinload(Message.reactions),
        )

    async def create_message(self, message: Message) -> Message:
        self.session.add(message)
        await self.session.flush()
        await self.touch_conversation(message.conversation_id)
        return await self.get_message(message.id)  # type: ignore[return-value]

    async def get_message(self, message_id: UUID) -> Message | None:
        result = await self.session.execute(
            select(Message)
            .options(*self._message_load_options())
            .where(Message.id == message_id)
            .execution_options(populate_existing=True)
        )
        return result.unique().scalar_one_or_none()

    async def save_message(self, message: Message) -> Message:
        self.session.add(message)
        await self.session.flush()
        return await self.get_message(message.id)  # type: ignore[return-value]

    async def list_messages(
        self,
        *,
        conversation_id: UUID,
        viewer_id: UUID,
        limit: int,
        cursor_created_at: datetime | None = None,
        cursor_id: UUID | None = None,
        since: datetime | None = None,
        since_message_id: UUID | None = None,
    ) -> list[Message]:
        hidden = select(MessageHiddenForUser.message_id).where(
            MessageHiddenForUser.user_id == viewer_id
        )
        stmt: Select = (
            select(Message)
            .options(*self._message_load_options())
            .where(
                Message.conversation_id == conversation_id,
                Message.id.not_in(hidden),
            )
        )

        if since is not None:
            stmt = stmt.where(Message.created_at > since)
        if since_message_id is not None:
            stmt = stmt.where(Message.id != since_message_id)
            # Messages strictly after the given id by created_at ordering:
            anchor = await self.get_message(since_message_id)
            if anchor is not None:
                stmt = stmt.where(
                    or_(
                        Message.created_at > anchor.created_at,
                        and_(
                            Message.created_at == anchor.created_at,
                            Message.id > anchor.id,
                        ),
                    )
                )

        if cursor_created_at is not None and cursor_id is not None:
            # History pagination: older messages (descending).
            stmt = stmt.where(
                or_(
                    Message.created_at < cursor_created_at,
                    and_(
                        Message.created_at == cursor_created_at,
                        Message.id < cursor_id,
                    ),
                )
            )

        if since is not None or since_message_id is not None:
            stmt = stmt.order_by(Message.created_at.asc(), Message.id.asc())
        else:
            stmt = stmt.order_by(Message.created_at.desc(), Message.id.desc())

        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.unique().scalars().all())

    async def get_last_message(
        self, *, conversation_id: UUID, viewer_id: UUID
    ) -> Message | None:
        hidden = select(MessageHiddenForUser.message_id).where(
            MessageHiddenForUser.user_id == viewer_id
        )
        result = await self.session.execute(
            select(Message)
            .options(*self._message_load_options())
            .where(
                Message.conversation_id == conversation_id,
                Message.id.not_in(hidden),
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(1)
        )
        return result.unique().scalar_one_or_none()

    async def count_unread(
        self, *, conversation_id: UUID, user_id: UUID, last_read_at: datetime | None
    ) -> int:
        hidden = select(MessageHiddenForUser.message_id).where(
            MessageHiddenForUser.user_id == user_id
        )
        stmt = select(func.count()).select_from(Message).where(
            Message.conversation_id == conversation_id,
            Message.sender_id != user_id,
            Message.id.not_in(hidden),
            Message.deleted_at.is_(None),
        )
        if last_read_at is not None:
            stmt = stmt.where(Message.created_at > last_read_at)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def soft_delete_for_everyone(self, message: Message) -> Message:
        message.deleted_at = datetime.now(timezone.utc)
        message.body_text = TOMBSTONE_BODY
        return await self.save_message(message)

    async def hide_for_user(self, *, message_id: UUID, user_id: UUID) -> None:
        existing = await self.session.execute(
            select(MessageHiddenForUser).where(
                MessageHiddenForUser.message_id == message_id,
                MessageHiddenForUser.user_id == user_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            return
        self.session.add(
            MessageHiddenForUser(message_id=message_id, user_id=user_id)
        )
        await self.session.flush()

    # ── Reactions ───────────────────────────────────────────────────────

    async def upsert_reaction(
        self, *, message_id: UUID, user_id: UUID, emoji: str
    ) -> MessageReaction:
        result = await self.session.execute(
            select(MessageReaction).where(
                MessageReaction.message_id == message_id,
                MessageReaction.user_id == user_id,
            )
        )
        reaction = result.scalar_one_or_none()
        if reaction is None:
            reaction = MessageReaction(
                message_id=message_id, user_id=user_id, emoji=emoji
            )
            self.session.add(reaction)
        else:
            reaction.emoji = emoji
        await self.session.flush()
        return reaction

    async def delete_reaction(self, *, message_id: UUID, user_id: UUID) -> bool:
        result = await self.session.execute(
            select(MessageReaction).where(
                MessageReaction.message_id == message_id,
                MessageReaction.user_id == user_id,
            )
        )
        reaction = result.scalar_one_or_none()
        if reaction is None:
            return False
        await self.session.delete(reaction)
        await self.session.flush()
        return True

    async def list_reactions(self, message_id: UUID) -> list[MessageReaction]:
        result = await self.session.execute(
            select(MessageReaction).where(MessageReaction.message_id == message_id)
        )
        return list(result.scalars().all())
