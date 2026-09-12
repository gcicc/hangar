"""The commitments board: stated ambition against measured reality.

This is the point of HANGAR. Both companies run on public promises with dates
attached, and the interesting question is never "what did they say" but "what
happened to what they said."

Three kinds of row land on the board, and they are deliberately never mixed:

**TRACKED** - curated in ``data/targets.json``. Each carries the statement, the
date it was said, a source URL, and a ``metric`` key that resolves against live
data so status is computed, not asserted. These are the rows with real evidence
on both sides.

**CLAIMED** - detected automatically from incoming headlines by
:func:`detect_claims`. A commitment verb plus a time anchor plus one of the two
companies. These are *candidates*: the regex is noisy, so a claim is shown as
something somebody said in a headline, cited and linked, never as a tracked
fact. Promoting a claim to TRACKED is a human act.

**Nothing else.** In particular this module never invents a target. If a goal is
not in the curated file and was not detected in a real headline with a link, it
does not appear.

Zero LLM calls, matching the house pattern in GRUDGE and clintrialist-report:
the whole pipeline stays free and deterministic.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TARGETS_FILE = DATA_DIR / "targets.json"
CLAIMS_FILE = DATA_DIR / "claims.json"

# Keep the claims ledger bounded; oldest fall off.
MAX_CLAIMS = 120

# --- detection -----------------------------------------------------------

# A commitment needs all three: someone committing, a horizon, and one of the
# two companies. Requiring all three is what keeps the false-positive rate
# survivable without a model in the loop.

_VERBS = (
    r"targets?|aims?|plans?|expects?|promises?|pledges?|vows?|plans to|intends?|"
    r"plans on|plan to|plans for|slated|scheduled|on track|due|plans?|plans|"
    r"hopes?|projects?|forecasts?|guides?|will (?:begin|start|launch|deliver|open|reach|hit|produce|ship|fly|have)|"
    r"to (?:begin|start|launch|deliver|open|reach|hit|produce|ship|fly)|"
    r"says?|said|announced|unveil(?:s|ed)?"
)

_TIME = (
    r"by (?:the )?end of (?:20\d\d|the (?:year|quarter|decade))|"
    r"by (?:early|mid|late) 20\d\d|"
    r"(?:by|in|during|before) Q[1-4](?:\s+20\d\d)?|"
    r"(?:by|in|before) 20\d\d|"
    r"(?:by|in|before) (?:January|February|March|April|May|June|July|August|"
    r"September|October|November|December)(?:\s+20\d\d)?|"
    r"next (?:year|quarter|month)|this (?:year|quarter|month)|"
    r"within (?:the )?next \d+ (?:weeks|months|years)|"
    r"within \d+ (?:weeks|months|years)"
)

_ENTITY = (
    r"Tesla|SpaceX|Musk|Optimus|Starship|Starlink|Cybercab|Cybertruck|Megapack|"
    r"Robotaxi|Gigafactory|Megafactory|Semi|Roadster|Dragon|Falcon"
)

_QUANTITY = (
    r"\d[\d,]*(?:\.\d+)?\s*(?:million|billion|thousand|k|M|B)?\s*"
    r"(?:GWh|MWh|MW|GW|satellites?|vehicles?|cars?|units?|cities|robots?|"
    r"flights?|launches?|deliveries|Megapacks?|users?|subscribers?|stores?|stalls?)"
)

_RE_VERB = re.compile(rf"\b(?:{_VERBS})\b", re.IGNORECASE)
_RE_TIME = re.compile(rf"\b(?:{_TIME})\b", re.IGNORECASE)
_RE_ENTITY = re.compile(rf"\b(?:{_ENTITY})\b", re.IGNORECASE)
_RE_QTY = re.compile(_QUANTITY, re.IGNORECASE)

# Headlines that match the grammar but are questions or speculation about a
# commitment rather than a commitment. Cheap, and it removes a lot of noise.
_RE_SPECULATIVE = re.compile(
    r"\b(?:could|might|may|rumou?r|analyst|speculat|predicts?|bets?|"
    r"here'?s why|what to know|opinion|why |should )",
    re.IGNORECASE,
)

_MONTHS = {
    m.lower(): i
    for i, m in enumerate(
        [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ],
        start=1,
    )
}


def _resolve_horizon(phrase: str, asof: date) -> tuple[str | None, str]:
    """Turn a time phrase into an ISO date and a precision label.

    Returns ``(iso_date_or_None, precision)``. The date is the *end* of the
    stated window, because "by Q3" means the deadline is the end of Q3. The
    precision label travels with it so the board never renders a month-precision
    horizon as though it were a day.
    """
    p = phrase.lower().strip()

    m = re.search(r"20\d\d", p)
    year = int(m.group()) if m else None

    q = re.search(r"q([1-4])", p)
    if q:
        quarter = int(q.group(1))
        y = year or asof.year
        end_month = quarter * 3
        last = 31 if end_month in (3, 12) else 30
        return f"{y:04d}-{end_month:02d}-{last:02d}", "quarter"

    for name, idx in _MONTHS.items():
        if re.search(rf"\b{name}\b", p):
            y = year or asof.year
            last = [31, 29 if y % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][idx - 1]
            return f"{y:04d}-{idx:02d}-{last:02d}", "month"

    if "end of the decade" in p:
        return f"{(asof.year // 10) * 10 + 9:04d}-12-31", "year"
    if "next year" in p:
        return f"{asof.year + 1:04d}-12-31", "year"
    if "this year" in p or "end of the year" in p:
        return f"{asof.year:04d}-12-31", "year"
    if "next quarter" in p:
        nq = (asof.month - 1) // 3 + 2
        y = asof.year + (1 if nq > 4 else 0)
        nq = nq - 4 if nq > 4 else nq
        end_month = nq * 3
        return f"{y:04d}-{end_month:02d}-{30 if end_month in (6, 9) else 31}", "quarter"

    w = re.search(r"within (?:the )?next (\d+) (weeks|months|years)", p) or re.search(
        r"within (\d+) (weeks|months|years)", p
    )
    if w:
        n, unit = int(w.group(1)), w.group(2)
        days = {"weeks": 7, "months": 30, "years": 365}[unit] * n
        return (datetime.fromordinal(asof.toordinal() + days).date().isoformat(), "approx")

    if year:
        return f"{year:04d}-12-31", "year"
    return None, "unknown"


def detect_claims(entries: list[dict], asof: date | None = None) -> list[dict]:
    """Extract candidate commitments from news entries.

    A headline qualifies only if it names one of the two companies, contains a
    commitment verb, states a time horizon, and does not read as speculation.
    Everything returned is a candidate for the CLAIMED lane, never a fact.
    """
    asof = asof or datetime.now(UTC).date()
    claims: list[dict] = []

    for entry in entries:
        text = entry.get("title", "")
        if _RE_SPECULATIVE.search(text):
            continue
        if not _RE_ENTITY.search(text) or not _RE_VERB.search(text):
            continue
        time_hit = _RE_TIME.search(text)
        if not time_hit:
            continue

        horizon, precision = _resolve_horizon(time_hit.group(), asof)
        qty = _RE_QTY.search(text)
        entity = _RE_ENTITY.search(text).group()

        claims.append(
            {
                "statement": text.strip(),
                "entity": entity,
                "horizon_phrase": time_hit.group(),
                "horizon": horizon,
                "horizon_precision": precision,
                "quantity": qty.group().strip() if qty else None,
                "source": entry.get("source"),
                "link": entry.get("link"),
                "first_seen": asof.isoformat(),
                "topics": entry.get("topics", []),
            }
        )
    return claims


def _claim_key(claim: dict) -> str:
    """Normalised identity so the same promise re-reported does not duplicate."""
    text = re.sub(r"[^a-z0-9 ]+", " ", claim["statement"].lower())
    return re.sub(r"\s+", " ", text).strip()[:110]


def load_claims() -> list[dict]:
    """Read the persisted claims ledger without modifying it.

    Rendering must never bump the "times seen" counters - that would turn a
    repeated render into apparent repeated reporting.
    """
    if not CLAIMS_FILE.exists():
        return []
    try:
        return json.loads(CLAIMS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def merge_claims(new: list[dict]) -> list[dict]:
    """Merge newly detected claims into the persistent ledger.

    A promise that keeps being re-reported is not new information, but the fact
    that it is *still* being repeated is - so a repeat bumps ``last_seen`` and
    ``times_seen`` rather than creating a second row.
    """
    existing: list[dict] = []
    if CLAIMS_FILE.exists():
        try:
            existing = json.loads(CLAIMS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = []

    by_key = {_claim_key(c): c for c in existing}
    today = datetime.now(UTC).date().isoformat()

    for claim in new:
        key = _claim_key(claim)
        if key in by_key:
            row = by_key[key]
            row["last_seen"] = today
            row["times_seen"] = row.get("times_seen", 1) + 1
        else:
            claim["last_seen"] = today
            claim["times_seen"] = 1
            by_key[key] = claim

    merged = sorted(by_key.values(), key=lambda c: c.get("last_seen", ""), reverse=True)
    merged = merged[:MAX_CLAIMS]
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CLAIMS_FILE.write_text(json.dumps(merged, indent=1), encoding="utf-8")
    return merged


# --- tracked targets ------------------------------------------------------


def load_targets() -> list[dict]:
    """Load the curated target register. Absent file is not an error."""
    if not TARGETS_FILE.exists():
        return []
    try:
        return json.loads(TARGETS_FILE.read_text(encoding="utf-8")).get("targets", [])
    except (json.JSONDecodeError, OSError) as e:
        print(f"  [WARN] targets.json unreadable: {e}")
        return []


def _status(target: dict, actual: float | None, today: date) -> dict:
    """Compute schedule and progress status for one tracked target.

    Status is derived from data on both sides. A target with no resolvable
    actual is reported as ``unmeasured`` rather than being scored on the
    deadline alone - not knowing where something stands is a distinct state
    from knowing it is late.
    """
    horizon = target.get("target_date")
    due = date.fromisoformat(horizon) if horizon else None
    days_left = (due - today).days if due else None

    goal = target.get("target_value")
    progress = None
    if actual is not None and isinstance(goal, (int, float)) and goal:
        progress = round(actual / goal, 4)

    if actual is None:
        state = "unmeasured"
    elif progress is not None and progress >= 1.0:
        state = "met"
    elif days_left is not None and days_left < 0:
        state = "missed"
    elif days_left is not None and days_left <= 90:
        state = "due-soon"
    else:
        state = "open"

    return {
        "state": state,
        "days_left": days_left,
        "progress": progress,
        "actual": actual,
    }


def resolve(targets: list[dict], metrics: dict, today: date | None = None) -> list[dict]:
    """Join each tracked target to its live actual and compute status.

    ``metrics`` maps a target's ``metric`` key to a current numeric value,
    assembled by ``run.py`` from whatever the fetchers returned.
    """
    today = today or datetime.now(UTC).date()
    out = []
    for target in targets:
        actual = metrics.get(target.get("metric")) if target.get("metric") else None
        row = dict(target)
        row.update(_status(target, actual, today))
        out.append(row)

    order = {"missed": 0, "due-soon": 1, "open": 2, "met": 3, "unmeasured": 4}
    out.sort(
        key=lambda r: (
            order.get(r["state"], 9),
            r.get("days_left") if r.get("days_left") is not None else 99999,
        )
    )
    return out
