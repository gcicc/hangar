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

Coordinates are to roughly the site, not the property line. They are for putting
a dot on a world map, not for navigation.
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
        "lat": 33.9207,
        "lon": -118.3277,
        "status": "operating",
    },
    {
        "co": "SpaceX",
        "name": "Starbase",
        "kind": "Starship production and launch",
        "lat": 25.9971,
        "lon": -97.1554,
        "status": "operating",
    },
    {
        "co": "SpaceX",
        "name": "McGregor",
        "kind": "Engine test",
        "lat": 31.4046,
        "lon": -97.4636,
        "status": "operating",
    },
    {
        "co": "SpaceX",
        "name": "Redmond",
        "kind": "Starlink satellite production",
        "lat": 47.6740,
        "lon": -122.1215,
        "status": "operating",
    },
    {
        "co": "SpaceX",
        "name": "Bastrop",
        "kind": "Starlink terminal production",
        "lat": 30.1105,
        "lon": -97.3153,
        "status": "operating",
    },
    {
        "co": "SpaceX",
        "name": "Roberts Road",
        "kind": "Starship facility, KSC",
        "lat": 28.5860,
        "lon": -80.6550,
        "status": "building",
    },
    {
        "co": "SpaceX",
        "name": "Starbase Louisiana",
        "kind": "Spaceport, 125,000 acres",
        "lat": 29.6400,
        "lon": -92.4600,
        "status": "announced",
        "note": "Pecan Island, Vermilion Parish. $100B committed; construction 2027, first launch targeted 2029.",
        "source": "https://fortune.com/2026/08/27/spacex-largest-spaceport-100-billion-louisiana-expansion/",
    },
    # Terafab is a Tesla/SpaceX joint venture, so it is filed under neither
    # exclusively; listed as SpaceX because the regulatory filing is SpaceX's.
    {
        "co": "SpaceX",
        "name": "Terafab",
        "kind": "Semiconductor fab (Tesla/SpaceX JV)",
        "lat": 30.5400,
        "lon": -95.9800,
        "status": "building",
        "note": "Grimes County, Texas. $16.8B first phase.",
        "source": "https://www.statesman.com/business/article/elon-musk-terafab-spacex-grimes-county-22375537.php",
    },
    # --- Tesla ---
    {
        "co": "Tesla",
        "name": "Fremont",
        "kind": "Vehicle assembly",
        "lat": 37.4931,
        "lon": -121.9440,
        "status": "operating",
    },
    {
        "co": "Tesla",
        "name": "Giga Texas",
        "kind": "Vehicle assembly / HQ",
        "lat": 30.2214,
        "lon": -97.6169,
        "status": "operating",
    },
    {
        "co": "Tesla",
        "name": "Giga Berlin",
        "kind": "Vehicle assembly",
        "lat": 52.3900,
        "lon": 13.7986,
        "status": "operating",
    },
    {
        "co": "Tesla",
        "name": "Giga Shanghai",
        "kind": "Vehicle assembly",
        "lat": 30.9600,
        "lon": 121.8400,
        "status": "operating",
    },
    {
        "co": "Tesla",
        "name": "Giga Nevada",
        "kind": "Cells, packs, drive units",
        "lat": 39.5380,
        "lon": -119.4430,
        "status": "operating",
    },
    {
        "co": "Tesla",
        "name": "Buffalo",
        "kind": "Solar / Supercharger hardware",
        "lat": 42.8300,
        "lon": -78.8200,
        "status": "operating",
    },
    {
        "co": "Tesla",
        "name": "Lathrop Megafactory",
        "kind": "Megapack production",
        "lat": 37.8220,
        "lon": -121.2760,
        "status": "operating",
    },
    {
        "co": "Tesla",
        "name": "Shanghai Megafactory",
        "kind": "Megapack production",
        "lat": 30.8900,
        "lon": 121.8100,
        "status": "operating",
    },
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
