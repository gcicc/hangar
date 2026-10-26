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
from hangar import orbits_history as oh
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


@pytest.mark.parametrize(
    ("title", "topic"),
    [
        ("xAI plans to bring Colossus 2 online by end of 2027", "ai"),
        ("Neuralink aims to implant 1,000 patients by 2027", "neurotech"),
        ("Boring Company says Vegas Loop will open 10 new stations by 2027", "tunnels"),
    ],
)
def test_smaller_companies_pass_relevance_tag_and_claim(title, topic):
    """Each layer has its own vocabulary; missing one drops the company silently."""
    e = entry(title)
    assert require_relevance([e], RELEVANCE) == [e]
    assert tag_entry(e)[0] == topic
    assert targets.detect_claims([e], date(2026, 10, 8))


def test_relevance_rejects_hyphenated_x_corp_lookalike():
    kept = require_relevance(
        [
            entry("Form 13D/A Karbon-X Corp For: 9 October"),
            entry("X Corp files suit over advertiser boycott"),
        ],
        RELEVANCE,
    )
    assert [e["title"] for e in kept] == ["X Corp files suit over advertiser boycott"]


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


def test_ignores_third_party_forecasts():
    claims = targets.detect_claims(
        [entry("Wells Fargo's Starlink Forecast: 47M Subscribers and $51B by 2028")]
    )
    assert claims == []


def test_ignores_retrospective_dates():
    claims = targets.detect_claims(
        [entry("In 2018, Musk said Tesla would hit production targets")],
        asof=date(2026, 9, 27),
    )
    assert claims == []


def test_collapse_merges_one_story_across_outlets():
    rows = [
        {
            "statement": "Tesla will sell Optimus in 2027 - Electrek",
            "source": "Electrek",
            "horizon": "2027-12-31",
            "first_seen": "2026-09-10",
            "last_seen": "2026-09-20",
            "times_seen": 3,
        },
        {
            "statement": "Tesla will sell Optimus in 2027 - electrek.co",
            "source": "electrek.co",
            "horizon": "2027-12-31",
            "first_seen": "2026-09-12",
            "last_seen": "2026-09-25",
            "times_seen": 2,
        },
    ]
    out = targets.collapse(rows)
    assert len(out) == 1
    assert out[0]["outlets"] == ["Electrek", "electrek.co"]
    assert out[0]["first_seen"] == "2026-09-10" and out[0]["last_seen"] == "2026-09-25"


def test_this_month_resolves_to_month_end():
    horizon, precision = targets._resolve_horizon("this month", date(2026, 9, 13))
    assert (horizon, precision) == ("2026-09-30", "month")


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


# --- time-lapse catalogue (orbits_history) --------------------------------


SATCAT_FIXTURE = """OBJECT_NAME,OBJECT_ID,NORAD_CAT_ID,OBJECT_TYPE,OPS_STATUS_CODE,OWNER,LAUNCH_DATE,LAUNCH_SITE,DECAY_DATE,PERIOD,INCLINATION,APOGEE,PERIGEE,RCS,DATA_STATUS_CODE,ORBIT_CENTER,ORBIT_TYPE
SL-1 R/B,1957-001A,1,R/B,D,CIS,1957-10-04,TYMSC,1957-12-01,96.19,65.10,938,214,20.42,,EA,IMP
SPUTNIK 1,1957-001B,2,PAY,D,CIS,1957-10-04,TYMSC,1958-01-03,96.10,65.00,1080,64,,,EA,IMP
"STARLINK-1008",2019-074A,44714,PAY,+,US,2019-11-11,AFETR,,94.0,53.05,470,460,,,EA,ORB
NAVSTAR 81 (USA 319),2021-054A,48859,PAY,+,US,2021-06-17,AFETR,,717.9,55.0,20200,20160,,,EA,ORB
LUNAR PROBE,2022-001A,50000,PAY,+,US,2022-01-01,AFETR,,,,,,,,MO,ORB
MYSTERY SAT,2023-001A,50001,PAY,+,TBD,2023-01-01,NOWHERE,,95.0,97.5,520,500,,,EA,ORB
"""

PSATCAT_FIXTURE = (
    "#JCAT\tPiece\tName\tLDate\tTLast\tTOp\tTDate\tTF\tProgram\tPlane\tAtt\tMvr\tClass\tCategory\n"
    "# Updated 2026 Oct 26\n"
    "S00002    \t1957 ALP 2\tFirst Sputnik\t-\t-\t-\t-\t-\tSputnik\t-\t-\t-\tC\tTECH\n"
    "S44714    \t2019-074A\tStarlink\t-\t-\t-\t-\t-\tStarlink\t-\t-\t-\tB\tCOM\n"
    "S48859    \t2021-054A\tNavstar\t-\t-\t-\t-\t-\tGPS\t-\t-\t-\tD\tNAV\n"
)

LAUNCH_FIXTURE = (
    "#Launch_Tag\tLaunch_JD\tLaunch_Date\tLV_Type\n"
    "# Updated 2026 Oct 26\n"
    "1957-001 \t0\t1957 Oct  4\tSputnik 8K71PS\n"
    "2019-074 \t0\t2019 Nov 11\tFalcon 9\n"
    "2021-054 \t0\t2021 Jun 17\tFalcon 9\n"
    "2023-001 \t0\t2023 Jan  1\tViper Falcon\n"
)


@pytest.fixture
def catalogue():
    return oh.build(SATCAT_FIXTURE, PSATCAT_FIXTURE, LAUNCH_FIXTURE)


def test_catalogue_keeps_only_earth_orbit_payloads(catalogue):
    # Rocket body and lunar probe out; Sputnik, Starlink, GPS and the mystery sat in.
    assert catalogue["sat"]["id"] == [2, 44714, 48859, 50001]
    assert catalogue["counts"]["skipped"] == {"left Earth orbit": 1}


def test_decay_dates_separate_history_from_the_current_fleet(catalogue):
    dec = catalogue["sat"]["dec"]
    assert dec[0] == (date(1958, 1, 3) - oh.EPOCH).days
    assert dec[1:] == [-1, -1, -1]
    assert catalogue["counts"]["in_orbit"] == 3


def test_spacex_launches_come_from_the_vehicle_not_the_owner(catalogue):
    launch = catalogue["launch"]
    spx = dict(zip(launch["tag"], launch["spx"], strict=True))
    # A US Air Force GPS satellite on a Falcon 9 is a SpaceX launch.
    assert spx == {"1957-001": 0, "2019-074": 1, "2021-054": 1, "2023-001": 0}
    assert catalogue["counts"]["spacex_launches"] == 2


def test_starlink_is_spacex_owned_and_its_name_is_compressed(catalogue):
    sat = catalogue["sat"]
    assert catalogue["groups"][sat["g"][1]] == "SpaceX"
    assert sat["name"][1] == "*1008"
    # Other US satellites are not SpaceX's, whoever launched them.
    assert catalogue["groups"][sat["g"][2]] == "US"


def test_unclassified_and_unmapped_are_kept_and_counted(catalogue):
    sat = catalogue["sat"]
    assert catalogue["purposes"][sat["p"][3]] == "Other"
    assert catalogue["counts"]["unclassified"] == 1
    # An unknown site still appears, without coordinates, so the page skips its streak.
    site = catalogue["sites"][catalogue["launch"]["site"][3]]
    assert site[0] == "NOWHERE" and site[2] is None


@pytest.mark.parametrize(
    ("category", "cls", "expected"),
    [
        ("COM", "B", "Communications"),
        ("COM", "D", "Military"),
        ("NAV", "D", "Navigation"),
        ("IMG*", "C", "Earth observation"),
        ("COM/MET-RO", "B", "Communications"),
        ("SIG?", "C", "Military"),
        ("SS", "C", "Science & crewed"),
        ("", "", "Other"),
    ],
)
def test_purpose_buckets(category, cls, expected):
    assert oh.purpose(category, cls) == expected


@pytest.mark.parametrize(
    ("owner", "name", "expected"),
    [
        ("US", "STARLINK-30001", "SpaceX"),
        ("US", "GPS IIF-1", "US"),
        ("GLOB", "GLOBALSTAR M001", "US"),
        ("CIS", "COSMOS 2500", "USSR / Russia"),
        ("PRC", "BEIDOU-3 M1", "China"),
        ("FR", "SPOT 6", "Europe"),
        ("ISRA", "OFEQ 16", "Other"),
    ],
)
def test_owner_groups(owner, name, expected):
    assert oh.owner_group(owner, name) == expected


def test_site_coordinates_are_on_the_globe():
    for name, lat, lon, _approx in oh.SITES.values():
        assert -90 <= lat <= 90 and -180 <= lon <= 180, name


def test_published_sources_are_written_compact_to_docs(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(cache, "PUBLISH_DIR", tmp_path / "docs")
    cache.save("fleet", {"id": [1, 2]})
    cache.save("news", {"x": 1})
    published = (tmp_path / "docs" / "fleet.json").read_text(encoding="utf-8")
    assert "\n" not in published and '"id":[1,2]' in published
    assert (tmp_path / "data" / "news.json").exists()
    assert not (tmp_path / "data" / "fleet.json").exists()
    assert cache.load("fleet")["data"] == {"id": [1, 2]}


def test_greek_letter_era_launches_join_on_date():
    # GCAT keeps "1957 ALP" and "1961 A BET"; SATCAT renumbered them "1957-001".
    satcat = (
        SATCAT_FIXTURE.splitlines()[0]
        + "\n"
        + (
            "EXPLORER 1,1958-001A,4,PAY,D,US,1958-02-01,AFETR,1970-03-31,0,33.2,2550,350,,,EA,ELL\n"
            "DISCOVERER 32,1961-026A,177,PAY,D,US,1961-09-17,AFWTR,1961-10-13,0,82.6,400,240,,,EA,ELL\n"
        )
    )
    launch_tsv = LAUNCH_FIXTURE + (
        "1958 ALP  \t0\t1958 Feb  1 0347:56\tJuno I\n"
        "1961 A BET  \t0\t1961 Sep 17 2100\tThor Agena B\n"
    )
    cat = oh.build(satcat, PSATCAT_FIXTURE, launch_tsv)
    lvs = [cat["lvs"][i] for i in cat["launch"]["lv"]]
    assert lvs == ["Juno I", "Thor Agena B"]
