"""Pure DB helper tests (no Postgres required)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from apps.api.db import validate_metrics_window


def test_default_metrics_window() -> None:
    now = datetime(2026, 6, 9, 12, 0, tzinfo=UTC)
    start, end = validate_metrics_window(None, None, max_days=7, now=now)
    assert end == now
    assert start == now - timedelta(days=1)


def test_partial_range_rejected() -> None:
    now = datetime(2026, 6, 9, 12, 0, tzinfo=UTC)
    with pytest.raises(ValueError, match="Both from and to"):
        validate_metrics_window(now, None, max_days=7, now=now)


def test_range_too_large() -> None:
    now = datetime(2026, 6, 9, 12, 0, tzinfo=UTC)
    start = now - timedelta(days=30)
    with pytest.raises(ValueError, match="maximum"):
        validate_metrics_window(start, now, max_days=7, now=now)
