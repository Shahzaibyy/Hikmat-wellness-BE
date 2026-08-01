from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.chat.exceptions import (
    ConversationExistsError,
    ConversationNotFoundError,
    InvalidCursorError,
    InvalidMessagePayloadError,
    MessageForbiddenError,
    MessageNotFoundError,
    MessagingBlockedError,
    NotConversationParticipantError,
)
from app.domains.chat.models import Message, TOMBSTONE_BODY
from app.domains.chat.repository import ChatRepository
from app.domains.chat.schemas import (
    ChatUserPreview,
    ConversationCreateRequest,
    ConversationLastMessage,
    ConversationResponse,
    DeleteScopeEnum,
    MessageEditRequest,
    MessageReactionResponse,
    MessageResponse,
    MessageSendRequest,
    ReplyPreview,
)
from app.domains.users.models import User
from app.domains.users.service import UserService
from app.utils.pagination import CursorPage, build_page, decode_cursor


class ChatService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = ChatRepository(session)
        self.users = UserService(session)
        self._block_checker = None  # wired by ConnectionsService when available

    def set_block_checker(self, checker) -> None:
        """Optional hook: async (user_a, user_b) -> bool if blocked either way."""
        self._block_checker = checker

    async def _ensure_not_blocked(self, user_a: UUID, user_b: UUID) -> None:
        if self._block_checker is None:
            return
        if await self._block_checker(user_a, user_b):
            raise MessagingBlockedError()

    async def create_conversation(
        self, creator: User, payload: ConversationCreateRequest
    ) -> ConversationResponse:
        if creator.id == payload.participant_id:
            raise InvalidMessagePayloadError("Cannot start a conversation with yourself.")
        other = await self.users.get_by_id(payload.participant_id)
        await self._ensure_not_blocked(creator.id, other.id)

        existing = await self.repo.find_direct_conversation(creator.id, other.id)
        if existing is not None:
            raise ConversationExistsError(str(existing.id))

        conversation = await self.repo.create_conversation(
            participant_ids=[creator.id, other.id]
        )
        return await self._to_conversation_response(conversation, viewer=creator)

    async def get_or_create_direct_conversation(
        self, user_a_id: UUID, user_b_id: UUID
    ) -> ConversationResponse:
        """Used by ConnectionsService on accept — no duplicate create."""
        await self._ensure_not_blocked(user_a_id, user_b_id)
        existing = await self.repo.find_direct_conversation(user_a_id, user_b_id)
        if existing is not None:
            viewer = await self.users.get_by_id(user_a_id)
            return await self._to_conversation_response(existing, viewer=viewer)

        conversation = await self.repo.create_conversation(
            participant_ids=[user_a_id, user_b_id]
        )
        viewer = await self.users.get_by_id(user_a_id)
        return await self._to_conversation_response(conversation, viewer=viewer)

    async def list_conversations(self, viewer: User) -> list[ConversationResponse]:
        conversations = await self.repo.list_user_conversations(viewer.id)
        return [
            await self._to_conversation_response(c, viewer=viewer) for c in conversations
        ]

    async def list_messages(
        self,
        viewer: User,
        conversation_id: UUID,
        *,
        cursor: str | None = None,
        limit: int = 20,
        since: datetime | None = None,
        since_message_id: UUID | None = None,
    ) -> CursorPage[MessageResponse]:
        await self._require_participant(conversation_id, viewer.id)

        cursor_data = self._parse_cursor(cursor) if cursor else None
        messages = await self.repo.list_messages(
            conversation_id=conversation_id,
            viewer_id=viewer.id,
            limit=limit + 1,
            cursor_created_at=self._cursor_dt(cursor_data),
            cursor_id=self._cursor_uuid(cursor_data),
            since=since,
            since_message_id=since_message_id,
        )

        # Recovery path (`since`) returns ascending; history uses descending cursor.
        if since is not None or since_message_id is not None:
            page = build_page(
                messages,
                limit=limit,
                cursor_builder=lambda m: {
                    "t": m.created_at.isoformat(),
                    "id": str(m.id),
                },
            )
        else:
            page = build_page(
                messages,
                limit=limit,
                cursor_builder=lambda m: {
                    "t": m.created_at.isoformat(),
                    "id": str(m.id),
                },
            )

        if messages:
            newest = max(messages, key=lambda m: (m.created_at, m.id))
            await self.repo.update_last_read(
                conversation_id=conversation_id,
                user_id=viewer.id,
                read_at=newest.created_at,
            )

        return CursorPage(
            items=[self._to_message_response(m) for m in page.items],
            next_cursor=page.next_cursor,
            has_more=page.has_more,
        )

    async def send_message(
        self,
        sender: User,
        conversation_id: UUID,
        payload: MessageSendRequest,
    ) -> MessageResponse:
        await self._require_participant(conversation_id, sender.id)
        await self._assert_messaging_allowed(conversation_id, sender.id)

        reply_to = None
        if payload.reply_to_message_id is not None:
            reply_to = await self.repo.get_message(payload.reply_to_message_id)
            if reply_to is None or reply_to.conversation_id != conversation_id:
                raise InvalidMessagePayloadError("Invalid reply_to_message_id.")

        message = Message(
            conversation_id=conversation_id,
            sender_id=sender.id,
            body_text=payload.body_text.strip(),
            reply_to_message_id=payload.reply_to_message_id,
        )
        created = await self.repo.create_message(message)
        return self._to_message_response(created)

    async def edit_message(
        self, editor: User, message_id: UUID, payload: MessageEditRequest
    ) -> MessageResponse:
        message = await self.repo.get_message(message_id)
        if message is None or message.deleted_at is not None:
            raise MessageNotFoundError()
        await self._require_participant(message.conversation_id, editor.id)
        if message.sender_id != editor.id:
            raise MessageForbiddenError("Only the sender can edit this message.")
        await self._assert_messaging_allowed(message.conversation_id, editor.id)

        message.body_text = payload.body_text.strip()
        message.edited_at = datetime.now(timezone.utc)
        saved = await self.repo.save_message(message)
        return self._to_message_response(saved)

    async def delete_message(
        self, actor: User, message_id: UUID, scope: DeleteScopeEnum
    ) -> MessageResponse | None:
        message = await self.repo.get_message(message_id)
        if message is None:
            raise MessageNotFoundError()
        await self._require_participant(message.conversation_id, actor.id)

        if scope == DeleteScopeEnum.for_everyone:
            if message.sender_id != actor.id:
                raise MessageForbiddenError(
                    "Only the sender can delete this message for everyone."
                )
            if message.deleted_at is not None:
                return self._to_message_response(message)
            saved = await self.repo.soft_delete_for_everyone(message)
            return self._to_message_response(saved)

        await self.repo.hide_for_user(message_id=message_id, user_id=actor.id)
        return None

    async def react(
        self, user: User, message_id: UUID, emoji: str
    ) -> tuple[MessageResponse, MessageReactionResponse]:
        message = await self.repo.get_message(message_id)
        if message is None or message.deleted_at is not None:
            raise MessageNotFoundError()
        await self._require_participant(message.conversation_id, user.id)
        await self._assert_messaging_allowed(message.conversation_id, user.id)

        await self.repo.upsert_reaction(
            message_id=message_id, user_id=user.id, emoji=emoji
        )
        refreshed = await self.repo.get_message(message_id)
        assert refreshed is not None
        return self._to_message_response(refreshed), MessageReactionResponse(
            user_id=user.id, emoji=emoji, created_at=datetime.now(timezone.utc)
        )

    async def unreact(self, user: User, message_id: UUID) -> MessageResponse:
        message = await self.repo.get_message(message_id)
        if message is None:
            raise MessageNotFoundError()
        await self._require_participant(message.conversation_id, user.id)
        await self.repo.delete_reaction(message_id=message_id, user_id=user.id)
        refreshed = await self.repo.get_message(message_id)
        assert refreshed is not None
        return self._to_message_response(refreshed)

    async def list_user_conversation_ids(self, user_id: UUID) -> list[UUID]:
        return await self.repo.list_conversation_ids_for_user(user_id)

    async def list_participant_ids(self, conversation_id: UUID) -> list[UUID]:
        return await self.repo.list_participant_user_ids(conversation_id)

    async def _assert_messaging_allowed(
        self, conversation_id: UUID, actor_id: UUID
    ) -> None:
        participant_ids = await self.repo.list_participant_user_ids(conversation_id)
        for other_id in participant_ids:
            if other_id != actor_id:
                await self._ensure_not_blocked(actor_id, other_id)

    async def ensure_participant(self, conversation_id: UUID, user_id: UUID) -> None:
        await self._require_participant(conversation_id, user_id)

    async def _require_participant(
        self, conversation_id: UUID, user_id: UUID
    ) -> None:
        conversation = await self.repo.get_conversation(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError()
        participant = await self.repo.get_participant(
            conversation_id=conversation_id, user_id=user_id
        )
        if participant is None:
            raise NotConversationParticipantError()

    async def _to_conversation_response(
        self, conversation, *, viewer: User
    ) -> ConversationResponse:
        participants = [
            ChatUserPreview(
                id=p.user.id,
                full_name=p.user.full_name,
                avatar_url=p.user.avatar_url,
            )
            for p in conversation.participants
        ]
        last = await self.repo.get_last_message(
            conversation_id=conversation.id, viewer_id=viewer.id
        )
        last_message = None
        if last is not None:
            last_message = ConversationLastMessage(
                id=last.id,
                body_text=TOMBSTONE_BODY if last.deleted_at else last.body_text,
                sender_id=last.sender_id,
                created_at=last.created_at,
                is_deleted=last.deleted_at is not None,
            )

        my_participant = next(
            (p for p in conversation.participants if p.user_id == viewer.id), None
        )
        last_read = my_participant.last_read_at if my_participant else None
        unread = await self.repo.count_unread(
            conversation_id=conversation.id,
            user_id=viewer.id,
            last_read_at=last_read,
        )
        return ConversationResponse(
            id=conversation.id,
            participants=participants,
            last_message=last_message,
            unread_count=unread,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )

    def _to_message_response(self, message: Message) -> MessageResponse:
        is_deleted = message.deleted_at is not None
        reply_preview = None
        if message.reply_to is not None:
            rt = message.reply_to
            reply_preview = ReplyPreview(
                id=rt.id,
                sender_id=rt.sender_id,
                body_text=TOMBSTONE_BODY if rt.deleted_at else rt.body_text,
                is_deleted=rt.deleted_at is not None,
            )
        return MessageResponse(
            id=message.id,
            conversation_id=message.conversation_id,
            sender=ChatUserPreview(
                id=message.sender.id,
                full_name=message.sender.full_name,
                avatar_url=message.sender.avatar_url,
            ),
            body_text=TOMBSTONE_BODY if is_deleted else message.body_text,
            reply_to=reply_preview,
            reactions=[
                MessageReactionResponse(
                    user_id=r.user_id, emoji=r.emoji, created_at=r.created_at
                )
                for r in message.reactions
            ],
            is_deleted=is_deleted,
            edited_at=message.edited_at,
            created_at=message.created_at,
            attachment_url=message.attachment_url,
            attachment_type=message.attachment_type,
        )

    @staticmethod
    def _parse_cursor(cursor: str) -> dict:
        try:
            return decode_cursor(cursor)
        except ValueError as exc:
            raise InvalidCursorError() from exc

    @staticmethod
    def _cursor_dt(data: dict | None) -> datetime | None:
        if not data or "t" not in data:
            return None
        try:
            return datetime.fromisoformat(str(data["t"]))
        except ValueError as exc:
            raise InvalidCursorError() from exc

    @staticmethod
    def _cursor_uuid(data: dict | None) -> UUID | None:
        if not data or "id" not in data:
            return None
        try:
            return UUID(str(data["id"]))
        except ValueError as exc:
            raise InvalidCursorError() from exc
