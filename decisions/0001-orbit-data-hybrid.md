# 0001 — Orbit data for the globe time-lapse: weekly committed files plus live upgrade

- **Status:** accepted
- **Date:** 2026-10-26
- **Decided by:** Greg

## Context

The globe time-lapse (1957 → today) needs two datasets:

- The **catalogue** of every Earth-orbit payload: SATCAT joined to GCAT. 1.5 MB raw, 350 KB gzipped.
- **Element sets** for every operating satellite: CelesTrak `active`. 1.1 MB raw, 345 KB gzipped.

The refresh workflow commits `data/` and `docs/` every 2 hours, and git keeps every version.
Inlining both datasets in `index.html` would recommit ~2.6 MB on every render. Refreshing the
elements every 6 hours would add roughly 500 MB a year. When this was decided the repo was 13 MB.

Fetching CelesTrak directly from the browser is allowed (CelesTrak sends
`Access-Control-Allow-Origin: *`), but on its own it doesn't work:

- CelesTrak answers a repeat request for the same group from the same IP within its ~2 h update
  cycle with HTTP 403, so a reload gets nothing.
- GCAT sends no CORS header, so the purpose and launch-vehicle data can't be fetched by the browser.
- A view-time failure is invisible to the page's source-status bus.

## Decision

Hybrid:

1. **Weekly committed files.** Both datasets refresh at most every 7 days (`cache.MAX_AGE`). Each
   one's cache *is* its published file (`docs/orbits.json`, `docs/fleet.json`, compact JSON), so
   nothing is committed twice. The page fetches both from its own origin and doesn't inline them.
2. **Live upgrade in the browser.** The page also requests CelesTrak `active` directly. On success
   the end-state globe uses live elements. On a 403 or any other failure it keeps the committed
   copy. The caption says which one is showing.

Expected git growth is about 35 MB a year.

## Consequences

- Opening `docs/index.html` from `file://` can't load the orbit files. Preview through
  `python -m http.server -d docs` instead.
- A visitor whose live fetch fails sees elements up to 7 days old. That's fine for a picture of
  70 years of history, but not for tracking a particular satellite now.
- Revisit if the end-state globe is meant to become a "where is satellite X now" tool. Daily
  elements would cost ~125 MB a year.
