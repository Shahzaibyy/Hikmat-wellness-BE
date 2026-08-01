"""Cursor-based pagination helpers shared by list endpoints."""

from __future__ import annotations

import base64
import json
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class CursorPage(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None
    has_more: bool = False


class PaginationParams(BaseModel):
    cursor: str | None = None
    limit: int = Field(default=20, ge=1, le=50)


def encode_cursor(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_cursor(cursor: str) -> dict[str, Any]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid cursor.") from exc
    if not isinstance(data, dict):
        raise ValueError("Invalid cursor.")
    return data


def build_page(items: list[T], *, limit: int, cursor_builder) -> CursorPage[T]:
    """Take limit+1 rows; if extra exists, emit next_cursor from the last kept item."""
    has_more = len(items) > limit
    page_items = items[:limit]
    next_cursor = None
    if has_more and page_items:
        next_cursor = encode_cursor(cursor_builder(page_items[-1]))
    return CursorPage(items=page_items, next_cursor=next_cursor, has_more=has_more)
