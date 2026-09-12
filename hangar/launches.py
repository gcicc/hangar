"""Launch Library 2 client.

The whole design of this module is shaped by one number: the free tier allows
**15 requests per hour** from an unauthenticated IP. So:

* Every run has a hard call cap (``MAX_CALLS``) and counts against it.
* Pads are *derived* from the launches already fetched rather than costing a
  separate ``/pads/`` call. That also gives better data - pads weighted by the
  launches actually flown from them, not a static list.
* Nothing here is ever called from the browser. ``run.py`` writes the result to
  ``data/launches.json`` and the page reads that file.

Provider names are grouped into SpaceX vs everyone else, which is what the
cadence chart compares.
"""

from __future__ import annotations

import time
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta

import requests

BASE = "https://ll.thespacedevs.com/2.3.0"
HEADERS = {"User-Agent": "HANGAR/0.1 (+https://github.com/gcicc/hangar)"}
TIMEOUT = 30

# Free tier is 15 req/hr. Stay well under it so a manual run and a scheduled run
# in the same hour cannot trip the limit between them.
MAX_CALLS = 5
PAUSE_SECONDS = 1.0

PREVIOUS_PAGES = 2
PAGE_SIZE = 100
UPCOMING_LIMIT = 20
CADENCE_MONTHS = 12

SPACEX = "SpaceX"

# Entries LL2 reports as "in space" that are not people. Kept as a set so the
# headcount stays honest without silently dropping them from the page.
NON_HUMAN_IN_SPACE = {"Starman"}


class RateBudget:
    """Counts calls in one run and refuses to exceed MAX_CALLS."""

    def __init__(self, limit: int = MAX_CALLS) -> None:
        self.limit = limit
        self.used = 0

    def spend(self) -> None:
        if self.used >= self.limit:
            raise RuntimeError(f"LL2 call budget of {self.limit} exhausted")
        self.used += 1


def _get(path: str, params: dict, budget: RateBudget) -> dict:
    budget.spend()
    resp = requests.get(f"{BASE}{path}", params=params, headers=HEADERS, timeout=TIMEOUT)
    if resp.status_code == 429:
        # LL2 reports exactly when the window reopens. Carrying that into the
        # status ledger turns "this is broken" into "this retries at a known
        # time", which is the difference between a bug and a wait.
        detail = ""
        try:
            seconds = int(resp.json().get("detail", "").split("available in ")[1].split(" ")[0])
            detail = f" - retry in {seconds // 60}m{seconds % 60:02d}s"
        except (ValueError, IndexError, KeyError):
            pass
        raise RuntimeError(f"LL2 throttled (429){detail}")
    resp.raise_for_status()
    time.sleep(PAUSE_SECONDS)  # be a polite client on a free tier
    return resp.json()


def _provider(launch: dict) -> str:
    return ((launch.get("launch_service_provider") or {}).get("name") or "Unknown").strip()


def _normalize(launch: dict) -> dict:
    """Flatten one LL2 launch into the compact shape the page needs."""
    pad = launch.get("pad") or {}
    mission = launch.get("mission") or {}
    rocket_cfg = (launch.get("rocket") or {}).get("configuration") or {}
    status = launch.get("status") or {}
    image = launch.get("image") or {}

    lat, lon = pad.get("latitude"), pad.get("longitude")
    launch_id = launch.get("id")
    return {
        "id": launch_id,
        "name": launch.get("name"),
        "net": launch.get("net"),
        "net_precision": (launch.get("net_precision") or {}).get("abbrev"),
        "status": status.get("abbrev"),
        "status_name": status.get("name"),
        "provider": _provider(launch),
        "rocket": rocket_cfg.get("full_name") or rocket_cfg.get("name"),
        "mission": mission.get("name"),
        "mission_type": mission.get("type"),
        "orbit": (mission.get("orbit") or {}).get("abbrev"),
        "description": (mission.get("description") or "")[:400],
        "pad": pad.get("name"),
        "pad_location": (pad.get("location") or {}).get("name"),
        "lat": float(lat) if lat not in (None, "") else None,
        "lon": float(lon) if lon not in (None, "") else None,
        "image": image.get("thumbnail_url") or image.get("image_url"),
        "webcast_live": launch.get("webcast_live"),
        "url": f"https://nextspaceflight.com/launches/details/{launch_id}" if launch_id else None,
    }


def parse_net(net: str | None) -> datetime | None:
    """Parse an LL2 NET timestamp, returning None rather than raising."""
    if not net:
        return None
    try:
        return datetime.fromisoformat(net)
    except ValueError:
        return None


def _cadence(previous: list[dict], months: int = CADENCE_MONTHS) -> dict:
    """Monthly launch counts, SpaceX vs everyone else, oldest month first.

    Two months in this series are partial and would lie if charted as-is:

    * The **oldest** one is only as complete as the sample reaches. We fetch a
      fixed number of launches, not a fixed date range, so the earliest bucket is
      truncated at an arbitrary day. It is dropped entirely.
    * The **current** month is partial because it has not finished. It is kept -
      dropping it would hide this month's activity - but flagged so the page can
      render it distinctly instead of implying a cadence collapse.
    """
    cutoff = datetime.now(UTC) - timedelta(days=31 * months)
    buckets: dict[str, Counter] = defaultdict(Counter)
    for launch in previous:
        dt = parse_net(launch["net"])
        if dt is None or dt < cutoff:
            continue
        key = f"{dt.year:04d}-{dt.month:02d}"
        buckets[key]["spacex" if launch["provider"] == SPACEX else "other"] += 1

    labels = sorted(buckets)
    # Drop the truncated oldest bucket once there is enough series to spare it.
    if len(labels) > 2:
        labels = labels[1:]

    now = datetime.now(UTC)
    current = f"{now.year:04d}-{now.month:02d}"
    return {
        "labels": labels,
        "spacex": [buckets[m]["spacex"] for m in labels],
        "other": [buckets[m]["other"] for m in labels],
        "partial": [m == current for m in labels],
        "note": "Current month is incomplete; earliest sampled month omitted.",
    }


def _pads(launches: list[dict]) -> list[dict]:
    """Derive the pad map from launches already fetched. Costs no extra call."""
    pads: dict[tuple, dict] = {}
    for launch in launches:
        if launch["lat"] is None or launch["lon"] is None or not launch["pad"]:
            continue
        key = (launch["pad"], launch["pad_location"])
        entry = pads.setdefault(
            key,
            {
                "name": launch["pad"],
                "location": launch["pad_location"],
                "lat": launch["lat"],
                "lon": launch["lon"],
                "count": 0,
                "providers": Counter(),
                "last_net": None,
            },
        )
        entry["count"] += 1
        entry["providers"][launch["provider"]] += 1
        if launch["net"] and (entry["last_net"] is None or launch["net"] > entry["last_net"]):
            entry["last_net"] = launch["net"]

    out = []
    for entry in pads.values():
        providers = entry.pop("providers")
        entry["top_provider"] = providers.most_common(1)[0][0] if providers else None
        entry["spacex"] = providers.get(SPACEX, 0) > 0
        out.append(entry)
    out.sort(key=lambda p: p["count"], reverse=True)
    return out


def _next_launch(upcoming: list[dict]) -> dict | None:
    """First upcoming launch whose NET is still in the future."""
    now = datetime.now(UTC)
    future = [launch for launch in upcoming if (parse_net(launch["net"]) or now) > now]
    return future[0] if future else (upcoming[0] if upcoming else None)


def fetch() -> dict:
    """Fetch launches and astronauts, derive cadence and pads. Uses 4 calls."""
    budget = RateBudget()

    upcoming_raw = _get("/launches/upcoming/", {"limit": UPCOMING_LIMIT, "mode": "normal"}, budget)
    upcoming = [_normalize(launch) for launch in upcoming_raw["results"]]
    print(f"  [OK]   LL2 upcoming: {len(upcoming)}")

    previous: list[dict] = []
    for page in range(PREVIOUS_PAGES):
        payload = _get(
            "/launches/previous/",
            {"limit": PAGE_SIZE, "offset": page * PAGE_SIZE, "mode": "normal"},
            budget,
        )
        previous.extend(_normalize(launch) for launch in payload["results"])
        if not payload.get("next"):
            break
    print(f"  [OK]   LL2 previous: {len(previous)}")

    astronauts_raw = _get("/astronauts/", {"limit": 30, "in_space": "true"}, budget)
    everyone = [
        {
            "name": a.get("name"),
            "agency": (a.get("agency") or {}).get("abbrev"),
            "type": (a.get("type") or {}).get("name")
            if isinstance(a.get("type"), dict)
            else a.get("type"),
            "status": (a.get("status") or {}).get("name")
            if isinstance(a.get("status"), dict)
            else a.get("status"),
            "flights": a.get("flights_count"),
            "image": (a.get("image") or {}).get("thumbnail_url"),
        }
        for a in astronauts_raw["results"]
    ]
    # LL2's "in space" list includes Starman - the mannequin in the Roadster on a
    # heliocentric orbit. Counting him as a person in space is wrong, but a Tesla
    # in solar orbit is squarely on-topic for this page, so he is separated out
    # rather than discarded.
    astronauts = [a for a in everyone if a["name"] not in NON_HUMAN_IN_SPACE]
    passengers = [a for a in everyone if a["name"] in NON_HUMAN_IN_SPACE]
    print(f"  [OK]   LL2 in space: {len(astronauts)} people (+{len(passengers)} non-human)")

    spacex_previous = [launch for launch in previous if launch["provider"] == SPACEX]

    # The share below is over a rolling window of the most recent N launches,
    # not over all launches ever or over a fixed calendar period. The window's
    # own start and end therefore travel with it, because without them the
    # number reads as "SpaceX's share of world launches" - a very different and
    # much stronger claim than the data supports.
    nets = sorted(launch["net"] for launch in previous if launch["net"])
    window = {"from": nets[0][:10], "to": nets[-1][:10]} if nets else None
    return {
        "next": _next_launch(upcoming),
        "upcoming": upcoming,
        "previous": previous[:60],  # what the page lists; cadence uses the full set
        "astronauts": astronauts,
        "astronauts_count": len(astronauts),
        "passengers": passengers,
        "cadence": _cadence(previous),
        "pads": _pads(previous + upcoming),
        "totals": {
            "previous_sampled": len(previous),
            "spacex_sampled": len(spacex_previous),
            "spacex_share": round(len(spacex_previous) / len(previous), 3) if previous else None,
            "window": window,
            "share_caveat": (
                "Share of the most recent orbital launches fetched, over the "
                "window shown. Not a share of all launches, and not a fixed "
                "calendar period - the window moves with every refresh."
            ),
        },
        "calls_used": budget.used,
    }
