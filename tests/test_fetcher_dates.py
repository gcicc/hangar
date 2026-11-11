"""feedparser struct_time values are UTC; parsing must not apply the local offset."""

import time
from datetime import UTC, datetime

from hangar.fetcher import _parse_date


def test_parse_date_treats_struct_time_as_utc():
    parsed = time.strptime("2026-01-15 21:00:00", "%Y-%m-%d %H:%M:%S")
    assert _parse_date({"published_parsed": parsed}) == datetime(2026, 1, 15, 21, 0, tzinfo=UTC)
