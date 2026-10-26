"""Every payload ever put into Earth orbit, for the globe's time-lapse.

Three catalogues are joined, each for what it alone does well:

* **CelesTrak SATCAT** - the object list: launch and decay dates, owner, launch
  site, and the last known apogee, perigee and inclination.
* **GCAT** (Jonathan McDowell, planet4589.org) ``psatcat`` - mission category and
  class (``D`` = defense). SATCAT has no purpose field at all.
* **GCAT** ``launch`` - launch vehicle and agency, which is what says whether
  SpaceX flew it. SATCAT records the satellite's owner, not who launched it.

Debris and rocket bodies are excluded: the subject is satellites. So are objects
that left Earth orbit (lunar, planetary, heliocentric).

**Positions are not historical.** Free element-set archives do not go back to
1957, so the page flies each satellite on an orbit with its real inclination,
apogee and perigee but a synthetic node and phase. The page says so. Satellites
still operating get their real elements from ``constellation.fetch_fleet``.

The payload is columnar - parallel arrays, dates as day numbers - because ~28,000
objects as a list of dicts would be roughly three times the size.
"""

from __future__ import annotations

import csv
import io
import re
from collections import Counter
from datetime import UTC, date, datetime, timedelta

import requests

SATCAT_URL = "https://celestrak.org/pub/satcat.csv"
PSATCAT_URL = "https://planet4589.org/space/gcat/tsv/cat/psatcat.tsv"
LAUNCH_URL = "https://planet4589.org/space/gcat/tsv/launch/launch.tsv"
HEADERS = {"User-Agent": "HANGAR/0.1 (+https://github.com/gcicc/hangar)"}
TIMEOUT = 120

# Day numbers in the payload count from here; it predates Sputnik 1.
EPOCH = date(1957, 1, 1)

# Launch vehicles counted as SpaceX. Matched on GCAT's LV_Type prefix; "Viper
# Falcon" and "FalconLaunch" are unrelated sounding rockets, hence no bare
# "Falcon".
SPACEX_LV_PREFIXES = ("Falcon 1", "Falcon 9", "Falcon Heavy", "Starship")

# Owner groups, in legend order. SpaceX is split out of the US by satellite name
# (Starlink), because SATCAT records Starlink's owner as plain "US".
GROUPS = ["SpaceX", "US", "USSR / Russia", "China", "Europe", "Japan", "India", "Other"]

# SATCAT owner codes per group. US-based commercial operators are coded by
# company in SATCAT (Globalstar, Orbcomm, ...) and are folded into the US.
_OWNER_GROUP = {
    "US": "US",
    "GLOB": "US",
    "ORB": "US",
    "IRID": "US",
    "USBZ": "US",
    "CIS": "USSR / Russia",
    "PRC": "China",
    "JPN": "Japan",
    "IND": "India",
}
_EUROPE = {
    "ESA",
    "ESRO",
    "EUTE",
    "EUME",
    "SES",
    "UK",
    "FR",
    "GER",
    "FGER",
    "IT",
    "FRIT",
    "SPN",
    "NETH",
    "BEL",
    "LUXE",
    "SWTZ",
    "ASRA",
    "SWED",
    "NOR",
    "DEN",
    "FIN",
    "POL",
    "CZCH",
    "SVK",
    "SVN",
    "HUN",
    "ROM",
    "BUL",
    "GREC",
    "POR",
    "IRL",
    "EST",
    "LTU",
    "LAT",
    "HRV",
    "MNE",
    "MCO",
    "VAT",
    "NATO",
}

# Purpose buckets, in legend order; each gets one glyph on the globe.
PURPOSES = [
    "Communications",
    "Navigation",
    "Earth observation",
    "Science & crewed",
    "Military",
    "Other",
]

# GCAT category -> purpose. Categories carry '*' (uncertain) and '?' markers and
# can be compound ("COM/MET-RO"); the first component decides.
_CATEGORY_PURPOSE = {
    "COM": "Communications",
    "NAV": "Navigation",
    "IMG": "Earth observation",
    "IMG-R": "Earth observation",
    "MET": "Earth observation",
    "MET-RO": "Earth observation",
    "EOSCI": "Earth observation",
    "GEOD": "Earth observation",
    "MGRAV": "Earth observation",
    "SCI": "Science & crewed",
    "AST": "Science & crewed",
    "PLAN": "Science & crewed",
    "BIO": "Science & crewed",
    "SS": "Science & crewed",
    "MICRO": "Science & crewed",
    "SIG": "Military",
    "EW": "Military",
    "WEAPON": "Military",
    "TARG": "Military",
}

# SATCAT launch-site code -> (name, lat, lon, approximate). Approximate rows are
# sea, air or submarine launch areas with no fixed pad; the streak starts from a
# representative point in that area.
SITES = {
    "AFETR": ("Cape Canaveral", 28.49, -80.58, False),
    "AFWTR": ("Vandenberg", 34.73, -120.57, False),
    "TYMSC": ("Baikonur", 45.92, 63.34, False),
    "PLMSC": ("Plesetsk", 62.93, 40.58, False),
    "FRGUI": ("Kourou", 5.24, -52.77, False),
    "JSC": ("Jiuquan", 40.96, 100.29, False),
    "TAISC": ("Taiyuan", 38.85, 111.61, False),
    "SRILR": ("Sriharikota", 13.73, 80.23, False),
    "VOSTO": ("Vostochny", 51.88, 128.33, False),
    "XICLF": ("Xichang", 28.25, 102.03, False),
    "WSC": ("Wenchang", 19.61, 110.95, False),
    "RLLB": ("Rocket Lab Mahia", -39.26, 177.86, False),
    "TANSC": ("Tanegashima", 30.40, 130.97, False),
    "WLPIS": ("Wallops", 37.83, -75.49, False),
    "YSLA": ("Yellow Sea launch area", 34.90, 121.20, True),
    "KYMSC": ("Kapustin Yar", 48.58, 45.72, False),
    "DLS": ("Dombarovsky", 51.09, 59.84, False),
    "SEAL": ("Sea Launch, Pacific", 0.00, -154.00, True),
    "WRAS": ("Western Range airspace", 34.60, -121.50, True),
    "ERAS": ("Eastern Range airspace", 28.50, -79.50, True),
    "NSC": ("Naro", 34.43, 127.54, False),
    "KODAK": ("Kodiak", 57.44, -152.34, False),
    "STARB": ("Starbase", 25.99, -97.15, False),
    "SCSLA": ("South China Sea launch area", 21.00, 112.00, True),
    "YAVNE": ("Palmachim", 31.88, 34.68, False),
    "SNMLP": ("San Marco, Kenya", -2.94, 40.21, False),
    "SEMLS": ("Semnan", 35.23, 53.92, False),
    "ANDSP": ("Andøya", 69.29, 16.02, False),
    "SVOBO": ("Svobodny", 51.80, 128.40, False),
    "SMTS": ("Shahroud", 36.20, 55.33, False),
    "HGSTR": ("Hammaguir", 30.88, -3.06, False),
    "YUN": ("Sohae", 39.66, 124.71, False),
    "SUBL": ("Barents Sea submarine", 70.00, 35.00, True),
    "WOMRA": ("Woomera", -30.95, 136.50, False),
    "KWAJ": ("Kwajalein", 9.05, 167.74, False),
    "CAS": ("Canary Islands airspace", 27.90, -15.50, True),
    "JJSLA": ("Jeju sea launch area", 33.00, 126.50, True),
    "KSCUT": ("Uchinoura", 31.25, 131.08, False),
}


def _day(text: str | None) -> int | None:
    """'2019-05-24' -> days since EPOCH; None for a blank or malformed date."""
    if not text:
        return None
    try:
        return (date.fromisoformat(text.strip()[:10]) - EPOCH).days
    except ValueError:
        return None


def owner_group(owner: str, name: str) -> str:
    """Owner group for a SATCAT owner code; Starlink is SpaceX's own."""
    if name.upper().startswith("STARLINK"):
        return "SpaceX"
    if owner in _OWNER_GROUP:
        return _OWNER_GROUP[owner]
    return "Europe" if owner in _EUROPE else "Other"


def purpose(category: str | None, cls: str | None) -> str:
    """Purpose bucket from GCAT category and class.

    Defense-class payloads count as military whatever their category, except
    navigation: GPS, GLONASS and BeiDou are defense-run but are the world's
    navigation systems, and "Military" would hide that.
    """
    head = (category or "").strip().split("/")[0].rstrip("*?")
    bucket = _CATEGORY_PURPOSE.get(head, "Other")
    if "D" in (cls or "") and bucket != "Navigation":
        return "Military"
    return bucket


def _gcat_rows(text: str) -> list[dict]:
    """Parse a GCAT TSV: '#'-prefixed header line, '#' comment lines, padded cells."""
    lines = text.splitlines()
    header = [h.strip() for h in lines[0].lstrip("#").split("\t")]
    rows = []
    for line in lines[1:]:
        if not line or line.startswith("#"):
            continue
        cells = [c.strip() for c in line.split("\t")]
        rows.append(dict(zip(header, cells, strict=False)))
    return rows


# "1957 ALP"; past omega the alphabet restarts with a prefix, "1961 A BET".
_GREEK_TAG = re.compile(r"^\d{4} (?:[A-Z] )?[A-Z]{2,3}\d*$")


def _gcat_date(text: str) -> str | None:
    """GCAT '1957 Oct  4 1928:34' -> '1957-10-04'."""
    parts = text.split()
    if len(parts) < 3:
        return None
    try:
        when = datetime.strptime(" ".join(parts[:3]), "%Y %b %d").replace(tzinfo=UTC)
        return when.date().isoformat()
    except ValueError:
        return None


def _vehicle(lv_of: dict, tag: str, launched: int) -> tuple[str, bool]:
    """Launch vehicle for a SATCAT launch tag, falling back to the launch date.

    The date fallback covers the Greek-letter era and allows a day either way:
    SATCAT and GCAT disagree by a day on some early launches near midnight UTC.
    """
    if tag in lv_of:
        return lv_of[tag]
    for shift in (0, -1, 1):
        key = f"date:{(EPOCH + timedelta(days=launched + shift)).isoformat()}"
        if key in lv_of:
            return lv_of[key]
    return ("", False)


def _get(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.content.decode("utf-8", errors="replace")


def build(satcat_csv: str, psatcat_tsv: str, launch_tsv: str) -> dict:
    """Join the three catalogues into the columnar payload. Pure; no network."""
    meta: dict[int, tuple[str, str]] = {}
    for r in _gcat_rows(psatcat_tsv):
        jcat = r.get("JCAT", "")
        if jcat.startswith("S") and jcat[1:].isdigit():
            meta[int(jcat[1:])] = (r.get("Category", ""), r.get("Class", ""))

    lv_of: dict[str, tuple[str, bool]] = {}
    for r in _gcat_rows(launch_tsv):
        tag, lv = r.get("Launch_Tag", ""), r.get("LV_Type", "")
        entry = (lv, lv.startswith(SPACEX_LV_PREFIXES))
        lv_of[tag] = entry
        # Before 1963 GCAT keeps the original Greek-letter tags ("1957 ALP"),
        # while SATCAT renumbered them "1957-001". Those join on launch date.
        if _GREEK_TAG.match(tag):
            when = _gcat_date(r.get("Launch_Date", ""))
            if when:
                lv_of.setdefault(f"date:{when}", entry)

    owners: list[str] = []
    cats: list[str] = []
    lvs: list[str] = []
    site_codes: list[str] = []
    index: dict[tuple[str, str], int] = {}

    def intern(table: list[str], kind: str, value: str) -> int:
        key = (kind, value)
        if key not in index:
            index[key] = len(table)
            table.append(value)
        return index[key]

    launch_idx: dict[str, int] = {}
    launch = {"tag": [], "day": [], "site": [], "lv": [], "spx": []}
    sat = {k: [] for k in ("id", "name", "l", "dec", "inc", "apo", "per", "g", "o", "p", "c")}
    skipped = Counter()
    unmapped_sites = Counter()

    for r in csv.DictReader(io.StringIO(satcat_csv)):
        if r.get("OBJECT_TYPE") != "PAY":
            continue
        if r.get("ORBIT_CENTER") != "EA":
            skipped["left Earth orbit"] += 1
            continue
        launched = _day(r.get("LAUNCH_DATE"))
        try:
            apo, per, inc = float(r["APOGEE"]), float(r["PERIGEE"]), float(r["INCLINATION"])
        except (KeyError, TypeError, ValueError):
            skipped["no orbit data"] += 1
            continue
        if launched is None:
            skipped["no launch date"] += 1
            continue

        norad = int(r["NORAD_CAT_ID"])
        name = r.get("OBJECT_NAME", "").strip()
        tag = (r.get("OBJECT_ID") or "")[:8]
        site = r.get("LAUNCH_SITE", "").strip()
        if site not in SITES:
            unmapped_sites[site] += 1

        if tag not in launch_idx:
            lv, spx = _vehicle(lv_of, tag, launched)
            launch_idx[tag] = len(launch["tag"])
            launch["tag"].append(tag)
            launch["day"].append(launched)
            launch["site"].append(intern(site_codes, "site", site))
            launch["lv"].append(intern(lvs, "lv", lv))
            launch["spx"].append(1 if spx else 0)

        category, cls = meta.get(norad, ("", ""))
        decayed = _day(r.get("DECAY_DATE"))
        owner = r.get("OWNER", "").strip()

        sat["id"].append(norad)
        # Starlink is ~45% of the catalogue; '*' stands for the prefix.
        sat["name"].append("*" + name[9:] if name.startswith("STARLINK-") else name)
        sat["l"].append(launch_idx[tag])
        sat["dec"].append(-1 if decayed is None else decayed)
        sat["inc"].append(round(inc, 1))
        sat["apo"].append(round(apo))
        sat["per"].append(round(per))
        sat["g"].append(GROUPS.index(owner_group(owner, name)))
        sat["o"].append(intern(owners, "owner", owner))
        sat["p"].append(PURPOSES.index(purpose(category, cls)))
        sat["c"].append(intern(cats, "cat", category or "-"))

    in_orbit = sum(1 for d in sat["dec"] if d < 0)
    unclassified = sum(1 for c in sat["c"] if cats[c] == "-")
    spx_launches = sum(launch["spx"])

    print(
        f"  [OK]   catalogue: {len(sat['id'])} payloads, {in_orbit} still in orbit, "
        f"{len(launch['tag'])} launches ({spx_launches} SpaceX), "
        f"{unclassified} without a GCAT category"
    )
    if unmapped_sites:
        print(f"  [WARN] launch sites with no coordinates: {dict(unmapped_sites)}")

    return {
        "epoch": EPOCH.isoformat(),
        "groups": GROUPS,
        "purposes": PURPOSES,
        "owners": owners,
        "cats": cats,
        "lvs": lvs,
        "sites": [
            [code, *SITES[code]] if code in SITES else [code, code, None, None, True]
            for code in site_codes
        ],
        "launch": launch,
        "sat": sat,
        "counts": {
            "payloads": len(sat["id"]),
            "in_orbit": in_orbit,
            "launches": len(launch["tag"]),
            "spacex_launches": spx_launches,
            "unclassified": unclassified,
            "skipped": dict(skipped),
        },
        "caveat": (
            "Payloads only; debris and rocket bodies are excluded. Launches are those "
            "that put at least one payload in Earth orbit. Purpose is GCAT's mission "
            "category. Historical positions are illustrative: real inclination, "
            "apogee and perigee, synthetic node and phase."
        ),
    }


def fetch() -> dict:
    """Download the three catalogues and build the payload."""
    return build(_get(SATCAT_URL), _get(PSATCAT_URL), _get(LAUNCH_URL))
