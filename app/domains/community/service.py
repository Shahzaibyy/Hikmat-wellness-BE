from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.community.exceptions import (
    AlreadyFollowingError,
    CannotFollowSelfError,
    InvalidCursorError,
    InvalidPostCategoryError,
    NotFollowingError,
    PostNotFoundError,
)
from app.domains.community.models import Post, PostComment
from app.domains.community.repository import CommunityRepository
from app.domains.community.schemas import (
    CommentCreateRequest,
    CommentResponse,
    FeedTab,
    FollowResponse,
    PostAuthorResponse,
    PostCategoryResponse,
    PostCreateRequest,
    PostResponse,
    PostTypeEnum,
)
from app.domains.lookups.models import LookupOption
from app.domains.users.exceptions import UserNotFoundError
from app.domains.users.models import User
from app.domains.users.service import UserService
from app.utils.pagination import CursorPage, build_page, decode_cursor

# Stop-words ignored when matching post category labels to onboarding health interests.
_STOP = frozenset({"and", "the", "of", "a", "an", "&"})


def _tokens(value: str) -> set[str]:
    cleaned = value.lower().replace("&", " ").replace("-", " ").replace("_", " ")
    return {t for t in cleaned.split() if t and t not in _STOP}


def matching_category_ids(
    categories: list[LookupOption],
    health_interests: list[str] | None,
) -> set[UUID]:
    """Prefer categories whose label/key shares meaningful tokens with the user's interests."""
    if not health_interests:
        return set()
    interest_token_sets = [_tokens(item) for item in health_interests]
    matched: set[UUID] = set()
    for cat in categories:
        cat_tokens = _tokens(cat.label) | _tokens(cat.key)
        for interest_tokens in interest_token_sets:
            if cat_tokens & interest_tokens:
                matched.add(cat.id)
                break
    return matched


class CommunityService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = CommunityRepository(session)
        self.users = UserService(session)

    async def create_post(self, author: User, payload: PostCreateRequest) -> PostResponse:
        category = await self.repo.get_category_by_key(payload.category)
        if category is None:
            raise InvalidPostCategoryError(payload.category)

        post = Post(
            author_id=author.id,
            post_type=payload.post_type.value,
            category_id=category.id,
            body_text=payload.body_text.strip(),
            image_url=payload.image_url,
            like_count=0,
            comment_count=0,
        )
        # Attach relationship objects so response mapping works before reload.
        post.category = category
        post.author = author
        created = await self.repo.create_post(post)
        return self._to_post_response(created, liked_by_me=False)

    async def get_post(self, post_id: UUID, viewer: User) -> PostResponse:
        post = await self.repo.get_post_by_id(post_id)
        if post is None:
            raise PostNotFoundError()
        liked = await self.repo.list_liked_post_ids(user_id=viewer.id, post_ids=[post.id])
        return self._to_post_response(post, liked_by_me=post.id in liked)

    async def get_feed(
        self,
        viewer: User,
        *,
        tab: FeedTab,
        cursor: str | None,
        limit: int,
    ) -> CursorPage[PostResponse]:
        cursor_data = self._parse_cursor(cursor) if cursor else None

        if tab == FeedTab.for_you:
            categories = await self.repo.list_post_categories()
            preferred = matching_category_ids(categories, viewer.health_interests)
            posts = await self.repo.list_feed_for_you(
                preferred_category_ids=preferred,
                limit=limit + 1,
                cursor_created_at=self._cursor_dt(cursor_data),
                cursor_id=self._cursor_uuid(cursor_data),
                cursor_match=self._cursor_int(cursor_data, "m"),
            )
            page = build_page(
                posts,
                limit=limit,
                cursor_builder=lambda p: {
                    "tab": tab.value,
                    "m": 1 if p.category_id in preferred else 0,
                    "t": p.created_at.isoformat(),
                    "id": str(p.id),
                },
            )
        elif tab == FeedTab.following:
            posts = await self.repo.list_feed_following(
                follower_id=viewer.id,
                limit=limit + 1,
                cursor_created_at=self._cursor_dt(cursor_data),
                cursor_id=self._cursor_uuid(cursor_data),
            )
            page = build_page(
                posts,
                limit=limit,
                cursor_builder=lambda p: {
                    "tab": tab.value,
                    "t": p.created_at.isoformat(),
                    "id": str(p.id),
                },
            )
        else:
            posts = await self.repo.list_feed_trending(
                since=CommunityRepository.trending_window_start(days=7),
                limit=limit + 1,
                cursor_engagement=self._cursor_int(cursor_data, "e"),
                cursor_created_at=self._cursor_dt(cursor_data),
                cursor_id=self._cursor_uuid(cursor_data),
            )
            page = build_page(
                posts,
                limit=limit,
                cursor_builder=lambda p: {
                    "tab": tab.value,
                    "e": p.like_count + p.comment_count,
                    "t": p.created_at.isoformat(),
                    "id": str(p.id),
                },
            )

        liked_ids = await self.repo.list_liked_post_ids(
            user_id=viewer.id,
            post_ids=[p.id for p in page.items],
        )
        return CursorPage(
            items=[
                self._to_post_response(p, liked_by_me=p.id in liked_ids) for p in page.items
            ],
            next_cursor=page.next_cursor,
            has_more=page.has_more,
        )

    async def like_post(self, post_id: UUID, user: User) -> PostResponse:
        post = await self.repo.get_post_by_id(post_id)
        if post is None:
            raise PostNotFoundError()
        await self.repo.like_post(post_id=post_id, user_id=user.id)
        refreshed = await self.repo.get_post_by_id(post_id)
        assert refreshed is not None
        return self._to_post_response(refreshed, liked_by_me=True)

    async def unlike_post(self, post_id: UUID, user: User) -> PostResponse:
        post = await self.repo.get_post_by_id(post_id)
        if post is None:
            raise PostNotFoundError()
        await self.repo.unlike_post(post_id=post_id, user_id=user.id)
        refreshed = await self.repo.get_post_by_id(post_id)
        assert refreshed is not None
        liked = await self.repo.list_liked_post_ids(user_id=user.id, post_ids=[post_id])
        return self._to_post_response(refreshed, liked_by_me=post_id in liked)

    async def add_comment(
        self, post_id: UUID, author: User, payload: CommentCreateRequest
    ) -> CommentResponse:
        post = await self.repo.get_post_by_id(post_id)
        if post is None:
            raise PostNotFoundError()
        comment = PostComment(
            post_id=post_id,
            author_id=author.id,
            body_text=payload.body_text.strip(),
        )
        comment.author = author
        created = await self.repo.create_comment(comment)
        return self._to_comment_response(created)

    async def list_comments(
        self,
        post_id: UUID,
        *,
        cursor: str | None,
        limit: int,
    ) -> CursorPage[CommentResponse]:
        post = await self.repo.get_post_by_id(post_id)
        if post is None:
            raise PostNotFoundError()

        cursor_data = self._parse_cursor(cursor) if cursor else None
        comments = await self.repo.list_comments(
            post_id=post_id,
            limit=limit + 1,
            cursor_created_at=self._cursor_dt(cursor_data),
            cursor_id=self._cursor_uuid(cursor_data),
        )
        page = build_page(
            comments,
            limit=limit,
            cursor_builder=lambda c: {
                "t": c.created_at.isoformat(),
                "id": str(c.id),
            },
        )
        return CursorPage(
            items=[self._to_comment_response(c) for c in page.items],
            next_cursor=page.next_cursor,
            has_more=page.has_more,
        )

    async def follow_user(self, follower: User, followed_user_id: UUID) -> FollowResponse:
        if follower.id == followed_user_id:
            raise CannotFollowSelfError()
        await self.users.get_by_id(followed_user_id)
        follow = await self.repo.follow(
            follower_id=follower.id, followed_id=followed_user_id
        )
        if follow is None:
            raise AlreadyFollowingError()
        return FollowResponse(
            follower_id=follow.follower_id,
            followed_id=follow.followed_id,
            created_at=follow.created_at,
        )

    async def unfollow_user(self, follower: User, followed_user_id: UUID) -> None:
        if follower.id == followed_user_id:
            raise CannotFollowSelfError()
        # Ensure target exists (consistent 404 for unknown users).
        try:
            await self.users.get_by_id(followed_user_id)
        except UserNotFoundError:
            raise
        removed = await self.repo.unfollow(
            follower_id=follower.id, followed_id=followed_user_id
        )
        if not removed:
            raise NotFollowingError()

    def _to_post_response(self, post: Post, *, liked_by_me: bool) -> PostResponse:
        return PostResponse(
            id=post.id,
            post_type=PostTypeEnum(post.post_type),
            category=PostCategoryResponse(key=post.category.key, label=post.category.label),
            body_text=post.body_text,
            image_url=post.image_url,
            like_count=post.like_count,
            comment_count=post.comment_count,
            liked_by_me=liked_by_me,
            author=PostAuthorResponse(
                id=post.author.id,
                full_name=post.author.full_name,
                avatar_url=post.author.avatar_url,
                is_verified_hakeem=False,
            ),
            created_at=post.created_at,
            updated_at=post.updated_at,
        )

    def _to_comment_response(self, comment: PostComment) -> CommentResponse:
        return CommentResponse(
            id=comment.id,
            post_id=comment.post_id,
            body_text=comment.body_text,
            author=PostAuthorResponse(
                id=comment.author.id,
                full_name=comment.author.full_name,
                avatar_url=comment.author.avatar_url,
                is_verified_hakeem=False,
            ),
            created_at=comment.created_at,
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

    @staticmethod
    def _cursor_int(data: dict | None, key: str) -> int | None:
        if not data or key not in data:
            return None
        try:
            return int(data[key])
        except (TypeError, ValueError) as exc:
            raise InvalidCursorError() from exc
