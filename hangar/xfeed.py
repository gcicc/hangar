"""X (Twitter) posts as a *primary* source for the commitments board.

Musk states most targets on X before any outlet reports them, so a claim
sourced from the post itself outranks the same claim sourced from coverage of
the post. This module is what lets the board mark that difference.

**This module never fetches anything.** X requires a real browser - the
logged-out profile view is JavaScript-rendered and the API's useful read tiers
are paid - and the refresh job runs in GitHub Actions, where spinning up
Chromium on every run would be slow and fragile. So collection is decoupled:

* An optional local collector (Windows Task Scheduler, the same split already
  used by GCourses and gfinance2) writes ``data/x_posts.json``.
* This module reads that file if it exists, and reports its age.

When the file is missing or stale the board still works - it falls back to
claims sourced from news coverage and says so on the page. A silent downgrade
from primary to second-hand sourcing would be worse than an absent panel.

Known limits of the logged-out view, which the page states rather than hides:
only the most recent handful of posts are visible, timestamps are relative
("1h", "Sep 3") and are resolved against the collector's own clock, and
permalinks are not recoverable from the text rendering.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
X_FILE = DATA_DIR / "x_posts.json"

# Beyond this the panel is labelled stale rather than presented as current.
STALE_AFTER = timedelta(hours=12)

_REL = re.compile(r"^(\d+)\s*([smhd])$", re.IGNORECASE)


def resolve_relative(stamp: str, observed_at: datetime) -> str | None:
    """Resolve X's relative timestamps against the moment they were observed.

    ``"1h"`` means one hour before *collection*, not before render, so this is
    computed once at ingest and stored, never recomputed later.
    """
    stamp = (stamp or "").strip()
    m = _REL.match(stamp)
    if m:
        n, unit = int(m.group(1)), m.group(2).lower()
        delta = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}[unit]
        return (observed_at - timedelta(**{delta: n})).isoformat(timespec="seconds")
    # Absolute month-day form, e.g. "Sep 3" - year is implied by the observation.
    try:
        parsed = datetime.strptime(stamp, "%b %d").replace(year=observed_at.year, tzinfo=UTC)
        if parsed > observed_at + timedelta(days=1):
            parsed = parsed.replace(year=observed_at.year - 1)
        return parsed.isoformat(timespec="seconds")
    except ValueError:
        return None


def load() -> dict:
    """Read the collected posts. Absence is a reported state, not an error."""
    if not X_FILE.exists():
        return {
            "available": False,
            "reason": "no collection yet - run the local X collector",
            "posts": [],
        }
    try:
        payload = json.loads(X_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return {"available": False, "reason": f"unreadable: {e}", "posts": []}

    collected = payload.get("collected_at")
    age_note = None
    stale = False
    if collected:
        try:
            then = datetime.fromisoformat(collected)
            age = datetime.now(UTC) - then
            stale = age > STALE_AFTER
            hours = int(age.total_seconds() // 3600)
            age_note = f"{hours}h ago" if hours else "under an hour ago"
        except ValueError:
            pass

    return {
        "available": True,
        "stale": stale,
        "collected_at": collected,
        "age": age_note,
        "handle": payload.get("handle", "elonmusk"),
        "posts": payload.get("posts", []),
        "note": payload.get("note"),
    }


def as_entries(feed: dict) -> list[dict]:
    """Shape X posts like news entries so the claim detector can read them.

    The detector takes ``title``/``link``/``source``; posts are mapped onto that
    shape with ``source`` set to the handle, which is what marks the resulting
    claim as primary-sourced downstream.
    """
    entries = []
    for post in feed.get("posts", []):
        text = (post.get("text") or "").strip()
        if not text:
            continue
        entries.append(
            {
                "title": text,
                "link": post.get("link") or f"https://x.com/{feed.get('handle', 'elonmusk')}",
                "source": f"@{feed.get('handle', 'elonmusk')}",
                "published": post.get("posted_at") or feed.get("collected_at"),
                "summary": "",
                "primary": True,
            }
        )
    return entries
