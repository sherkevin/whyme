"""Pagination helpers for PRD10 API responses."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Pagination:
    """PRD10 pagination metadata."""

    page: int
    page_size: int
    total: int
    has_more: bool

    def to_dict(self) -> dict[str, int | bool]:
        return {
            "page": self.page,
            "page_size": self.page_size,
            "total": self.total,
            "has_more": self.has_more,
        }


def build_pagination(page: int, page_size: int, total: int) -> Pagination:
    """Build validated pagination metadata."""
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")
    if total < 0:
        raise ValueError("total must be >= 0")

    consumed = page * page_size
    return Pagination(
        page=page,
        page_size=page_size,
        total=total,
        has_more=consumed < total,
    )

