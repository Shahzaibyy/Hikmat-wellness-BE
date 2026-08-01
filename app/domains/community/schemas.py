from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PostTypeEnum(str, Enum):
    tip = "tip"
    question = "question"


class FeedTab(str, Enum):
    for_you = "for_you"
    following = "following"
    trending = "trending"


class PostCreateRequest(BaseModel):
    post_type: PostTypeEnum
    category: str = Field(min_length=1, max_length=120)
    body_text: str = Field(min_length=1, max_length=5000)
    image_url: str | None = Field(default=None, max_length=500)


class CommentCreateRequest(BaseModel):
    body_text: str = Field(min_length=1, max_length=2000)


class PostAuthorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str | None = None
    avatar_url: str | None = None
    # Hakeem verification lives in the hakeem domain (not built yet) — always false for now.
    is_verified_hakeem: bool = False


class PostCategoryResponse(BaseModel):
    key: str
    label: str


class PostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    post_type: PostTypeEnum
    category: PostCategoryResponse
    body_text: str
    image_url: str | None = None
    like_count: int
    comment_count: int
    liked_by_me: bool = False
    author: PostAuthorResponse
    created_at: datetime
    updated_at: datetime


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    post_id: UUID
    body_text: str
    author: PostAuthorResponse
    created_at: datetime


class FollowResponse(BaseModel):
    follower_id: UUID
    followed_id: UUID
    created_at: datetime
