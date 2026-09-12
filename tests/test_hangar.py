"""Tests for the parts where being wrong is silent.

The bias here is toward the logic that would fail *quietly*: a topic tagger
mislabelling stories, a cache that overwrites good data with an error, a
countdown claiming more precision than its source has. A broken fetch announces
itself; these do not.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import pytest

from hangar import cache, targets
from hangar.feeds import RELEVANCE
from hangar.fetcher import dedupe, dedupe_key, require_relevance
from hangar.scorer import drop_stale, rank, score_entry
from hangar.topics import tag_entry


def entry(title, published=None, summary=""):
    return {
        "title": title,
        "summary": summary,
        "published": published or datetime.now(UTC),
        "link": "https://example.com/x",
        "source": "Test",
    }


# --- topic tagging -------------------------------------------------------


@pytest.mark.parametrize(
    "title,expected",
    [
        ("SpaceX to launch 80th Starlink mission of 2026", True),
        ("Isar Aerospace launches Spectrum rocket after delays", True),
        ("Falcon 9 booster landed on droneship", True),
        # "Launch" also means "initiate". These must not be tagged as launches.
        ("NHTSA Launches Probe Into Tesla Cybercab", False),
        ("Tesla launches a new service in Austin", False),
        ("Tesla launches new Model Y trim", False),
        ("Tesla lands a big deal with Panasonic", False),
    ],
)
def test_launch_topic_disambiguation(title, expected):
    assert ("launch" in tag_entry(entry(title))) is expected


def test_optimus_is_its_own_topic_not_autonomy():
    tags = tag_entry(entry("Tesla Optimus Gen 3 walks unaided in new demo"))
    assert "optimus" in tags
    assert "autonomy" not in tags


def test_robotaxi_is_autonomy_not_optimus():
    tags = tag_entry(entry("Tesla robotaxi expands to Phoenix"))
    assert "autonomy" in tags
    assert "optimus" not in tags


def test_regulatory_beats_launch_for_a_probe():
    tags = tag_entry(entry("NHTSA Launches Probe Into Tesla Cybercab"))
    assert tags[0] != "launch"
    assert "regulatory" in tags


# --- relevance and recency ----------------------------------------------


def test_relevance_drops_sector_news_about_other_companies():
    kept = require_relevance(
        [
            entry("BYD launches biggest-ever sales event in the UK"),
            entry("Uber launched the UK's first autonomous rides in London"),
            entry("Tesla Cybercab begins public rides in Austin"),
        ],
        RELEVANCE,
    )
    assert [e["title"] for e in kept] == ["Tesla Cybercab begins public rides in Austin"]


def test_stale_high_keyword_story_is_dropped():
    """A 2023 quarterly report outscored fresh news before the age cap existed."""
    old = entry(
        "Tesla Vehicle Production & Deliveries for Fourth Quarter 2023",
        published=datetime.now(UTC) - timedelta(days=777),
    )
    fresh = entry("Tesla opens new Supercharger site")
    assert score_entry(old) > score_entry(fresh), "premise: keywords beat recency"
    assert drop_stale([old, fresh]) == [fresh]


def test_rank_orders_by_materiality_then_recency():
    ranked = rank(
        [
            entry("Here's why Tesla stock might move"),
            entry("Tesla recalls 12,000 vehicles over steering fault"),
        ],
        limit=2,
    )
    assert ranked[0]["title"].startswith("Tesla recalls")


# --- dedupe --------------------------------------------------------------


def test_dedupe_key_strips_google_news_publisher_suffix():
    a = dedupe_key("SpaceX clears Starship mishap probe - CNBC")
    b = dedupe_key("SpaceX clears Starship mishap probe | Reuters")
    assert a == b


def test_shared_seen_set_prevents_cross_section_duplicates():
    seen: set[str] = set()
    first = dedupe([entry("Tesla misses on earnings")], seen)
    second = dedupe([entry("Tesla misses on earnings - CNBC")], seen)
    assert len(first) == 1
    assert second == []


# --- claim detection -----------------------------------------------------


def test_detects_a_dated_commitment():
    claims = targets.detect_claims(
        [entry("Elon Musk says Tesla will sell humanoid robots by end of 2027")]
    )
    assert len(claims) == 1
    assert claims[0]["horizon"] == "2027-12-31"


def test_ignores_speculation_that_matches_the_grammar():
    claims = targets.detect_claims(
        [
            entry("Tesla could reach 20,000 robots by 2027, analyst says"),
            entry("Here's why Tesla might ship Optimus in 2027"),
        ]
    )
    assert claims == []


def test_requires_a_time_horizon():
    assert targets.detect_claims([entry("Tesla plans to build more Optimus robots")]) == []


def test_requires_one_of_the_two_companies():
    assert targets.detect_claims([entry("Rivian plans to launch a new truck in 2027")]) == []


@pytest.mark.parametrize(
    "phrase,expected_precision",
    [("by Q3 2027", "quarter"), ("in March 2027", "month"), ("by 2027", "year")],
)
def test_horizon_precision_is_preserved(phrase, expected_precision):
    claims = targets.detect_claims([entry(f"Tesla plans to ship Optimus {phrase}")])
    assert claims and claims[0]["horizon_precision"] == expected_precision


# --- target status -------------------------------------------------------


def test_unmeasured_is_distinct_from_missed():
    """A target with no live metric is unknown, not late - even past its date."""
    rows = targets.resolve(
        [{"id": "t", "statement": "x", "target_date": "2020-01-01", "metric": "nothing"}],
        metrics={},
        today=date(2026, 9, 5),
    )
    assert rows[0]["state"] == "unmeasured"


def test_missed_when_past_due_and_short():
    rows = targets.resolve(
        [
            {
                "id": "t",
                "statement": "x",
                "target_date": "2026-01-01",
                "target_value": 100,
                "metric": "m",
            }
        ],
        metrics={"m": 40},
        today=date(2026, 9, 5),
    )
    assert rows[0]["state"] == "missed"
    assert rows[0]["progress"] == 0.4


def test_met_when_goal_reached_even_if_late():
    rows = targets.resolve(
        [
            {
                "id": "t",
                "statement": "x",
                "target_date": "2026-01-01",
                "target_value": 100,
                "metric": "m",
            }
        ],
        metrics={"m": 120},
        today=date(2026, 9, 5),
    )
    assert rows[0]["state"] == "met"


# --- cache ---------------------------------------------------------------


def test_failed_fetch_keeps_previous_data(tmp_path, monkeypatch):
    """The property the whole design rests on: an outage degrades to stale."""
    monkeypatch.setattr(cache, "DATA_DIR", tmp_path)
    cache.save("news", {"v": "good"})

    def boom():
        raise RuntimeError("upstream down")

    assert cache.refresh("news", boom, force=True) == {"v": "good"}
    saved = json.loads((tmp_path / "news.json").read_text())
    assert saved["data"] == {"v": "good"}


def test_not_modified_does_not_record_an_error(tmp_path, monkeypatch):
    """CelesTrak's 403 means 'unchanged'. It must not mark the source broken."""
    monkeypatch.setattr(cache, "DATA_DIR", tmp_path)
    cache.save("constellation", {"in_orbit": 8000})

    def unchanged():
        raise cache.NotModified("GP data has not updated")

    assert cache.refresh("constellation", unchanged, force=True) == {"in_orbit": 8000}
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["constellation"]["last_error"] is None


def test_fresh_cache_is_not_refetched(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "DATA_DIR", tmp_path)
    cache.save("news", {"v": 1})
    calls = []
    cache.refresh("news", lambda: calls.append(1) or {"v": 2})
    assert calls == [], "a fresh source must not hit the network"


# --- speculation is a multiplier, not a negative keyword ------------------


def test_rumoured_event_ranks_below_the_confirmed_one():
    """A -2 keyword cannot offset a +5 verb, so speculation must scale instead."""
    confirmed = entry("SpaceX launches Starlink on record 37th flight")
    rumoured = entry("Rumor: SpaceX might launch Starlink on a record flight")
    assert score_entry(confirmed) > score_entry(rumoured) * 3


def test_speculation_penalty_is_proportional_not_fixed():
    """The same marker must bite equally hard whatever else is in the headline.

    As additive points, "might" cut a neutral story five-fold and a recall story
    barely at all.
    """
    from hangar.scorer import _speculation_multiplier

    plain_ratio = score_entry(entry("Tesla might open a site")) / score_entry(
        entry("Tesla opens a site")
    )
    material_ratio = score_entry(entry("Tesla might recall 12,000 vehicles")) / score_entry(
        entry("Tesla recalls 12,000 vehicles")
    )
    assert abs(plain_ratio - material_ratio) < 0.02
    assert _speculation_multiplier("no markers here") == 1.0


def test_rumour_still_outranks_a_routine_story():
    """Demoted, not buried: a rumoured launch is still more interesting."""
    assert score_entry(entry("Rumor: Tesla might launch something")) > score_entry(
        entry("Tesla opens a new Supercharger site")
    )
