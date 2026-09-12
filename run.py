"""HANGAR entry point.

    python run.py             # refresh what has gone stale, then render
    python run.py --force     # refresh everything regardless of cache age
    python run.py --render    # render from cache only, no network at all

The refresh is *periodic, not continuous*: every source declares a max_age in
``hangar/cache.py`` and a run only goes to the network for sources that have
expired. That keeps HANGAR inside Launch Library's 15-requests-per-hour free
tier, and means the page still builds with no network at all.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from hangar import cache, constellation, financials, history, launches, sites, targets, xfeed
from hangar.feeds import (
    EXCLUDE_TITLES,
    FEEDS_BY_SECTION,
    RELEVANCE,
    SECTION_LIMITS,
    SECTION_ORDER,
    SECTIONS,
)
from hangar.fetcher import dedupe, fetch_feed, filter_by_title, require_relevance
from hangar.render import render
from hangar.scorer import drop_stale, rank
from hangar.topics import tag_entry

ROOT = Path(__file__).resolve().parent


def fetch_news() -> dict:
    """Fetch every section's feeds, dedupe across sections, rank and tag.

    The ``seen`` set is shared across sections in SECTION_ORDER so a story that
    could land in two places stays in the more specific one - a Starship story
    belongs under SpaceX, not under Markets.

    The claim detector reads the *whole* deduped corpus, not just the stories
    ranked high enough to display - a commitment is worth catching even in a
    story that did not make the page. The corpus is then discarded rather than
    cached: it is working data, and persisting it put 1.2 MB into a file this
    repo commits twelve times a day.
    """
    seen: set[str] = set()
    sections: dict[str, list[dict]] = {}
    corpus: list[dict] = []

    for section in SECTION_ORDER:
        print(f"\n--- {SECTIONS[section]} ---")
        raw: list[dict] = []
        for feed in FEEDS_BY_SECTION[section]:
            raw.extend(fetch_feed(feed["name"], feed["url"]))

        unique = filter_by_title(dedupe(raw, seen), EXCLUDE_TITLES)
        unique = require_relevance(unique, RELEVANCE)
        for entry in unique:
            tag_entry(entry)
        corpus.extend(unique)

        # The age cap is applied to what is *displayed*, not to what is kept:
        # the claim detector should still see an older commitment, and the
        # corpus feeds it.
        fresh = drop_stale(list(unique))
        chosen = rank(fresh, SECTION_LIMITS[section])
        sections[section] = chosen
        print(
            f"  --> {len(raw)} raw -> {len(unique)} relevant -> "
            f"{len(fresh)} recent -> {len(chosen)} shown"
        )

    # Claim detection belongs here, not at render time, for two reasons. It is
    # part of *ingesting* news; and merge_claims bumps a "times seen" counter,
    # so re-running it on every render would inflate that counter without any
    # new reporting having happened.
    x = xfeed.load()
    detected = targets.detect_claims(xfeed.as_entries(x) + corpus)
    for claim in detected:
        claim["primary"] = str(claim.get("source", "")).startswith("@")
    targets.merge_claims(detected)
    print(f"\n  [OK]   claims: {len(detected)} detected from {len(corpus)} headlines")

    for entry in corpus:
        if isinstance(entry.get("published"), datetime):
            entry["published"] = entry["published"].isoformat()

    # The corpus and the raw summaries are working data, not page data. Caching
    # them put 1.2 MB into a file this repo commits twelve times a day; the page
    # never reads either.
    for section_items in sections.values():
        for entry in section_items:
            entry.pop("summary", None)

    return {
        "sections": sections,
        "labels": SECTIONS,
        "order": SECTION_ORDER,
        "corpus_size": len(corpus),
    }


def _metrics(payload: dict) -> dict:
    """Current values that tracked targets resolve against.

    Only numbers that come from a fetched source belong here. A target whose
    metric is absent renders as ``unmeasured``, which is the honest state - not
    knowing where something stands is different from knowing it is late.
    """
    metrics: dict[str, float] = {}

    const = payload.get("constellation")
    if const:
        metrics["starlink_in_orbit"] = const["in_orbit"]

    lp = payload.get("launches")
    if lp:
        cadence = lp.get("cadence") or {}
        if cadence.get("spacex"):
            # Trailing 12 months excluding the incomplete current month.
            complete = [
                n
                for n, partial in zip(cadence["spacex"], cadence.get("partial", []))
                if not partial
            ]
            if complete:
                metrics["spacex_launches_12mo"] = sum(complete)
                metrics["spacex_launches_per_month"] = round(sum(complete) / len(complete), 1)
        metrics["people_in_space"] = lp.get("astronauts_count")

    st = payload.get("sites") or {}
    sc = st.get("superchargers") or {}
    if sc.get("open_sites"):
        metrics["supercharger_sites"] = sc["open_sites"]
        metrics["supercharger_stalls"] = sc["total_stalls"]

    fin = payload.get("financials") or {}
    for key, series in (fin.get("series") or {}).items():
        if series.get("points"):
            metrics[f"tsla_{key}_latest"] = series["points"][-1]["value"]

    return {k: v for k, v in metrics.items() if v is not None}


def build_payload() -> dict:
    """Assemble everything the page needs into one JSON-serialisable dict."""

    def cached(name: str):
        env = cache.load(name)
        return env["data"] if env else None

    payload = {
        "meta": {
            "generated": datetime.now(UTC).isoformat(timespec="seconds"),
            "version": "0.1.0",
        },
        "news": cached("news"),
        "launches": cached("launches"),
        "constellation": cached("constellation"),
        "financials": cached("financials"),
        "sites": cached("sites"),
        "status": cache.status_report(),
    }

    # --- commitments board -------------------------------------------------
    # Claims were detected and merged during the news fetch; this only reads the
    # persisted ledger, so rendering never mutates it.
    x = xfeed.load()
    claims = targets.load_claims()

    metrics = _metrics(payload)
    payload["board"] = {
        "tracked": targets.resolve(targets.load_targets(), metrics),
        "claims": claims[:24],
        "claims_total": len(claims),
        "corpus_size": (payload.get("news") or {}).get("corpus_size"),
        "metrics": metrics,
        "x": {k: v for k, v in x.items() if k != "posts"},
        "x_posts": x.get("posts", [])[:6],
    }

    payload["history"] = history.record_and_load(metrics)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the HANGAR page.")
    parser.add_argument("--force", action="store_true", help="refresh every source")
    parser.add_argument("--render", action="store_true", help="render from cache; no network")
    args = parser.parse_args()

    if args.render:
        print("=== RENDER ONLY (no network) ===")
    else:
        print("=== NEWS ===")
        cache.refresh("news", fetch_news, force=args.force)

        print("\n=== LAUNCHES ===")
        cache.refresh("launches", launches.fetch, force=args.force)

        print("\n=== CONSTELLATION ===")
        cache.refresh("constellation", constellation.fetch, force=args.force)

        print("\n=== FINANCIALS ===")
        cache.refresh("financials", financials.fetch, force=args.force)

        print("\n=== SITES ===")
        cache.refresh("sites", sites.fetch, force=args.force)

    payload = build_payload()

    print("\n=== STATUS ===")
    for name, s in payload["status"].items():
        flag = "STALE" if s["stale"] else "ok   "
        err = f"  last error: {s['last_error']}" if s["last_error"] else ""
        print(f"  {flag} {name:15s} age={s['age']:>6}{err}")

    board = payload["board"]
    print(
        f"\n=== BOARD === tracked={len(board['tracked'])} "
        f"claims={board['claims_total']} "
        f"x={'yes' if board['x'].get('available') else 'no'} "
        f"metrics={len(board['metrics'])}"
    )

    out = ROOT / "docs" / "index.html"
    out.parent.mkdir(exist_ok=True)
    render(payload, out)
    print(f"\nWrote {out.stat().st_size:,} bytes to {out}")


if __name__ == "__main__":
    main()
