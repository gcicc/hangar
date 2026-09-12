"""Tesla and SpaceX market data and filed financial history.

Two sources, both free and both authoritative for what they cover:

* **SEC XBRL** (``data.sec.gov``) for filed quarterly figures. This is the real
  growth spine on the money side - numbers a company signed its name to, going
  back years, rather than anything reconstructed or remembered.
* **Yahoo's chart endpoint** for quotes and price series, using the same
  keyless call already proven in ``GRUDGE/grudge/market.py``.

One XBRL quirk is handled explicitly. Q4 is almost never tagged as its own
quarterly fact: the 10-K reports the full year, and Q4 has to be derived as
``FY - (Q1 + Q2 + Q3)``. Skipping that step silently drops every fourth point
and makes the series look seasonal when it is not.
"""

from __future__ import annotations

import os
from datetime import date

import requests

SEC_BASE = "https://data.sec.gov/api/xbrl/companyconcept"
# SEC asks for a contact address in the User-Agent and throttles anonymous clients.
# Kept out of the source so a public repo does not carry a personal address; set
# SEC_CONTACT locally and as a repository secret for the refresh workflow.
SEC_CONTACT = os.environ.get("SEC_CONTACT", "hangar@example.invalid")
SEC_HEADERS = {"User-Agent": f"HANGAR/0.1 {SEC_CONTACT}"}

YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YAHOO_HEADERS = {"User-Agent": "HANGAR/0.1"}

TIMEOUT = 30

TICKERS = {
    "TSLA": "Tesla",
    "SPCX": "SpaceX",
}

CIKS = {"TSLA": "CIK0001318605"}

CONCEPTS = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
    ],
    "net_income": ["NetIncomeLoss"],
    "rnd": ["ResearchAndDevelopmentExpense"],
}

# A fact is "quarterly" if its period is about a quarter long, and "annual" if
# about a year. XBRL contains many overlapping windows; these bounds pick the
# two that matter and ignore half-years and nine-month cumulatives.
_Q_MIN, _Q_MAX = 80, 100
_Y_MIN, _Y_MAX = 350, 380


def _days(fact: dict) -> int:
    return (date.fromisoformat(fact["end"]) - date.fromisoformat(fact["start"])).days


def _quarter_of(end: str) -> tuple[int, int]:
    d = date.fromisoformat(end)
    return d.year, (d.month - 1) // 3 + 1


def _derive_q4(quarterly: dict[tuple, float], annual: dict[int, float]) -> dict[tuple, float]:
    """Fill in Q4 as FY minus the first three quarters, where all four exist."""
    filled = dict(quarterly)
    for year, fy_value in annual.items():
        if (year, 4) in filled:
            continue
        parts = [quarterly.get((year, q)) for q in (1, 2, 3)]
        if all(p is not None for p in parts):
            filled[(year, 4)] = round(fy_value - sum(parts), 2)
    return filled


def _fetch_concept(cik: str, names: list[str]) -> dict | None:
    """Try each concept name in order; return the first that resolves."""
    for name in names:
        url = f"{SEC_BASE}/{cik}/us-gaap/{name}.json"
        resp = requests.get(url, headers=SEC_HEADERS, timeout=TIMEOUT)
        if resp.status_code == 404:
            continue
        resp.raise_for_status()
        return resp.json()
    return None


def _series_from_concept(payload: dict) -> dict:
    facts = payload.get("units", {}).get("USD", [])
    quarterly: dict[tuple, float] = {}
    annual: dict[int, float] = {}

    for fact in facts:
        if "start" not in fact or "end" not in fact:
            continue
        length = _days(fact)
        if _Q_MIN <= length <= _Q_MAX:
            quarterly[_quarter_of(fact["end"])] = fact["val"]
        elif _Y_MIN <= length <= _Y_MAX:
            annual[date.fromisoformat(fact["end"]).year] = fact["val"]

    derived = set(_derive_q4(quarterly, annual)) - set(quarterly)
    combined = _derive_q4(quarterly, annual)

    points = [
        {
            "period": f"{y}-Q{q}",
            "year": y,
            "quarter": q,
            "value": combined[(y, q)],
            "derived": (y, q) in derived,
        }
        for (y, q) in sorted(combined)
    ]
    return {
        "points": points,
        "label": payload.get("label"),
        "concept": payload.get("tag"),
        "derived_note": (
            "Q4 is not filed as its own quarterly fact; where marked, it is the "
            "annual figure minus Q1-Q3. A derived Q4 inherits any later "
            "restatement of the full year, and is recomputed on each refresh "
            "rather than held - so it tracks the filing, but a value read here "
            "before a restatement will differ from the same value read after."
        ),
    }


def fetch_quote(symbol: str) -> dict | None:
    """Current quote plus a one-year daily close series."""
    try:
        resp = requests.get(
            YAHOO.format(symbol=symbol),
            params={"range": "1y", "interval": "1d"},
            headers=YAHOO_HEADERS,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        result = resp.json()["chart"]["result"][0]
        meta = result["meta"]
        closes = [c for c in result["indicators"]["quote"][0]["close"] if c is not None]

        price = meta["regularMarketPrice"]
        prev = meta.get("chartPreviousClose") or price
        return {
            "symbol": symbol,
            "name": meta.get("longName") or TICKERS.get(symbol, symbol),
            "price": round(price, 2),
            "change": round(price - prev, 2),
            "change_pct": round((price - prev) / prev * 100, 2) if prev else None,
            "currency": meta.get("currency"),
            "exchange": meta.get("fullExchangeName"),
            "week52_high": meta.get("fiftyTwoWeekHigh"),
            "week52_low": meta.get("fiftyTwoWeekLow"),
            "first_trade": meta.get("firstTradeDate"),
            "series": [round(c, 2) for c in closes[-260:]],
        }
    except Exception as e:  # noqa: BLE001 - a dead quote must not fail the run
        print(f"  [FAIL] quote {symbol}: {e}")
        return None


def fetch() -> dict:
    """Quotes for both tickers plus Tesla's filed quarterly series."""
    quotes = {}
    for symbol in TICKERS:
        q = fetch_quote(symbol)
        if q:
            quotes[symbol] = q
            print(f"  [OK]   {symbol}: {q['price']} ({q['change_pct']:+.2f}%)")

    series = {}
    for key, names in CONCEPTS.items():
        try:
            payload = _fetch_concept(CIKS["TSLA"], names)
            if payload:
                s = _series_from_concept(payload)
                series[key] = s
                print(f"  [OK]   TSLA {key}: {len(s['points'])} quarters filed")
        except Exception as e:  # noqa: BLE001
            print(f"  [FAIL] TSLA {key}: {e}")

    return {
        "quotes": quotes,
        "series": series,
        "caveat": {
            "SPCX": (
                "SpaceX listed in June 2026. The price series does not yet cover "
                "a full earnings cycle, so technical levels drawn from it are weak "
                "evidence."
            )
        },
    }
