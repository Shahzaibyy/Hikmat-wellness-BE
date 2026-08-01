from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ConnectionStatusEnum(str, Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"
    cancelled = "cancelled"


class ConnectionRequestCreate(BaseModel):
    recipient_id: UUID


class BlockCreateRequest(BaseModel):
    user_id: UUID


class ConnectionUserPreview(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str | None = None
    avatar_url: str | None = None


class ConnectionResponse(BaseModel):
    id: UUID
    requester: ConnectionUserPreview
    recipient: ConnectionUserPreview
    status: ConnectionStatusEnum
    created_at: datetime
    responded_at: datetime | None = None
    conversation_id: UUID | None = None


class BlockResponse(BaseModel):
    blocker_id: UUID
    blocked_id: UUID
    blocked_user: ConnectionUserPreview
    created_at: datetime


class RelationshipStatus(str, Enum):
    """For Discover / profile badges — no extra round-trip."""

    none = "none"
    pending_outgoing = "pending_outgoing"
    pending_incoming = "pending_incoming"
    connected = "connected"
    blocked = "blocked"
    blocked_by_them = "blocked_by_them"


class RelationshipStatusResponse(BaseModel):
    user_id: UUID
    status: RelationshipStatus
    connection_id: UUID | None = None
