---
name: hangar
type: maintain
category: building
tier: 02-Maintain
updated: 2026-10-08
url: https://gcicc.github.io/hangar/
note: moved from 01-Active-Projects 2026-09-07
---
# HANGAR — next steps

**Type:** Maintain (moved from 01-Active-Projects 2026-09-07)
**Phase:** 2 — published, Tier 2 (GitHub Pages)
**Started:** 2026-09-05
**Capability:** A single page tracking SpaceX and Tesla as *cadence machines* —
stated ambition against measured reality, refreshed on a schedule.

## Where this stands

`python run.py` builds `docs/index.html` from six sources, each on its own
refresh cadence. 31 tests pass, ruff clean. Last refresh 2026-09-27 21:20 UTC
(manual dispatch of the scheduled workflow).

Working now (rows marked † last read 2026-09-12; the rest 2026-09-27):

| Panel | Source | State |
|---|---|---|
| Precision clock / next launch | Launch Library 2 | Starship V3 / Flight 14 (Starlink Group 31-1), NET 2026-09-28 12:15Z, Go, MIN precision |
| Manifest | Launch Library 2 | 20 upcoming + 200 previous fetched; SpaceX 46% of sampled orbital launches |
| Range map | LL2 pads + `sites.py` | 50 pads, 16 facilities, 8,967 open Supercharger sites (84,653 stalls), 4 toggleable layers |
| Commitments board — TRACKED lane | curated + live metric | 4 tracked, all UNMEASURED † |
| Commitments board — CLAIMED lane | headline regex + X posts | 23 claims after dedupe (was 44: syndicated copies, retrospectives, third-party forecasts) |
| Starlink fleet + growth | CelesTrak | 11,131 in orbit, median 465.6 km, 2019–2026 curve |
| Tesla filed financials | SEC XBRL | 19 quarters revenue, 66 net income, 64 R&D † |
| Quotes | Yahoo | SPCX 151.21, TSLA 365.44, 1-year series † |
| Dispatch (news) | 22 RSS feeds | 48 shown from 1,243 deduped † |
| Measured history | own ledger | 9 metrics; 17 daily observations 2026-09-06 → 2026-09-27 |

The 2026-09-06 Launch Library 429 outage has cleared. Launches, manifest, pad
map and the precision clock all populate, and `sites.py` is written and
cached weekly. Nothing is unpopulated.

## Next task

Seed the TRACKED lane with sourced targets that resolve against metrics the
page already measures (`starlink_in_orbit`, `spacex_launches_12mo`,
`supercharger_sites`, `supercharger_stalls`, `people_in_space`). All 4 current
rows are UNMEASURED, so the page's thesis panel has no measured row. Each entry
needs a statement, who said it, when, and a source URL — Greg's to supply, never
from recollection. Then decide blocker 1 (X collector).

Done 2026-10-08 (other companies + globe close-up): xAI, X, Neuralink and
Boring added at light depth: a fourth Dispatch column (5 Google News queries),
claim entities, the topics AI / Neurotech / Tunnels, and 9 sourced facilities
including Omelek Island (Falcon 1, Kwajalein Atoll). Clicking a globe site, or
`/` → "Zoom → …", dives to Esri satellite imagery. All facility coordinates
were re-checked against OSM/Wikipedia. Eight were 0.6–10 km off, among them
Giga Shanghai, Bastrop, Terafab and Redmond, and Starbase now pins production
rather than the launch mount. Facilities are now read from `sites.py` at render
time, not the weekly cache. 38 tests pass.
Open from that pass: the Shanghai Megafactory coordinate is still approximate
(no published one), and Music City Loop is unpinned for the same reason. X HQ
and the Neuralink Austin status rest on 2024 sources.

Done 2026-09-27 (portal pass): hero globe with the Starlink sample propagated
in-browser (two-body + J2; median ~11 km from SGP4 at +24 h), promise horizon,
final-24h bar, masthead source lights, headline ticker, command bar (`/`),
boot sequence, HUD styling. Fixed: quote "today" was a 1-year change; claims
duplicated per outlet; stat tiles clipped at 1440px; phone overflow.

Resolved 2026-09-27: the scheduled refresh commits cleanly. 77 of 79 runs since
2026-09-12 succeeded; both failures (2026-09-13, 2026-09-24) were GitHub
returning HTTP 500 on `git push`, and the next run recovered. GitHub throttles
the `0 */2 * * *` cron: it actually fires 4–6 times a day, not 12. That is
inside every source's `max_age` except news/launches/quotes (2h), which
therefore refresh every ~4–5h in practice.

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
