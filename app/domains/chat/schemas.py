from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DeleteScopeEnum(str, Enum):
    for_me = "for_me"
    for_everyone = "for_everyone"


class ConversationCreateRequest(BaseModel):
    """Start a 1:1 conversation with another user."""

    participant_id: UUID


class MessageSendRequest(BaseModel):
    body_text: str = Field(min_length=1, max_length=5000)
    reply_to_message_id: UUID | None = None


class MessageEditRequest(BaseModel):
    body_text: str = Field(min_length=1, max_length=5000)


class MessageDeleteRequest(BaseModel):
    scope: DeleteScopeEnum


class MessageReactRequest(BaseModel):
    emoji: str = Field(min_length=1, max_length=32)


class ChatUserPreview(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str | None = None
    avatar_url: str | None = None


class MessageReactionResponse(BaseModel):
    user_id: UUID
    emoji: str
    created_at: datetime


class ReplyPreview(BaseModel):
    id: UUID
    sender_id: UUID
    body_text: str
    is_deleted: bool = False


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    sender: ChatUserPreview
    body_text: str
    reply_to: ReplyPreview | None = None
    reactions: list[MessageReactionResponse] = []
    is_deleted: bool = False
    edited_at: datetime | None = None
    created_at: datetime
    # Present but always null until attachments pass.
    attachment_url: str | None = None
    attachment_type: str | None = None


class ConversationLastMessage(BaseModel):
    id: UUID
    body_text: str
    sender_id: UUID
    created_at: datetime
    is_deleted: bool = False


class ConversationResponse(BaseModel):
    id: UUID
    participants: list[ChatUserPreview]
    last_message: ConversationLastMessage | None = None
    unread_count: int = 0
    created_at: datetime
    updated_at: datetime


class ReactionUpdatedEvent(BaseModel):
    message_id: UUID
    conversation_id: UUID
    user_id: UUID
    emoji: str | None
    reactions: list[MessageReactionResponse]
