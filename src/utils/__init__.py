"""Shared utility helpers."""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime.

    All timestamps in this codebase (database records, deadlines, retention
    calculations) are UTC. SQLite stores datetimes without the offset, so
    values read back from the database are naive but always represent UTC.
    """
    return datetime.now(tz=UTC)
