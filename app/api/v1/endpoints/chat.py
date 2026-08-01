from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.domains.chat.schemas import (
    ConversationCreateRequest,
    ConversationResponse,
    MessageDeleteRequest,
    MessageEditRequest,
    MessageReactRequest,
    MessageResponse,
    MessageSendRequest,
)
from app.domains.chat.service import ChatService
from app.domains.users.models import User
from app.utils.pagination import CursorPage

router = APIRouter(prefix="/conversations", tags=["chat"])


def get_chat_service(session: AsyncSession = Depends(get_db_session)) -> ChatService:
    service = ChatService(session)
    from app.domains.connections.service import ConnectionsService

    service.set_block_checker(ConnectionsService(session).is_blocked_either_way)
    return service


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> list[ConversationResponse]:
    return await service.list_conversations(current_user)


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreateRequest,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> ConversationResponse:
    return await service.create_conversation(current_user, payload)


@router.get("/{conversation_id}/messages", response_model=CursorPage[MessageResponse])
async def list_messages(
    conversation_id: UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    since: datetime | None = Query(
        default=None,
        description="Recovery: return messages created after this timestamp (ASC).",
    ),
    since_message_id: UUID | None = Query(
        default=None,
        description="Recovery: return messages after this message id (ASC).",
    ),
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> CursorPage[MessageResponse]:
    return await service.list_messages(
        current_user,
        conversation_id,
        cursor=cursor,
        limit=limit,
        since=since,
        since_message_id=since_message_id,
    )


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    conversation_id: UUID,
    payload: MessageSendRequest,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> MessageResponse:
    """REST fallback for sending (socket is the preferred real-time path)."""
    return await service.send_message(current_user, conversation_id, payload)


@router.patch("/messages/{message_id}", response_model=MessageResponse)
async def edit_message(
    message_id: UUID,
    payload: MessageEditRequest,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> MessageResponse:
    return await service.edit_message(current_user, message_id, payload)


@router.post("/messages/{message_id}/delete", response_model=MessageResponse | None)
async def delete_message(
    message_id: UUID,
    payload: MessageDeleteRequest,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> MessageResponse | Response:
    result = await service.delete_message(current_user, message_id, payload.scope)
    if result is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return result


@router.post("/messages/{message_id}/reactions", response_model=MessageResponse)
async def react_to_message(
    message_id: UUID,
    payload: MessageReactRequest,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> MessageResponse:
    message, _ = await service.react(current_user, message_id, payload.emoji)
    return message


@router.delete("/messages/{message_id}/reactions", response_model=MessageResponse)
async def unreact_to_message(
    message_id: UUID,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> MessageResponse:
    return await service.unreact(current_user, message_id)
