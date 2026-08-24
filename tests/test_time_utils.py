"""Tests for the shared UTC time helper."""

from __future__ import annotations

from datetime import UTC, timedelta

from utils import utc_now


def test_utc_now_is_timezone_aware_utc() -> None:
    now = utc_now()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)
    assert now.tzinfo == UTC
