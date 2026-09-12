---
name: hangar
type: maintain
category: building
tier: 02-Maintain
updated: 2026-09-12
url: https://gcicc.github.io/hangar/
note: moved from 01-Active-Projects 2026-09-07
---
# HANGAR — next steps

**Type:** Maintain (moved from 01-Active-Projects 2026-09-07)
**Phase:** 2 — published, Tier 2 (GitHub Pages)
**Started:** 2026-09-05
**Capability:** A single page tracking SpaceX and Tesla as *cadence machines* —
stated ambition against measured reality, refreshed on a schedule.

## Where it stands

`python run.py` builds `docs/index.html` from six sources, each on its own
refresh cadence. 31 tests pass, ruff clean. Last full build 2026-09-12.

Working now:

| Panel | Source | State |
|---|---|---|
| Precision clock / next launch | Launch Library 2 | Falcon 9 / O3b mPower 11-13, NET 2026-09-13 18:49Z, MIN precision |
| Manifest | Launch Library 2 | 29 scheduled, 20 upcoming + 200 previous fetched |
| Range map | LL2 pads + `sites.py` | 49 pads, 26 facilities, 8,915 Supercharger sites (84,102 stalls), 4 toggleable layers |
| Commitments board — TRACKED lane | curated + live metric | 4 tracked, all currently UNMEASURED |
| Commitments board — CLAIMED lane | headline regex + X posts | 15 claims detected from 1,243 headlines |
| Starlink fleet + growth | CelesTrak | 11,130 in orbit, median 465.6 km, 2019–2026 curve |
| Tesla filed financials | SEC XBRL | 19 quarters revenue, 66 net income, 64 R&D |
| Quotes | Yahoo | SPCX 151.21, TSLA 365.44, 1-year series |
| Dispatch (news) | 22 RSS feeds | 48 shown from 1,243 deduped |
| Measured history | own ledger | 9 metrics, 2 observation days (2026-09-06, 2026-09-12) |

The 2026-09-06 Launch Library 429 outage has cleared. Launches, manifest, pad
map and the precision clock all populate, and `sites.py` is written and
cached weekly. Nothing is unpopulated.

## Next task

Confirm the first scheduled refresh commits cleanly. The workflow fires every
two hours on `main`; check that the bot commit lands and `docs/index.html`
updates without a push failure.

## Blockers

Two decisions are Greg's:

1. **Where the X collector runs.** X needs a real browser, which GitHub Actions
   can't give cheaply. Default assumed: an optional local Windows scheduled task
   writing `data/x_posts.json`, same split as GCourses and gfinance2. The board
   degrades to second-hand claims and says so when X is absent. `data/x_posts.json`
   still holds the manual seed from 2026-09-05, so the board is currently
   rendering `@elonmusk collected 148h ago — STALE` in red.
2. **Rule 19a freeze gate.** This is a new project bootstrap and trips the gate.
   Recommend explicit unfreeze.

Resolved 2026-09-12: the repo now has a remote at github.com/gcicc/hangar and
publishes from `/docs` on `main`.

## What keeps this current

`.github/workflows/refresh.yml`, cron `0 */2 * * *`, commits `docs/` and `data/`
back to main. The SEC contact address is supplied by the `SEC_CONTACT`
repository secret rather than hardcoded (see `hangar/financials.py`). Pages serves from `/docs` on the branch — never a Pages build
workflow (`project-management/docs/PUBLISHING-PROTOCOL.md`).

Per-source cadence is enforced by `max_age` in `hangar/cache.py`, so the job
fires twelve times a day while CelesTrak is fetched four times and Supercharger
data once a week. Every panel prints its own `fetched_at`; `data/status.json`
records per-source last success and last error, and the footer renders anything
stale in red.

## Reach and finish

Tier 2 (Pages) as of 2026-09-12: https://gcicc.github.io/hangar/

Verified on publish — the page renders, the manifest and range map populate, and
the ArcGIS basemap tiles load over HTTPS.

**Tier 1 (Artifact) is not available to this page** and never will be: the map
needs tile requests, which the Artifact CSP blocks silently — the map renders and
the tiles never arrive. That is a property of tiles, not of which CDN serves
Leaflet.
