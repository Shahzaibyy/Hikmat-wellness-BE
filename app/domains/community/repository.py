from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import Select, and_, case, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.domains.community.models import Follow, Post, PostComment, PostLike
from app.domains.lookups.models import LookupOption


class CommunityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── Posts ───────────────────────────────────────────────────────────

    async def create_post(self, post: Post) -> Post:
        self.session.add(post)
        await self.session.flush()
        await self.session.refresh(post, attribute_names=["author", "category"])
        return post

    async def get_post_by_id(self, post_id: UUID) -> Post | None:
        result = await self.session.execute(
            select(Post)
            .options(joinedload(Post.author), joinedload(Post.category))
            .where(Post.id == post_id)
        )
        return result.unique().scalar_one_or_none()

    async def list_feed_for_you(
        self,
        *,
        preferred_category_ids: set[UUID],
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: UUID | None,
        cursor_match: int | None,
    ) -> list[Post]:
        if preferred_category_ids:
            match_score = case(
                (Post.category_id.in_(preferred_category_ids), 1),
                else_=0,
            ).label("match_score")
        else:
            match_score = case((False, 1), else_=0).label("match_score")

        stmt = (
            select(Post, match_score)
            .options(joinedload(Post.author), joinedload(Post.category))
            .order_by(match_score.desc(), Post.created_at.desc(), Post.id.desc())
            .limit(limit)
        )

        if cursor_created_at is not None and cursor_id is not None and cursor_match is not None:
            stmt = stmt.where(
                or_(
                    match_score < cursor_match,
                    and_(
                        match_score == cursor_match,
                        Post.created_at < cursor_created_at,
                    ),
                    and_(
                        match_score == cursor_match,
                        Post.created_at == cursor_created_at,
                        Post.id < cursor_id,
                    ),
                )
            )

        result = await self.session.execute(stmt)
        return [row[0] for row in result.unique().all()]

    async def list_feed_following(
        self,
        *,
        follower_id: UUID,
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: UUID | None,
    ) -> list[Post]:
        stmt = (
            select(Post)
            .options(joinedload(Post.author), joinedload(Post.category))
            .join(Follow, Follow.followed_id == Post.author_id)
            .where(Follow.follower_id == follower_id)
            .order_by(Post.created_at.desc(), Post.id.desc())
            .limit(limit)
        )
        stmt = self._apply_created_cursor(stmt, cursor_created_at, cursor_id)
        result = await self.session.execute(stmt)
        return list(result.unique().scalars().all())

    async def list_feed_trending(
        self,
        *,
        since: datetime,
        limit: int,
        cursor_engagement: int | None,
        cursor_created_at: datetime | None,
        cursor_id: UUID | None,
    ) -> list[Post]:
        engagement = (Post.like_count + Post.comment_count).label("engagement")
        stmt = (
            select(Post, engagement)
            .options(joinedload(Post.author), joinedload(Post.category))
            .where(Post.created_at >= since)
            .order_by(engagement.desc(), Post.created_at.desc(), Post.id.desc())
            .limit(limit)
        )
        if (
            cursor_engagement is not None
            and cursor_created_at is not None
            and cursor_id is not None
        ):
            stmt = stmt.where(
                or_(
                    engagement < cursor_engagement,
                    and_(
                        engagement == cursor_engagement,
                        Post.created_at < cursor_created_at,
                    ),
                    and_(
                        engagement == cursor_engagement,
                        Post.created_at == cursor_created_at,
                        Post.id < cursor_id,
                    ),
                )
            )
        result = await self.session.execute(stmt)
        return [row[0] for row in result.unique().all()]

    @staticmethod
    def _apply_created_cursor(
        stmt: Select,
        cursor_created_at: datetime | None,
        cursor_id: UUID | None,
    ) -> Select:
        if cursor_created_at is None or cursor_id is None:
            return stmt
        return stmt.where(
            or_(
                Post.created_at < cursor_created_at,
                and_(Post.created_at == cursor_created_at, Post.id < cursor_id),
            )
        )

    # ── Likes ───────────────────────────────────────────────────────────

    async def like_post(self, *, post_id: UUID, user_id: UUID) -> bool:
        """Insert like if missing; atomically bump counter. Returns True if newly liked."""
        stmt = (
            insert(PostLike)
            .values(post_id=post_id, user_id=user_id)
            .on_conflict_do_nothing(constraint="uq_post_likes_post_user")
            .returning(PostLike.post_id)
        )
        result = await self.session.execute(stmt)
        inserted = result.scalar_one_or_none()
        if inserted is None:
            return False
        await self.session.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(like_count=Post.like_count + 1, updated_at=func.now())
        )
        return True

    async def unlike_post(self, *, post_id: UUID, user_id: UUID) -> bool:
        """Delete like if present; atomically decrement counter (floor 0)."""
        result = await self.session.execute(
            select(PostLike).where(
                PostLike.post_id == post_id,
                PostLike.user_id == user_id,
            )
        )
        like = result.scalar_one_or_none()
        if like is None:
            return False
        await self.session.delete(like)
        await self.session.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(
                like_count=func.greatest(Post.like_count - 1, 0),
                updated_at=func.now(),
            )
        )
        return True

    async def list_liked_post_ids(
        self, *, user_id: UUID, post_ids: list[UUID]
    ) -> set[UUID]:
        if not post_ids:
            return set()
        result = await self.session.execute(
            select(PostLike.post_id).where(
                PostLike.user_id == user_id,
                PostLike.post_id.in_(post_ids),
            )
        )
        return set(result.scalars().all())

    # ── Comments ────────────────────────────────────────────────────────

    async def create_comment(self, comment: PostComment) -> PostComment:
        self.session.add(comment)
        await self.session.flush()
        await self.session.execute(
            update(Post)
            .where(Post.id == comment.post_id)
            .values(comment_count=Post.comment_count + 1, updated_at=func.now())
        )
        await self.session.refresh(comment, attribute_names=["author"])
        return comment

    async def list_comments(
        self,
        *,
        post_id: UUID,
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: UUID | None,
    ) -> list[PostComment]:
        stmt = (
            select(PostComment)
            .options(joinedload(PostComment.author))
            .where(PostComment.post_id == post_id)
            .order_by(PostComment.created_at.desc(), PostComment.id.desc())
            .limit(limit)
        )
        if cursor_created_at is not None and cursor_id is not None:
            stmt = stmt.where(
                or_(
                    PostComment.created_at < cursor_created_at,
                    and_(
                        PostComment.created_at == cursor_created_at,
                        PostComment.id < cursor_id,
                    ),
                )
            )
        result = await self.session.execute(stmt)
        return list(result.unique().scalars().all())

    # ── Follows ─────────────────────────────────────────────────────────

    async def follow(self, *, follower_id: UUID, followed_id: UUID) -> Follow | None:
        stmt = (
            insert(Follow)
            .values(follower_id=follower_id, followed_id=followed_id)
            .on_conflict_do_nothing(constraint="uq_follows_follower_followed")
            .returning(Follow.follower_id, Follow.followed_id, Follow.created_at)
        )
        result = await self.session.execute(stmt)
        row = result.one_or_none()
        if row is None:
            return None
        return Follow(
            follower_id=row.follower_id,
            followed_id=row.followed_id,
            created_at=row.created_at,
        )

    async def unfollow(self, *, follower_id: UUID, followed_id: UUID) -> bool:
        result = await self.session.execute(
            select(Follow).where(
                Follow.follower_id == follower_id,
                Follow.followed_id == followed_id,
            )
        )
        follow = result.scalar_one_or_none()
        if follow is None:
            return False
        await self.session.delete(follow)
        return True

    async def get_category_by_key(self, key: str) -> LookupOption | None:
        result = await self.session.execute(
            select(LookupOption).where(
                LookupOption.type == "post_category",
                LookupOption.key == key,
                LookupOption.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def list_post_categories(self) -> list[LookupOption]:
        result = await self.session.execute(
            select(LookupOption)
            .where(
                LookupOption.type == "post_category",
                LookupOption.is_active.is_(True),
            )
            .order_by(LookupOption.sort_order.asc(), LookupOption.label.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    def trending_window_start(*, days: int = 7) -> datetime:
        return datetime.now(timezone.utc) - timedelta(days=days)
