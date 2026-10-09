"""Feed registry for SpaceX, Tesla and the smaller Musk companies.

Two mechanisms, both borrowed from clintrialist-report's ``feeds.py``:

* Publisher RSS where one exists and works.
* Google News ``site:`` searches as synthetic feeds where it does not. Negative
  terms trim the obvious noise before it ever reaches the scorer.

Query design follows the rationale already written down in
``02-Areas/finance/gfinance2/src/news/monitor.py``: a bare ticker is useless as
a search term, so market queries pair the company name with context words.
"""

from __future__ import annotations

from urllib.parse import quote


def _gnews(query: str) -> str:
    """Google News RSS search URL. ``query`` is written plainly and encoded here."""
    return f"https://news.google.com/rss/search?q={quote(query)}&hl=en-US&gl=US&ceid=US:en"


SECTIONS = {
    "spacex": "SpaceX",
    "tesla": "Tesla",
    "ventures": "xAI · X · Neuralink · Boring",
    "market": "Markets & Filings",
}

# Fetched in this order, and deduped against a shared `seen` set in that order,
# so a story that could land in two sections stays in the more specific one.
SECTION_ORDER = ["spacex", "tesla", "ventures", "market"]

SPACEX_FEEDS = [
    {"name": "SpaceX", "url": _gnews("site:spacex.com")},
    {"name": "NASASpaceflight", "url": "https://www.nasaspaceflight.com/feed/"},
    {"name": "Spaceflight Now", "url": "https://spaceflightnow.com/feed/"},
    {"name": "Ars Technica Space", "url": "https://arstechnica.com/space/feed/"},
    {"name": "Space.com", "url": "https://www.space.com/feeds/all"},
    {"name": "Starship", "url": _gnews('"SpaceX" AND (Starship OR "Super Heavy" OR Raptor)')},
    {
        "name": "Starlink",
        "url": _gnews('"Starlink" AND (satellite OR launch OR broadband OR subscribers)'),
    },
    {
        "name": "Falcon",
        "url": _gnews('"SpaceX" AND (Falcon OR Dragon OR booster OR "static fire")'),
    },
]

TESLA_FEEDS = [
    {"name": "Teslarati", "url": "https://www.teslarati.com/feed/"},
    {"name": "Electrek", "url": "https://electrek.co/feed/"},
    {"name": "InsideEVs", "url": "https://insideevs.com/rss/articles/all/"},
    {"name": "Not a Tesla App", "url": "https://www.notateslaapp.com/rss"},
    {"name": "Tesla", "url": _gnews("site:tesla.com")},
    {
        "name": "Autonomy",
        "url": _gnews('"Tesla" AND (robotaxi OR Cybercab OR FSD OR "full self-driving")'),
    },
    # Optimus gets its own pair rather than sharing the Autonomy query: one for
    # programme news, one for what the robot can actually do. Splitting them
    # stops capability demos being crowded out by production and funding stories.
    {
        "name": "Optimus",
        "url": _gnews(
            '"Optimus" AND (Tesla OR Musk) AND (robot OR humanoid OR production OR factory)'
        ),
    },
    {
        "name": "Optimus Features",
        "url": _gnews(
            '("Optimus" OR "Tesla bot") AND (demo OR capability OR hand OR walking OR "Gen 3" OR training OR skills)'
        ),
    },
    {
        "name": "Humanoids",
        "url": _gnews('humanoid robot AND (Tesla OR Optimus OR Figure OR "1X" OR Unitree)'),
    },
    {
        "name": "Production",
        "url": _gnews('"Tesla" AND (Gigafactory OR production OR deliveries OR Cybertruck)'),
    },
    {"name": "Energy", "url": _gnews('"Tesla" AND (Megapack OR Powerwall OR "energy storage")')},
]

# The smaller companies share one column. None has a trade press of its own, so
# all four are Google News searches. "X" alone is unsearchable, so the X query
# names its products instead of the company. xAI and X became SpaceX
# subsidiaries in 2026, but they are listed here rather than under SpaceX so
# that rockets and chatbots do not compete for one column's 18 slots.
VENTURES_FEEDS = [
    {"name": "xAI", "url": _gnews('"xAI" AND (Grok OR Colossus OR Musk OR model)')},
    {"name": "Grok", "url": _gnews('"Grok" AND (xAI OR release OR model OR Musk)')},
    {"name": "X", "url": _gnews('"X Corp" OR "X Money" OR "XChat" OR "X Payments"')},
    {"name": "Neuralink", "url": _gnews('"Neuralink" OR "Blindsight"')},
    {
        "name": "Boring",
        "url": _gnews('"Boring Company" OR "Vegas Loop" OR "Music City Loop"'),
    },
]

MARKET_FEEDS = [
    # Ticker-plus-context, not bare tickers - see module docstring.
    {
        "name": "TSLA",
        "url": _gnews('"Tesla" AND (stock OR earnings OR shares OR revenue OR guidance)'),
    },
    {
        "name": "SPCX",
        "url": _gnews(
            '"SpaceX" AND (stock OR IPO OR shares OR earnings OR "lock-up" OR valuation)'
        ),
    },
    {
        "name": "Musk",
        "url": _gnews(
            '"Elon Musk" AND (Tesla OR SpaceX) AND (SEC OR board OR compensation OR stake)'
        ),
    },
]

FEEDS_BY_SECTION = {
    "spacex": SPACEX_FEEDS,
    "tesla": TESLA_FEEDS,
    "ventures": VENTURES_FEEDS,
    "market": MARKET_FEEDS,
}

# How many stories each section shows.
SECTION_LIMITS = {"spacex": 18, "tesla": 18, "ventures": 18, "market": 12}

# Dropped if the substring appears anywhere in the title (case-insensitive).
# These are the recurring shapes of SEO filler that clear the relevance scorer
# on keyword alone.
EXCLUDE_TITLES = [
    "best tesla accessories",
    "deals of the day",
    "coupon",
    "promo code",
    "black friday",
    "horoscope",
    "according to reddit",
    "you won't believe",
]


# Every story on this page must be about one of the companies. The trade
# feeds (Electrek, InsideEVs, Space.com) carry the whole sector, so without this
# the page fills with BYD sales events and Uber robotaxi launches - real news,
# wrong page.
RELEVANCE = (
    r"\b(Tesla|SpaceX|Musk|Starlink|Starship|Falcon|Dragon|Optimus|Cybertruck|"
    r"Cybercab|Megapack|Powerwall|Supercharger|Gigafactory|Megafactory|Starbase|"
    r"Raptor|TSLA|SPCX|Roadster|Semi|FSD|Autopilot|Starshield|"
    # The lookbehind stops "Karbon-X Corp" passing as X: a hyphen is a \b.
    r"xAI|Grok|Colossus|(?<![\w-])X Corp|X Money|XChat|Neuralink|Blindsight|"
    r"Boring Company|Vegas Loop|Music City Loop)\b"
)
