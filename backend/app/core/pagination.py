"""
Industrial Operations Cloud — Cursor-Based Pagination

Provides consistent pagination across all list endpoints.
Uses cursor-based pagination for stable results with real-time data.
"""

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Standard pagination parameters for list queries."""

    cursor: Optional[str] = Field(None, description="Opaque cursor from previous response")
    limit: int = Field(50, ge=1, le=1000, description="Number of items per page")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response envelope."""

    data: list[Any] = Field(default_factory=list)
    count: int = Field(0, description="Number of items in this page")
    next_cursor: Optional[str] = Field(None, description="Cursor for the next page")
    has_more: bool = Field(False, description="Whether more pages exist")


def build_paginated_response(
    rows: list[dict],
    limit: int,
    cursor_field: str = "created_at",
) -> PaginatedResponse:
    """Build a paginated response from a database result set.

    Args:
        rows: List of row dicts from the database (should fetch limit+1 rows).
        limit: Requested page size.
        cursor_field: The field to use for cursor-based pagination.

    Returns:
        PaginatedResponse with next_cursor set if more data exists.
    """
    has_more = len(rows) > limit
    page_rows = rows[:limit]

    next_cursor = None
    if has_more and page_rows:
        last_row = page_rows[-1]
        cursor_val = last_row.get(cursor_field)
        if cursor_val is not None:
            next_cursor = str(cursor_val)

    return PaginatedResponse(
        data=page_rows,
        count=len(page_rows),
        next_cursor=next_cursor,
        has_more=has_more,
    )
