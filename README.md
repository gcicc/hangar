# HANGAR

A range board for SpaceX and Tesla: **stated ambition against measured reality.**

Both companies run on public promises with dates attached. The interesting
question is never what they said, it is what happened to what they said. HANGAR
puts the promises and the measurements on one page and lets them argue.

```
python run.py             # refresh what has gone stale, then render
python run.py --force     # refresh everything, ignoring cache age
python run.py --render    # rebuild the page from cache; no network at all
```

Output is `docs/index.html`, one self-contained file.

## Periodic, not continuous

The browser never calls an API. A scheduled job fetches, writes JSON to `data/`,
commits it, and the page reads static files. This is not an optimisation — it is
forced by Launch Library's free tier of **15 requests per hour** — but it also
means the page works offline and the refresh job and the page are fully
decoupled.

Every source declares its own `max_age` in `hangar/cache.py`, so one cron at
`0 */2 * * *` produces six different refresh rates:

| Source | max_age | Why |
|---|---|---|
| News RSS | 2h | 22 feeds; the rate GRUDGE has run at for months |
| Launch Library | 2h | 4 calls per run, under the 15/hour ceiling |
| Yahoo quotes | 2h | free, no key |
| CelesTrak | 6h | upstream itself only updates every 2h |
| supercharge.info | 7d | large payload, changes slowly |

Three failure modes are handled distinctly, because conflating them is how a
dashboard lies:

- **Fetch failed** → keep the previous payload, record the error, mark the panel
  stale. An empty panel is indistinguishable from a quiet news day.
- **Upstream unchanged** → CelesTrak answers a repeat request with HTTP 403 and
  "GP data has not updated". That is a courtesy, not an error, and must not mark
  a healthy source broken.
- **Still fresh** → skip the call entirely.

## The commitments board

Three kinds of row, never mixed:

- **TRACKED** — curated in `data/targets.json`. Each carries the statement, who
  said it, when, a source URL, and a `metric` key that resolves against live
  data, so status is *computed*. This register is deliberately never populated
  from recollection; a row without a source does not belong in it.
- **CLAIMED** — detected automatically from headlines: a commitment verb, plus a
  time horizon, plus one of the two companies, minus anything reading as
  speculation. Roughly 0.6% of headlines qualify. These are candidates, shown as
  what somebody said, cited and linked — never as verified fact.
- **Nothing else.** No target is ever invented.

Zero LLM calls anywhere in the pipeline, matching GRUDGE and clintrialist-report:
deterministic and free.

### Sourcing

Musk states most targets on X before any outlet reports them, so a claim from the
post itself outranks the same claim from coverage of it. X needs a real browser,
which GitHub Actions cannot cheaply provide, so collection is decoupled: an
optional local task writes `data/x_posts.json` and `hangar/xfeed.py` reads it.
When that file is missing or stale the board falls back to reported claims **and
says so on the page**. A silent downgrade from primary to second-hand sourcing
would be worse than an absent panel.

## Honest numbers

Several places where the obvious rendering would mislead, and what is done
instead:

- **Launch cadence** — the oldest month is truncated by where the sample ends, so
  it is dropped; the current month is incomplete, so it is kept but flagged.
- **Starlink by launch year** — counts only satellites *still in orbit*, so it is
  survivorship-biased and understates past years. Labelled as what it is. The
  unbiased series accumulates in `data/history.json` from the first run.
- **Tesla Q4** — never filed as its own quarterly XBRL fact. Derived as
  FY − (Q1+Q2+Q3) and marked as derived.
- **People in space** — Launch Library counts Starman, the mannequin in the
  Roadster. He is separated out rather than discarded; a Tesla in solar orbit
  belongs on this page, just not in the headcount.
- **SPCX** — listed June 2026. The price series does not cover a full earnings
  cycle, so technical levels drawn from it are weak evidence.
- **The countdown** — Launch Library reports how precisely a NET date is actually
  known. The clock never shows finer resolution than the data supports: a
  month-precision NET does not get a ticking seconds readout.

## Layout

`hangar/` — `cache` (age gating, status ledger) · `fetcher` `feeds` `scorer`
`topics` (news) · `launches` `constellation` `financials` (data clients) ·
`targets` `xfeed` `history` (the board) · `render` + `templates/` (the page).

Built from house patterns: the feed layer is ported from
`02-Maintain/clintrialist-report`, the cron from `02-Maintain/GRUDGE`, the
single-file renderer from `02-Maintain/portfolio-dashboard`, and the embedded
Leaflet map from `02-Maintain/dads80th/includes/lifemap.html`.
