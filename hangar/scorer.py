"""Relevance ranking: materiality x recency.

Structurally this is GRUDGE's ``scorer.py`` - keyword points, a linear recency
decay, sort and truncate. The keyword table is the part that changes. GRUDGE
scores for *drama* because it is a Drudge parody; HANGAR scores for
*materiality*: things that actually moved a rocket, a factory line, or a share
price outrank things that were merely written about loudly.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

# Word -> base points, case-insensitive, matched on word boundaries.
MATERIALITY: dict[str, int] = {
    # Something physically happened
    "launch": 5,
    "landed": 5,
    "exploded": 5,
    "anomaly": 5,
    "mishap": 5,
    "static fire": 4,
    "liftoff": 4,
    "dock": 4,
    "splashdown": 4,
    "scrub": 3,
    "delay": 2,
    # Numbers were disclosed
    "deliveries": 5,
    "earnings": 5,
    "results": 3,
    "guidance": 4,
    "record": 3,
    "production": 3,
    "subscribers": 3,
    # A regulator or court acted
    "recall": 5,
    "approve": 4,
    "approval": 4,
    "license": 3,
    "investigation": 4,
    "probe": 3,
    "lawsuit": 3,
    "subpoena": 4,
    "settlement": 3,
    # Capital moved
    "ipo": 4,
    "lock-up": 4,
    "offering": 3,
    "stake": 3,
    "acquisition": 4,
    "contract": 4,
    "award": 4,
    "raised": 3,
}

# Speculation is a *multiplier*, not a negative keyword.
#
# As additive points these markers demoted inconsistently, because their effect
# depended on whatever else the headline contained: "might" took a neutral story
# from 1.0 to 0.2 (five-fold) but a recall story from 6.0 to 5.0 (barely at all).
# Worse, "Rumor: Tesla might launch something" scored 3.0 - triple a confirmed
# routine story - because -2 and -1 cannot offset a +5 verb.
#
# A multiplier is scale-invariant: it demotes speculation by the same proportion
# whatever the subject, so a rumoured launch still outranks a routine opening
# while ranking below the same launch confirmed.
SPECULATION: dict[str, float] = {
    "rumor": 0.35,
    "rumour": 0.35,
    "here's why": 0.25,
    "what to know": 0.3,
    "reportedly": 0.6,
    "could": 0.6,
    "might": 0.6,
    "may": 0.75,
    "analyst": 0.6,
    "speculation": 0.35,
    "predicts": 0.5,
}

# Keywords are matched with common inflections. Without this "recall" scores 5
# and "recalls" scores nothing, which let filler headlines outrank an actual
# vehicle recall. Multi-word phrases and words already carrying a suffix are
# matched literally - "deliveries" must not become "deliveriess".
_INFLECTED = r"(?:s|es|ed|ing)?"


def _pattern(word: str) -> str:
    """Match a keyword and its common inflections.

    Three cases. Phrases and words already inflected are matched literally.
    Words ending in "e" drop it before the suffix, so "approve" also catches
    "approved" and "approving" rather than the impossible "approveed".
    Everything else takes a plain optional suffix.
    """
    literal = re.escape(word)
    if " " in word or word.endswith(("s", "ed", "ing", "al", "y")):
        return rf"(?<!\w){literal}(?!\w)"
    if word.endswith("e"):
        return rf"(?<!\w){re.escape(word[:-1])}(?:e|es|ed|ing)(?!\w)"
    return rf"(?<!\w){literal}{_INFLECTED}(?!\w)"


_COMPILED = {word: re.compile(_pattern(word), re.IGNORECASE) for word in MATERIALITY}
_SPEC_COMPILED = {word: re.compile(_pattern(word), re.IGNORECASE) for word in SPECULATION}

# Recency decay window. Beyond this a story keeps only the floor multiplier.
DECAY_HOURS = 36.0
FLOOR = 0.15

# Filler is allowed to score below a neutral story, but never to zero.
BASE_FLOOR = 0.2


def _keyword_score(text: str) -> float:
    return float(
        sum(points for word, points in MATERIALITY.items() if _COMPILED[word].search(text))
    )


def _recency_multiplier(published: datetime) -> float:
    """Linear decay from 1.0 at publication to FLOOR at DECAY_HOURS."""
    age_hours = max(0.0, (datetime.now(UTC) - published).total_seconds() / 3600)
    return max(FLOOR, 1.0 - (age_hours / DECAY_HOURS))


def _speculation_multiplier(text: str) -> float:
    """Combined penalty for speculation markers. 1.0 when none are present."""
    factor = 1.0
    for word, penalty in SPECULATION.items():
        if _SPEC_COMPILED[word].search(text):
            factor *= penalty
    return factor


def score_entry(entry: dict) -> float:
    """Materiality x speculation x recency for one entry.

    A neutral story scores 1.0 before decay; a material one scores higher, and
    speculation scales the whole thing down proportionally rather than
    subtracting a fixed amount whose bite depends on the rest of the headline.
    """
    text = f"{entry.get('title', '')} {entry.get('summary', '')}"
    base = max(1.0, 1.0 + _keyword_score(text))
    score = base * _speculation_multiplier(text) * _recency_multiplier(entry["published"])
    return max(BASE_FLOOR * _recency_multiplier(entry["published"]), score)


def rank(entries: list[dict], limit: int) -> list[dict]:
    """Score, sort descending, and truncate."""
    for e in entries:
        e["score"] = round(score_entry(e), 3)
    entries.sort(key=lambda e: e["score"], reverse=True)
    return entries[:limit]


# A story older than this is not news, whatever its keyword score. Without a
# hard cap, a high-materiality headline ("Production & Deliveries") beats a
# fresh one purely on keywords once the recency floor stops decaying - which is
# how a 2023 quarterly report ended up at the top of the Tesla column.
MAX_AGE_DAYS = 21


def drop_stale(entries: list[dict], max_age_days: int = MAX_AGE_DAYS) -> list[dict]:
    """Remove entries older than the cutoff."""
    cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
    return [e for e in entries if e["published"] >= cutoff]
