from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.domains.community.schemas import (
    CommentCreateRequest,
    CommentResponse,
    FeedTab,
    FollowResponse,
    PostCreateRequest,
    PostResponse,
)
from app.domains.community.service import CommunityService
from app.domains.users.models import User
from app.utils.pagination import CursorPage

router = APIRouter(tags=["community"])


def get_community_service(
    session: AsyncSession = Depends(get_db_session),
) -> CommunityService:
    return CommunityService(session)


@router.post("/posts", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    payload: PostCreateRequest,
    current_user: User = Depends(get_current_user),
    service: CommunityService = Depends(get_community_service),
) -> PostResponse:
    return await service.create_post(current_user, payload)


@router.get("/posts/feed", response_model=CursorPage[PostResponse])
async def get_feed(
    tab: FeedTab = Query(default=FeedTab.for_you),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    service: CommunityService = Depends(get_community_service),
) -> CursorPage[PostResponse]:
    return await service.get_feed(current_user, tab=tab, cursor=cursor, limit=limit)


@router.get("/posts/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: UUID,
    current_user: User = Depends(get_current_user),
    service: CommunityService = Depends(get_community_service),
) -> PostResponse:
    return await service.get_post(post_id, current_user)


@router.post("/posts/{post_id}/like", response_model=PostResponse)
async def like_post(
    post_id: UUID,
    current_user: User = Depends(get_current_user),
    service: CommunityService = Depends(get_community_service),
) -> PostResponse:
    return await service.like_post(post_id, current_user)


@router.delete("/posts/{post_id}/like", response_model=PostResponse)
async def unlike_post(
    post_id: UUID,
    current_user: User = Depends(get_current_user),
    service: CommunityService = Depends(get_community_service),
) -> PostResponse:
    return await service.unlike_post(post_id, current_user)


@router.post(
    "/posts/{post_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_comment(
    post_id: UUID,
    payload: CommentCreateRequest,
    current_user: User = Depends(get_current_user),
    service: CommunityService = Depends(get_community_service),
) -> CommentResponse:
    return await service.add_comment(post_id, current_user, payload)


@router.get("/posts/{post_id}/comments", response_model=CursorPage[CommentResponse])
async def list_comments(
    post_id: UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    service: CommunityService = Depends(get_community_service),
) -> CursorPage[CommentResponse]:
    return await service.list_comments(post_id, cursor=cursor, limit=limit)


@router.post(
    "/users/{user_id}/follow",
    response_model=FollowResponse,
    status_code=status.HTTP_201_CREATED,
)
async def follow_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    service: CommunityService = Depends(get_community_service),
) -> FollowResponse:
    return await service.follow_user(current_user, user_id)


@router.delete("/users/{user_id}/follow", status_code=status.HTTP_204_NO_CONTENT)
async def unfollow_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    service: CommunityService = Depends(get_community_service),
) -> Response:
    await service.unfollow_user(current_user, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
