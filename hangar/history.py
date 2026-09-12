"""Append-only observation ledger: the unbiased growth series.

Most "growth over time" on this page is *reconstructed* - constellation size
from launch dates, revenue from filed quarters. Reconstruction is fine when the
source genuinely holds history, but several metrics have none: nobody publishes
"Starlink satellites in orbit" as a time series, so the only honest way to get
that curve is to start measuring and keep the measurements.

That is what this file is. Each run records the metrics it observed, one point
per metric per day, and never rewrites a past observation. After a few weeks it
produces a directly measured series that needs no reconstruction and carries no
survivorship bias.

Two rules make it trustworthy:

* **One observation per metric per day.** Re-running six times in an afternoon
  must not create six points and imply six measurements.
* **Past points are never rewritten.** If a source revises its numbers, that is
  a new observation at today's date, not a silent edit of last month's.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HISTORY_FILE = DATA_DIR / "history.json"

# Metrics worth a permanent record. Anything not listed is transient and is not
# accumulated - the ledger stays small and every series in it is deliberate.
TRACKED_METRICS = {
    "starlink_in_orbit": "Starlink satellites in orbit",
    "spacex_launches_12mo": "SpaceX launches, trailing 12 months",
    "spacex_launches_per_month": "SpaceX launches per month, trailing average",
    "people_in_space": "People in space",
    "supercharger_sites": "Supercharger sites open",
    "supercharger_stalls": "Supercharger stalls",
}

# Keep the ledger bounded at roughly five years of daily points per metric.
MAX_POINTS = 1900


def _load_raw() -> dict:
    if not HISTORY_FILE.exists():
        return {"series": {}}
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"  [WARN] history unreadable, starting fresh: {e}")
        return {"series": {}}


def record_and_load(metrics: dict) -> dict:
    """Record today's observations and return the full ledger.

    Returns the ledger even when nothing new was recorded, so the page always
    renders whatever history exists.
    """
    ledger = _load_raw()
    series = ledger.setdefault("series", {})
    today = datetime.now(UTC).date().isoformat()
    added = 0

    for key, label in TRACKED_METRICS.items():
        value = metrics.get(key)
        if value is None:
            continue
        entry = series.setdefault(key, {"label": label, "points": []})
        entry["label"] = label
        points = entry["points"]
        if points and points[-1]["d"] == today:
            # Same day: keep the first observation, do not overwrite it.
            continue
        points.append({"d": today, "v": value})
        del points[:-MAX_POINTS]
        added += 1

    ledger["updated"] = datetime.now(UTC).isoformat(timespec="seconds")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(ledger, indent=1), encoding="utf-8")

    span = {
        key: {
            "label": entry["label"],
            "points": entry["points"],
            "n": len(entry["points"]),
            "first": entry["points"][0]["d"] if entry["points"] else None,
            "delta": (
                entry["points"][-1]["v"] - entry["points"][0]["v"]
                if len(entry["points"]) > 1
                else None
            ),
        }
        for key, entry in series.items()
    }
    if added:
        print(f"  [OK]   history: recorded {added} observation(s) for {today}")
    return {
        "series": span,
        "updated": ledger["updated"],
        "note": (
            "Directly measured series. Starts the day HANGAR first ran, so a "
            "short history means a new ledger, not a flat metric."
        ),
    }
