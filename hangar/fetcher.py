"""RSS fetching, normalization, dedupe, and recency selection.

Ported near-verbatim from clintrialist-report's ``pharma_report/fetcher.py``,
which is itself GRUDGE's feed layer with the drama scoring removed. Two changes:
the dedupe key now strips the trailing " - Publisher" suffix Google News appends
(lifted from GRUDGE's ``run.py``), and dedupe accepts a shared ``seen`` set so a
story cannot appear in two sections of the page.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

import feedparser

USER_AGENT = "HANGAR/0.1 (+https://github.com/gcicc/hangar)"

# Trailing " - Publisher" / " | Publisher" suffix, Google News style.
_PUBLISHER_SUFFIX = re.compile(r"\s+[-\u2013\u2014|]\s+[^-\u2013\u2014|]{1,40}$")


def _parse_date(entry: dict) -> datetime:
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            try:
                from time import mktime

                return datetime.fromtimestamp(mktime(parsed), tz=UTC)
            except (ValueError, OverflowError, OSError):
                pass
    return datetime.now(UTC)


def _normalize_entry(entry: dict, source: str) -> dict | None:
    title = entry.get("title", "").strip()
    link = entry.get("link", "").strip()
    if not title or not link:
        return None
    return {
        "title": title,
        "link": link,
        "published": _parse_date(entry),
        "source": source,
        "summary": entry.get("summary", ""),
    }


def fetch_feed(name: str, url: str) -> list[dict]:
    """Fetch and normalize one RSS feed. Logs an OK/SKIP/FAIL line.

    Several publishers (nasaspaceflight.com among them) return 403 to a bare
    request, so a real User-Agent is always sent.
    """
    try:
        feed = feedparser.parse(url, request_headers={"User-Agent": USER_AGENT})
        if feed.bozo and not feed.entries:
            print(f"  [SKIP] {name}: feed error")
            return []
        results = []
        for entry in feed.entries:
            normalized = _normalize_entry(entry, name)
            if normalized:
                results.append(normalized)
        print(f"  [OK]   {name}: {len(results)} items")
        return results
    except Exception as e:  # noqa: BLE001 - one bad feed must not stop the run
        print(f"  [FAIL] {name}: {e}")
        return []


def dedupe_key(title: str) -> str:
    """Normalize a headline so near-duplicates collapse to one key."""
    key = title.lower().strip()
    key = _PUBLISHER_SUFFIX.sub("", key)
    key = re.sub(r"[^a-z0-9]+", " ", key).strip()
    return key


def dedupe(entries: list[dict], seen: set[str] | None = None) -> list[dict]:
    """Drop duplicate titles, keeping the first occurrence.

    Pass a shared ``seen`` set across sections so one story cannot appear twice
    on the page.
    """
    if seen is None:
        seen = set()
    unique: list[dict] = []
    for e in entries:
        key = dedupe_key(e["title"])
        if key and key not in seen:
            seen.add(key)
            unique.append(e)
    return unique


def filter_by_title(entries: list[dict], exclude_substrings: list[str]) -> list[dict]:
    """Drop entries whose titles contain any banned substring (case-insensitive)."""
    bans = [s.lower() for s in exclude_substrings]
    return [e for e in entries if not any(b in e["title"].lower() for b in bans)]


def require_relevance(entries: list[dict], pattern: str) -> list[dict]:
    """Keep only entries that actually name one of the tracked companies.

    The trade feeds cover their whole sector. Without this the page fills with
    accurate, well-sourced stories about BYD and Uber, which belong on a
    different page.
    """
    rx = re.compile(pattern, re.IGNORECASE)
    return [e for e in entries if rx.search(f"{e.get('title', '')} {e.get('summary', '')}")]


def latest_n(entries: list[dict], n: int) -> list[dict]:
    """Sort by publish date descending, return the first n."""
    entries.sort(key=lambda e: e["published"], reverse=True)
    return entries[:n]
