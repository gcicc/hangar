---
name: hangar
type: maintain
category: building
tier: 02-Maintain
updated: 2026-09-12
note: moved from 01-Active-Projects 2026-09-07
---
# HANGAR — next steps

**Type:** Maintain (moved from 01-Active-Projects 2026-09-07)
**Phase:** 1 — working page, Tier 0 local
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

Give the page a remote. The repo is local-only on branch `master`, so the
refresh workflow described below has never run. See blocker 3.

## Blockers

Three decisions are Greg's:

1. **Where the X collector runs.** X needs a real browser, which GitHub Actions
   can't give cheaply. Default assumed: an optional local Windows scheduled task
   writing `data/x_posts.json`, same split as GCourses and gfinance2. The board
   degrades to second-hand claims and says so when X is absent. `data/x_posts.json`
   still holds the manual seed from 2026-09-05, so the board is currently
   rendering `@elonmusk collected 148h ago — STALE` in red.
2. **Rule 19a freeze gate.** This is a new project bootstrap and trips the gate.
   Recommend explicit unfreeze.
3. **No git remote.** `git remote -v` is empty and the branch is `master`, while
   `.github/workflows/refresh.yml` targets `main`. The scheduled refresh cannot
   fire and Pages has nothing to serve, which is why the page is absent from the
   Web Ledger. Needs a GitHub repo created, the branch reconciled with the
   workflow, and Pages pointed at `/docs`.

## What keeps this current

`.github/workflows/refresh.yml`, cron `0 */2 * * *`, commits `docs/` and `data/`
back to main. Pages serves from `/docs` on the branch — never a Pages build
workflow (`project-management/docs/PUBLISHING-PROTOCOL.md`).

Per-source cadence is enforced by `max_age` in `hangar/cache.py`, so the job
fires twelve times a day while CelesTrak is fetched four times and Supercharger
data once a week. Every panel prints its own `fetched_at`; `data/status.json`
records per-source last success and last error, and the footer renders anything
stale in red.

## Reach and finish

Tier 0 (local) now, and blocked there by the missing remote (blocker 3).
Target Tier 2 (Pages) after the Crafted pass.

**Tier 1 (Artifact) is not available to this page** and never will be: the map
needs tile requests, which the Artifact CSP blocks silently — the map renders and
the tiles never arrive. That is a property of tiles, not of which CDN serves
Leaflet.
