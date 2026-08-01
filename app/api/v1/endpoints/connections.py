from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.domains.connections.schemas import (
    BlockCreateRequest,
    BlockResponse,
    ConnectionRequestCreate,
    ConnectionResponse,
    ConnectionStatusEnum,
    RelationshipStatusResponse,
)
from app.domains.connections.service import ConnectionsService
from app.domains.users.models import User

router = APIRouter(prefix="/connections", tags=["connections"])


def get_connections_service(
    session: AsyncSession = Depends(get_db_session),
) -> ConnectionsService:
    return ConnectionsService(session)


@router.post(
    "/request",
    response_model=ConnectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def request_connection(
    payload: ConnectionRequestCreate,
    current_user: User = Depends(get_current_user),
    service: ConnectionsService = Depends(get_connections_service),
) -> ConnectionResponse:
    return await service.request_connection(current_user, payload)


@router.get("", response_model=list[ConnectionResponse])
async def list_connections(
    status_filter: ConnectionStatusEnum | None = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    service: ConnectionsService = Depends(get_connections_service),
) -> list[ConnectionResponse]:
    return await service.list_connections(current_user, status=status_filter)


@router.post("/block", response_model=BlockResponse, status_code=status.HTTP_201_CREATED)
async def block_user(
    payload: BlockCreateRequest,
    current_user: User = Depends(get_current_user),
    service: ConnectionsService = Depends(get_connections_service),
) -> BlockResponse:
    return await service.block(current_user, payload)


@router.get("/blocked", response_model=list[BlockResponse])
async def list_blocked(
    current_user: User = Depends(get_current_user),
    service: ConnectionsService = Depends(get_connections_service),
) -> list[BlockResponse]:
    return await service.list_blocked(current_user)


@router.delete("/block/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unblock_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    service: ConnectionsService = Depends(get_connections_service),
) -> Response:
    await service.unblock(current_user, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/relationship/{user_id}", response_model=RelationshipStatusResponse)
async def get_relationship_status(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    service: ConnectionsService = Depends(get_connections_service),
) -> RelationshipStatusResponse:
    """Discover badge helper: none | pending_* | connected | blocked*."""
    return await service.get_relationship_status(current_user, user_id)


@router.post("/{connection_id}/accept", response_model=ConnectionResponse)
async def accept_connection(
    connection_id: UUID,
    current_user: User = Depends(get_current_user),
    service: ConnectionsService = Depends(get_connections_service),
) -> ConnectionResponse:
    return await service.accept(current_user, connection_id)


@router.post("/{connection_id}/reject", response_model=ConnectionResponse)
async def reject_connection(
    connection_id: UUID,
    current_user: User = Depends(get_current_user),
    service: ConnectionsService = Depends(get_connections_service),
) -> ConnectionResponse:
    return await service.reject(current_user, connection_id)


@router.post("/{connection_id}/cancel", response_model=ConnectionResponse)
async def cancel_connection(
    connection_id: UUID,
    current_user: User = Depends(get_current_user),
    service: ConnectionsService = Depends(get_connections_service),
) -> ConnectionResponse:
    return await service.cancel(current_user, connection_id)
