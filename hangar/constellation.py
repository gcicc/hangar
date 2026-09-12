"""Starlink constellation: current fleet, orbital shells, and growth over time.

Two different numbers get conflated constantly and this module keeps them apart,
because the gap between them is the interesting part:

* **In orbit now** - counted directly from CelesTrak's GP set. Exact.
* **Cumulatively launched** - reconstructed from the international designator
  (``OBJECT_ID``, e.g. ``2019-029A``, whose prefix is the launch year). This
  counts only satellites *still in orbit*, so it is survivorship-biased: it
  cannot see anything already deorbited.

Reading the second as "constellation size over time" would understate every
past year, so the page labels it as what it is - the current fleet broken down
by the year each satellite went up - and takes the honest growth curve from
launch history in ``launches.py`` instead.

A third, unbiased series accumulates going forward in ``history.py``: each run
records the observed in-orbit count, so after a few months there is a directly
measured curve that needs no reconstruction at all.
"""

from __future__ import annotations

from collections import Counter

import requests

from hangar.cache import NotModified

GP_URL = "https://celestrak.org/NORAD/elements/gp.php"
HEADERS = {"User-Agent": "HANGAR/0.1 (+https://github.com/gcicc/hangar)"}
TIMEOUT = 60

# Satellites carried in the committed JSON for the map animation. The full set
# is ~8,000 objects; committing that daily would bloat git history fast, and the
# browser cannot usefully animate all of it either.
ANIMATION_SAMPLE = 600

# Starlink shell boundaries by mean motion (revolutions/day). Mean motion is a
# direct function of semi-major axis, so it separates the shells without needing
# to propagate anything.
EARTH_MU = 398600.4418  # km^3/s^2
EARTH_R = 6378.137  # km


# Altitude is derived assuming a circular orbit. Starlink's shells are very
# nearly circular, so the error is roughly +/-10 km - fine for grouping, not
# fine for implying 25 km resolution. Buckets are therefore 50 km wide.
ALTITUDE_UNCERTAINTY_KM = 10
SHELL_BUCKET_KM = 50


def _altitude_km(mean_motion_rev_per_day: float) -> float:
    """Approximate circular altitude from mean motion."""
    if mean_motion_rev_per_day <= 0:
        return 0.0
    period_s = 86400.0 / mean_motion_rev_per_day
    semi_major = (EARTH_MU * (period_s / (2 * 3.141592653589793)) ** 2) ** (1 / 3)
    return semi_major - EARTH_R


def _launch_year(object_id: str | None) -> int | None:
    """Launch year from the international designator, e.g. '2019-029A' -> 2019."""
    if not object_id or len(object_id) < 4:
        return None
    try:
        year = int(object_id[:4])
    except ValueError:
        return None
    return year if 1957 <= year <= 2100 else None


def _shell_label(alt: float, inc: float) -> str:
    """Coarse shell bucket. Labels are altitude bands, not marketing names.

    Bucketed at 50 km rather than 25 km: the underlying altitude carries about
    +/-10 km of uncertainty, and narrower bands would sort satellites into
    different shells on that noise alone.
    """
    band = round(alt / SHELL_BUCKET_KM) * SHELL_BUCKET_KM
    return f"~{band:.0f} km / {inc:.0f}°"


def fetch(group: str = "starlink") -> dict:
    """Fetch the GP set and derive counts, shells, growth, and an animation sample."""
    resp = requests.get(
        GP_URL, params={"GROUP": group, "FORMAT": "json"}, headers=HEADERS, timeout=TIMEOUT
    )

    # CelesTrak answers a repeat request with 403 and a plain-text body saying
    # the data has not changed since our last successful download. That is their
    # rate-limiting courtesy, not a rejection: the correct response is to keep
    # the cached copy. Treating it as an error would mark a healthy source
    # broken every time we polled faster than their 2-hour update cycle.
    if resp.status_code == 403 and "has not updated" in resp.text:
        raise NotModified(resp.text.strip().replace("\n", " "))

    resp.raise_for_status()
    objects = resp.json()
    print(f"  [OK]   CelesTrak {group}: {len(objects)} objects")

    by_year: Counter = Counter()
    shells: Counter = Counter()
    altitudes: list[float] = []

    for o in objects:
        year = _launch_year(o.get("OBJECT_ID"))
        if year:
            by_year[year] += 1
        mm = o.get("MEAN_MOTION")
        inc = o.get("INCLINATION")
        if mm and inc:
            alt = _altitude_km(float(mm))
            altitudes.append(alt)
            if 200 < alt < 2000:
                shells[_shell_label(alt, float(inc))] += 1

    years = sorted(by_year)
    cumulative = []
    running = 0
    for y in years:
        running += by_year[y]
        cumulative.append(running)

    # Evenly spaced sample so the animation shows the whole constellation's
    # geometry rather than one dense corner of it.
    step = max(1, len(objects) // ANIMATION_SAMPLE)
    sample = [
        {
            "name": o.get("OBJECT_NAME"),
            "id": o.get("NORAD_CAT_ID"),
            "epoch": o.get("EPOCH"),
            "mm": o.get("MEAN_MOTION"),
            "ecc": o.get("ECCENTRICITY"),
            "inc": o.get("INCLINATION"),
            "raan": o.get("RA_OF_ASC_NODE"),
            "argp": o.get("ARG_OF_PERICENTER"),
            "ma": o.get("MEAN_ANOMALY"),
            "bstar": o.get("BSTAR"),
        }
        for o in objects[::step][:ANIMATION_SAMPLE]
    ]

    altitudes.sort()
    return {
        "in_orbit": len(objects),
        "group": group,
        "shells": [
            {"shell": s, "count": n} for s, n in sorted(shells.items(), key=lambda x: -x[1])[:8]
        ],
        "shells_caveat": (
            f"Altitude is derived from mean motion assuming a circular orbit, "
            f"good to about +/-{ALTITUDE_UNCERTAINTY_KM} km, and grouped into "
            f"{SHELL_BUCKET_KM} km bands. Counts are of the current fleet, not "
            "of any historical shell population."
        ),
        "by_launch_year": {
            "years": years,
            "added": [by_year[y] for y in years],
            "cumulative": cumulative,
            "caveat": (
                "Current fleet grouped by the year each satellite launched. "
                "Satellites already deorbited are not in this data, so earlier "
                "years understate what was in orbit at the time."
            ),
        },
        "altitude_median_km": round(altitudes[len(altitudes) // 2], 1) if altitudes else None,
        "sample": sample,
        "sample_note": f"{len(sample)} of {len(objects)} objects, evenly sampled",
    }
