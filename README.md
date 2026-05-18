# Big Trees of New Jersey

A browsable, ranked guide to every champion, heritage, and signature tree on New Jersey's official big-tree registry. Photos, stats, and directions to the ones you can visit, plus suggested half-day driving routes.

**Live site:** https://stephenstirling.github.io/big-trees/

> _This site was built with the assistance of [Claude Code](https://claude.com/claude-code)._

## What this is

The NJ DEP maintains an official registry of the state's largest trees, scored by the American Forests big-tree formula (circumference + height + ¼ × crown spread). They publish the data through an ArcGIS map but there's no easy way to scroll through the list, look at photos, rank trees by size, or plan a trip around them.

This is a static HTML page that does all of that. Not affiliated with NJ DEP.

Data source: [NJ DEP Big and Heritage Trees Program](https://dep.nj.gov/parksandforests/conservation/big-heritage-trees/) via its [public ArcGIS FeatureServer](https://services1.arcgis.com/QWdNfRs7lkPq4g4Q/ArcGIS/rest/services/NJDEP_Big_and_Heritage_Trees_in_New_Jersey/FeatureServer/19). 716 trees in the current snapshot.

## How it's built

Pure static site. No build step for the front end. Pre-fetched JSON + pre-resized photos committed to the repo so the page loads instantly and doesn't hammer the state's servers on every visit.

```
big-trees/
├── index.html
├── styles.css
├── app.js
├── data/nj/
│   ├── trees.json
│   └── trips.json
├── photos/nj/{OBJECTID}/{1.jpg, 1-thumb.jpg, manifest.json}
├── og/
│   ├── site.jpg                  # 1200×630 social card
│   └── template-site.html        # source for the card
├── scripts/
│   ├── _common.py                # shared resize, EXIF strip, helpers
│   ├── _visit_context.py         # address keyword classifier
│   ├── fetch_nj_data.py
│   ├── fetch_nj_photos.py
│   ├── build_nj_trips.py
│   ├── build_og_cards.py
│   └── requirements.txt
└── .github/workflows/pages.yml
```

## Reproducing the data locally

You need Python 3.10+ and ~200 MB of disk for the resized photos.

```bash
git clone https://github.com/stephenstirling/big-trees.git
cd big-trees

python3 -m venv .venv
.venv/bin/pip install -r scripts/requirements.txt

.venv/bin/python scripts/fetch_nj_data.py     # ~15 sec
.venv/bin/python scripts/fetch_nj_photos.py   # ~6 min first run, near-instant after
.venv/bin/python scripts/build_nj_trips.py    # ~1 min, generates field-trip routes via OSRM
.venv/bin/python scripts/build_og_cards.py    # regenerates the social card

python3 -m http.server 8000
open http://localhost:8000
```

## Field trips

`scripts/build_nj_trips.py` generates `data/nj/trips.json`, which the frontend renders as the "Field trips" section. Each trip is a one-way drive of 60-120 minutes through 5 nearby trees in one of five regions:

| Region | Counties |
|---|---|
| Northwest | Sussex, Warren, Morris |
| North | Essex, Bergen, Hudson, Passaic |
| Central | Somerset, Union, Middlesex, Hunterdon, Mercer |
| South | Burlington, Camden, Gloucester, Salem, Cumberland |
| Shore | Monmouth, Ocean, Atlantic, Cape May |

The build script:
- Excludes Emeritus trees (may no longer be standing)
- Within each region, seeds trips at the highest-scoring unassigned tree, then greedily adds nearby stops at least 4.5 miles apart, capping at 5 stops
- Orders each cluster as the shortest open path (brute-force TSP, small N)
- Calls the [OSRM public router](https://router.project-osrm.org/) to get real driving times and route geometry
- Falls back to a haversine × 1.4 estimate (40 mph average) if OSRM is unreachable

Trip names are auto-generated ("Northwest Trip 1"). Rename them by editing `data/nj/trips.json` directly — it's committed to the repo.

### Visit-context labels

The classifier in `scripts/_visit_context.py` tags every tree with a plain-language label based on address keywords:

- **In a park or preserve** — park, forest, preserve, arboretum keywords
- **At a school or campus** — school, college, university, academy
- **At a religious or memorial site** — church, cemetery, memorial, chapel
- **At a public institution** — library, museum, hospital, courthouse
- **At a private residence — view from public sidewalk only** (default)

Street-name false positives ("Park Ave", "Church Rd") are demoted via a suffix-aware regex. In the current snapshot, ~95% of trees fall into the default residence bucket — the field-trip cards make this visible at a glance with a warning icon and an "access mix" summary per trip.

## Photo pipeline

`scripts/fetch_nj_photos.py` does the following for every attachment on every tree, via shared helpers in `scripts/_common.py`:

1. Download the original JPEG.
2. Auto-rotate per EXIF orientation, then strip all EXIF (removes camera GPS, owner info, etc.).
3. Save **900px wide JPEG at q=78** as `{idx}.jpg` (used in the modal hero).
4. Save **350px wide JPEG at q=72** as `{idx}-thumb.jpg` (used in the grid).
5. Skip work if both files already exist (idempotent re-runs).

Scanned registration certificates (filenames starting with `Reg_`) are filtered out by default; pass `--include-certificates` to keep them.

## Privacy

Many of these trees stand on private property. NJ DEP records a per-tree `PermissionToList` flag — we show full addresses and precise pins only when that flag is YES. When NO/unknown, the address is hidden and the map is suppressed. Every record in the current snapshot has YES, but the fallback path exists for future refreshes.

If you visit a tree, be respectful — view from a public sidewalk or right-of-way unless you have explicit permission.

## Social cards

The site ships with an Open Graph / Twitter share card at `og/site.jpg` (1200×630, ~190 KB). When someone shares the homepage on Twitter, Slack, iMessage, Facebook, LinkedIn, etc., the preview shows the Belvidere Sycamore as the background with the "716 trees, ranked by size" headline overlay.

To regenerate the card after changing the template or the source photo:

```bash
.venv/bin/python scripts/build_og_cards.py
```

The script renders every `og/template-*.html` via headless Chrome (1200×630) and saves an optimized JPEG to `og/{name}.jpg`. To add another card variant later (e.g., a per-tree share card), drop a new `og/template-foo.html` and rerun.

The OG / Twitter meta tags in `index.html` point at the deployed URL — update them if you fork the repo to a different GitHub Pages path.

## Editorial notes

- "Biggest" everywhere on the site means highest score under the American Forests big-tree formula NJ DEP uses. A tree can be the biggest of its species (a Champion) without ranking near the top overall — small species don't compete with sycamores.
- Trees marked **Emeritus** are former champions that have been displaced by a larger tree or are no longer standing. They're excluded from the numbered rank on this page but still appear in the registry.
- Data cleanups applied at fetch time: status / county / municipality underscores stripped; `Cape_May` → `Cape May`; rows where `COMMONNAME` is actually a botanical name get the canonical common name swapped in from sibling rows of the same species.

## Deploy

`.github/workflows/pages.yml` publishes the repo as a static site on every push to `main`. Enable GitHub Pages in repository settings, source = GitHub Actions.

## License

Code: MIT. Data: NJ DEP (public records). Photos: contributors to the registry — rights belong to the original photographers and the program.
