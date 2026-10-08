"""Physical footprint: factories, plants, and the Supercharger network.

Two very different kinds of data, kept apart because their trust levels differ.

**Facilities** are a curated constant. There is no API for "where does Tesla
build cars" - the list is short, changes a few times a year, and each entry is
better carrying a source than being scraped from something that will rot. Each
records what the site *does* and its build status, which is what makes
"progress on the megafactory" answerable at all.

**Superchargers** come from supercharge.info, which is community-maintained,
free, keyless, and complete. It is also ~8,000 sites - far too many for raw
markers - so the module returns regional aggregates for the map and keeps the
totals exact. It is fetched weekly; the network does not change by the hour.

Coordinates are to the site, within ~200 m, because the globe's close-up zooms
satellite imagery to them. Each came from an OpenStreetMap feature or Wikipedia
coordinate (checked 2026-10-08). Where only a street address or a nearby place is
known, the row says so in its note and carries a lower ``zoom``, so an
approximate pin is not shown at a scale that implies precision.
"""

from __future__ import annotations

from collections import defaultdict

import requests

SUPERCHARGER_URL = "https://supercharge.info/service/supercharge/allSites"
HEADERS = {"User-Agent": "HANGAR/0.1 (+https://github.com/gcicc/hangar)"}
TIMEOUT = 60

# Grid size in degrees for aggregating Supercharger sites into map circles.
# ~5 degrees keeps continents legible without merging distinct metros into one
# meaningless blob.
GRID = 5.0

# Curated. `status` is the build state; `since` is when that state began, where
# it is known. Adding a row is a deliberate act - see README on sourcing.
FACILITIES = [
    # --- SpaceX ---
    {
        "co": "SpaceX",
        "name": "Hawthorne",
        "kind": "HQ / Falcon production",
        "lat": 33.9205,
        "lon": -118.3279,
        "status": "operating",
    },
    # The production site, not the launch mount: the launch mount is already on
    # the map as a Launch Library pad, ~3.4 km east.
    {
        "co": "SpaceX",
        "name": "Starbase",
        "kind": "Starship production (Mega Bay / Gigabay)",
        "lat": 25.9864,
        "lon": -97.1883,
        "status": "operating",
    },
    {
        "co": "SpaceX",
        "name": "McGregor",
        "kind": "Engine test",
        "lat": 31.4037,
        "lon": -97.4618,
        "status": "operating",
    },
    {
        "co": "SpaceX",
        "name": "Redmond",
        "kind": "Starlink satellite production",
        "lat": 47.6955,
        "lon": -122.0350,
        "status": "operating",
        "source": "https://cosmiclog.com/2021/04/07/spacex-expands-its-footprint-in-the-seattle-area/",
    },
    {
        "co": "SpaceX",
        "name": "Bastrop",
        "kind": "Starlink terminal production",
        "lat": 30.1569,
        "lon": -97.4065,
        "status": "operating",
    },
    {
        "co": "SpaceX",
        "name": "Roberts Road",
        "kind": "Starship facility, KSC",
        "lat": 28.5428,
        "lon": -80.6677,
        "status": "building",
        "source": "https://www.nasaspaceflight.com/2025/12/spacex-roberts-road-east-coast-starship/",
    },
    {
        "co": "SpaceX",
        "name": "Starbase Louisiana",
        "kind": "Spaceport, 125,000 acres",
        "lat": 29.6466,
        "lon": -92.4532,
        "status": "announced",
        "zoom": 12,
        "note": (
            "Pecan Island, Vermilion Parish. $100B committed; construction 2027, "
            "first launch targeted 2029. Pinned to the hamlet: no site boundary is public."
        ),
        "source": "https://fortune.com/2026/08/27/spacex-largest-spaceport-100-billion-louisiana-expansion/",
    },
    # Terafab is a Tesla/SpaceX joint venture, so it is filed under neither
    # exclusively; listed as SpaceX because the regulatory filing is SpaceX's.
    {
        "co": "SpaceX",
        "name": "Terafab",
        "kind": "Semiconductor fab (Tesla/SpaceX JV)",
        "lat": 30.6098,
        "lon": -96.0352,
        "status": "building",
        "note": "Grimes County, Texas. $16.8B first phase.",
        "source": "https://www.statesman.com/business/article/elon-musk-terafab-spacex-grimes-county-22375537.php",
    },
    # Where it started: all five Falcon 1 flights, 2006-2009. The islet is ~8
    # acres, so its centre is within ~150 m of the pad.
    {
        "co": "SpaceX",
        "name": "Omelek Island",
        "kind": "Falcon 1 launch site, Kwajalein Atoll",
        "lat": 9.0485,
        "lon": 167.7430,
        "status": "historic",
        "zoom": 16,
        "note": "All five Falcon 1 launches, 2006-2009, including the first privately developed liquid-fuel rocket to reach orbit (Flight 4, 2008).",
        "source": "https://en.wikipedia.org/wiki/Omelek_Island",
    },
    # --- Tesla ---
    {
        "co": "Tesla",
        "name": "Fremont",
        "kind": "Vehicle assembly",
        "lat": 37.4935,
        "lon": -121.9436,
        "status": "operating",
    },
    {
        "co": "Tesla",
        "name": "Giga Texas",
        "kind": "Vehicle assembly / HQ",
        "lat": 30.2219,
        "lon": -97.6188,
        "status": "operating",
    },
    {
        "co": "Tesla",
        "name": "Giga Berlin",
        "kind": "Vehicle assembly",
        "lat": 52.3972,
        "lon": 13.7948,
        "status": "operating",
    },
    {
        "co": "Tesla",
        "name": "Giga Shanghai",
        "kind": "Vehicle assembly",
        "lat": 30.8739,
        "lon": 121.7694,
        "status": "operating",
    },
    {
        "co": "Tesla",
        "name": "Giga Nevada",
        "kind": "Cells, packs, drive units",
        "lat": 39.5404,
        "lon": -119.4391,
        "status": "operating",
    },
    {
        "co": "Tesla",
        "name": "Buffalo",
        "kind": "Solar / Supercharger hardware",
        "lat": 42.8592,
        "lon": -78.8401,
        "status": "operating",
    },
    {
        "co": "Tesla",
        "name": "Lathrop Megafactory",
        "kind": "Megapack production",
        "lat": 37.7999,
        "lon": -121.2872,
        "status": "operating",
    },
    # No published coordinate found; sources place it in Lingang beside Giga
    # Shanghai. Zoomed out so an approximate pin does not pretend otherwise.
    {
        "co": "Tesla",
        "name": "Shanghai Megafactory",
        "kind": "Megapack production",
        "lat": 30.89,
        "lon": 121.81,
        "status": "operating",
        "zoom": 12,
        "note": "Location approximate: Lingang, beside Giga Shanghai.",
        "source": "https://cnevpost.com/2025/02/11/tesla-shanghai-megafactory-starts-production/",
    },
    # --- xAI and X (SpaceX subsidiaries since the February 2026 merger) ---
    {
        "co": "xAI",
        "name": "Colossus",
        "kind": "AI training data center",
        "lat": 35.0601,
        "lon": -90.1564,
        "status": "operating",
        "note": "Memphis. Former Electrolux plant.",
        "source": "https://en.wikipedia.org/wiki/Colossus_(data_center)",
    },
    {
        "co": "xAI",
        "name": "Colossus 2",
        "kind": "AI training data center",
        "lat": 34.9980,
        "lon": -90.0349,
        "status": "operating",
        "note": "Memphis (Whitehaven). First cluster online ~January 2026; expansion ongoing.",
        "source": "https://en.wikipedia.org/wiki/Colossus_(data_center)",
    },
    {
        "co": "xAI",
        "name": "Colossus 3",
        "kind": "AI data center",
        "lat": 34.9919,
        "lon": -90.0344,
        "status": "building",
        "note": "Southaven, Mississippi. Pinned by street address.",
        "source": "https://en.wikipedia.org/wiki/Colossus_(data_center)",
    },
    {
        "co": "xAI",
        "name": "Southaven power plant",
        "kind": "Gas turbine plant for Colossus",
        "lat": 34.9844,
        "lon": -90.0433,
        "status": "building",
        "note": "Permanent plant permitted March 2026. Pinned by street address.",
        "source": "https://en.wikipedia.org/wiki/Colossus_(data_center)",
    },
    {
        "co": "X",
        "name": "X HQ",
        "kind": "Corporate HQ",
        "lat": 30.1555,
        "lon": -97.4026,
        "status": "operating",
        "note": "Bastrop, Texas, per 2024 filings; not reconfirmed for 2026.",
        "source": "https://www.kxan.com/news/local/bastrop/social-media-company-x-cites-bastrop-address-as-its-official-headquarters/amp",
    },
    # --- Neuralink ---
    {
        "co": "Neuralink",
        "name": "Neuralink Fremont",
        "kind": "HQ and R&D",
        "lat": 37.5474,
        "lon": -122.0687,
        "status": "operating",
        "source": "https://en.wikipedia.org/wiki/Neuralink",
    },
    {
        "co": "Neuralink",
        "name": "Neuralink Austin",
        "kind": "Office and manufacturing campus",
        "lat": 30.2162,
        "lon": -97.5419,
        "status": "building",
        "note": "Del Valle, Texas. Status from 2024 reporting; not reconfirmed for 2026.",
        "source": "https://communityimpact.com/southwest-austin-dripping-springs/development/elon-musks-neuralink-to-expand-austin-offices/",
    },
    # --- The Boring Company ---
    {
        "co": "Boring Company",
        "name": "Boring Company HQ",
        "kind": "HQ and engineering",
        "lat": 30.1530,
        "lon": -97.4035,
        "status": "operating",
        "note": "Bastrop, Texas.",
        "source": "https://en.wikipedia.org/wiki/The_Boring_Company",
    },
    {
        "co": "Boring Company",
        "name": "Vegas Loop",
        "kind": "Passenger tunnel (Central Station, LVCC)",
        "lat": 36.1312,
        "lon": -115.1527,
        "status": "operating",
        "source": "https://en.wikipedia.org/wiki/Vegas_Loop",
    },
    # Music City Loop (Nashville) is under construction but has no published
    # portal coordinate, so it is not pinned rather than guessed.
]


def _bucket(lat: float, lon: float) -> tuple[float, float]:
    return (round(lat / GRID) * GRID, round(lon / GRID) * GRID)


def fetch() -> dict:
    """Supercharger aggregates plus the curated facility list."""
    resp = requests.get(SUPERCHARGER_URL, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    raw = resp.json()

    cells: dict[tuple, dict] = defaultdict(
        lambda: {"sites": 0, "stalls": 0, "lat": 0.0, "lon": 0.0, "regions": set()}
    )
    by_status: dict[str, int] = defaultdict(int)
    total_stalls = 0
    open_sites = 0

    for site in raw:
        status = (site.get("status") or "UNKNOWN").upper()
        by_status[status] += 1
        gps = site.get("gps") or {}
        lat, lon = gps.get("latitude"), gps.get("longitude")
        stalls = site.get("stallCount") or 0

        if status == "OPEN":
            open_sites += 1
            total_stalls += stalls
            if lat is not None and lon is not None:
                cell = cells[_bucket(lat, lon)]
                cell["sites"] += 1
                cell["stalls"] += stalls
                # Running mean, so the circle lands on the sites rather than on
                # the arbitrary centre of its grid square.
                n = cell["sites"]
                cell["lat"] += (lat - cell["lat"]) / n
                cell["lon"] += (lon - cell["lon"]) / n
                if site.get("address", {}).get("region"):
                    cell["regions"].add(site["address"]["region"])

    clusters = [
        {
            "lat": round(c["lat"], 3),
            "lon": round(c["lon"], 3),
            "sites": c["sites"],
            "stalls": c["stalls"],
            "regions": sorted(c["regions"])[:3],
        }
        for c in cells.values()
    ]
    clusters.sort(key=lambda c: -c["sites"])

    # Every site carries dateOpened, so the whole buildout is reconstructable
    # back to 2012 rather than having to be accumulated from today forward.
    # Same survivorship caveat as the Starlink fleet curve: this counts sites
    # open *now* by the year they opened, so it cannot see one that has since
    # closed, and slightly understates earlier years.
    opened_year: dict[str, int] = defaultdict(int)
    stalls_year: dict[str, int] = defaultdict(int)
    for site in raw:
        if (site.get("status") or "").upper() != "OPEN":
            continue
        opened = site.get("dateOpened")
        if not opened:
            continue
        year = opened[:4]
        opened_year[year] += 1
        stalls_year[year] += site.get("stallCount") or 0

    years = sorted(opened_year)
    cum_sites, cum_stalls, run_s, run_t = [], [], 0, 0
    for y in years:
        run_s += opened_year[y]
        run_t += stalls_year[y]
        cum_sites.append(run_s)
        cum_stalls.append(run_t)

    print(
        f"  [OK]   superchargers: {open_sites:,} open sites, "
        f"{total_stalls:,} stalls, {len(clusters)} map clusters"
    )

    return {
        "facilities": FACILITIES,
        "superchargers": {
            "open_sites": open_sites,
            "total_stalls": total_stalls,
            "by_status": dict(sorted(by_status.items(), key=lambda x: -x[1])),
            "clusters": clusters,
            "growth": {
                "years": years,
                "added": [opened_year[y] for y in years],
                "cumulative": cum_sites,
                "cumulative_stalls": cum_stalls,
                "caveat": (
                    "Sites open today, by the year each opened. A site that has "
                    "since closed is not counted, so earlier years are slightly "
                    "understated."
                ),
            },
            "note": (
                f"Open sites only, aggregated into ~{GRID:.0f}-degree cells for the map. "
                "Counts are exact; circle positions are the mean of the sites in a cell."
            ),
        },
    }
