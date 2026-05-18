# Big Trees of the Northeast

A browsable, ranked guide to every champion, heritage, Penn Charter, and notable tree on New Jersey's and Pennsylvania's official big-tree registries. Photos, stats, and directions to the ones you can visit.

**Live site:** https://stephenstirling.github.io/big-trees/

## What this is

Two state-run registries of the largest trees in their territory, scored by the same national formula (circumference + height + ¼ × crown spread). Each state publishes its data, but neither offers a ranked, browsable, image-forward presentation. This page does that, with each state on its own tab.

- **New Jersey** — 716 trees, sourced from the [NJ DEP Big and Heritage Trees Program](https://dep.nj.gov/parksandforests/conservation/big-heritage-trees/) via its [public ArcGIS FeatureServer](https://services1.arcgis.com/QWdNfRs7lkPq4g4Q/ArcGIS/rest/services/NJDEP_Big_and_Heritage_Trees_in_New_Jersey/FeatureServer/19).
- **Pennsylvania** — 1,833 trees, sourced from [Pennsylvania Big Trees](https://www.pabigtrees.com/tree-listings) via its public JSON API.

Not affiliated with either program.

## How it's built

Pure static site. No build step for the front end. Pre-fetched JSON + pre-resized photos committed to the repo so the page loads instantly and doesn't hammer the state servers on every visit.

```
big-trees/
├── index.html
├── styles.css
├── app.js
├── data/
│   ├── nj/trees.json
│   └── pa/trees.json
├── photos/
│   ├── nj/{OBJECTID}/{1.jpg, 1-thumb.jpg, manifest.json}
│   └── pa/{TR_ID}/{1.jpg, 1-thumb.jpg, manifest.json}
├── scripts/
│   ├── _common.py            # shared resize, EXIF strip, helpers
│   ├── fetch_nj_data.py
│   ├── fetch_nj_photos.py
│   ├── fetch_pa_data.py
│   ├── fetch_pa_photos.py
│   ├── requirements.txt
│   └── .cache/               # tree-id keyed image manifests (PA)
└── .github/workflows/pages.yml
```

Both states normalize to the same JSON schema so the frontend has one render path. State-specific bits (NJ permission flags vs PA nominator/measure-crew context) appear in the modal as state-aware sections.

## Reproducing the data locally

You need Python 3.10+ and ~700 MB of disk for the resized photos.

```bash
git clone https://github.com/stephenstirling/big-trees.git
cd big-trees

python3 -m venv .venv
.venv/bin/pip install -r scripts/requirements.txt

# 1. New Jersey
.venv/bin/python scripts/fetch_nj_data.py     # ~15 sec
.venv/bin/python scripts/fetch_nj_photos.py   # ~6 min first run, near-instant after
.venv/bin/python scripts/build_nj_trips.py    # ~1 min, generates field-trip routes via OSRM

# 2. Pennsylvania
.venv/bin/python scripts/fetch_pa_data.py     # ~15 min (fetches 1,833 image manifests at 0.4s/each)
.venv/bin/python scripts/fetch_pa_photos.py   # ~45 min first run, near-instant after

# 3. Serve locally
python3 -m http.server 8000
open http://localhost:8000
open http://localhost:8000/?state=pa
```

## Field trips (NJ only)

`scripts/build_nj_trips.py` generates `data/nj/trips.json`, which the frontend renders as the "Field trips" section on the NJ tab. Each trip is a one-way drive of 60-120 minutes through 5 nearby trees in one of five reader-facing regions:

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

Street-name false positives ("Park Ave", "Church Rd") are demoted via a suffix-aware regex. In the current NJ snapshot, ~95% of trees fall into the default residence bucket — the field-trip cards make this visible at a glance with a warning icon and an "access mix" summary per trip.

## Photo pipeline

Both pipelines do the same thing with `scripts/_common.py`:

1. Download the original JPEG.
2. Auto-rotate per EXIF orientation, then strip all EXIF (removes camera GPS, owner info, etc.).
3. Save **900px wide JPEG at q=78** as `{idx}.jpg` (used in the modal hero).
4. Save **350px wide JPEG at q=72** as `{idx}-thumb.jpg` (used in the grid).
5. Skip work if both files already exist (idempotent re-runs).

The NJ pipeline filters out scanned registration certificates (filenames starting with `Reg_`). The PA pipeline does the same heuristic but PA's data rarely contains certificates.

### Throttling

- NJ ArcGIS: no throttle. The state's CDN handles bursts fine.
- PA: 0.4s between API calls, 1.0s between image downloads. The PA program's `robots.txt` asks for a 20-second crawl delay, which is impractical for a one-time mirror of 1,800 records. We err well below that but well above hammering.

## Privacy

Many of these trees stand on private property. The two states handle privacy differently and we respect their conventions:

- **New Jersey** records a per-tree `PermissionToList` flag. We show full addresses and precise pins only when that flag is YES. When NO/unknown, the address is hidden and the map is suppressed. Every record in the current snapshot has YES, but the fallback path exists for future refreshes.
- **Pennsylvania** doesn't expose per-tree permission flags. The addresses you see are the ones the PA program already publishes in its own registry. We do not synthesize, augment, or geocode the data.

If you visit a tree, be respectful — view from a public sidewalk or right-of-way unless you have explicit permission.

## PA tab — currently gated off in the live build

The PA tab is hidden from the live site pending an outreach response from the Pennsylvania Forestry Association (see `OUTREACH-PA.md`). The PA data, photos, scripts, and frontend code all remain in this repo and continue to work locally. Re-enable by editing one line in `app.js`:

```js
const PUBLIC_STATES = new Set(["nj"]);          // current
const PUBLIC_STATES = new Set(["nj", "pa"]);    // re-enabled
```

When `PUBLIC_STATES` only contains a single state, the tab strip hides itself entirely so the page reads as a single-state site.

## Ethics & attribution

The two state programs have different funding and posture:

- **New Jersey** is run by the NJ DEP — a state agency funded by taxpayers. Public records.
- **Pennsylvania** is run by the [Pennsylvania Forestry Association](https://paforestry.org/), a 501(c)(3) non-profit founded in 1886. The PA Big Trees program is volunteer-led.

Because PA's program depends on volunteer labor and non-profit funding, the PA tab on this site:
- Carries a prominent acknowledgment callout in the hero linking back to [pabigtrees.com](https://www.pabigtrees.com/) and to the [PFA donation page](https://buy.stripe.com/8wM14jbI5arWgH65kl).
- Includes a "View the full record on pabigtrees.com" link on every PA tree's detail modal — not just buried in the source line.
- Names PFA and asks readers to donate from the methodology section.

Before pushing this project to a public URL, the maintainer plans to email PFA at thePFA@paforestry.org to introduce the project and ask permission to mirror their data and photos. The draft outreach email is in [`OUTREACH-PA.md`](OUTREACH-PA.md). If they decline, the PA tab will come down.

## Editorial notes

- "Biggest" everywhere on the site means highest score under the American Forests big-tree formula the registries use. A tree can be the biggest of its species (a Champion) without ranking near the top overall — small species don't compete with sycamores.
- Trees marked **Emeritus** (NJ) or **Retired** (PA) are former champions that have been displaced by a larger tree or are no longer standing. They're excluded from the numbered rank on this page but still appear in the registry.
- NJ data cleanups applied at fetch time: status / county / municipality underscores stripped; `Cape_May` → `Cape May`; rows where `COMMONNAME` is actually a botanical name get the canonical common name swapped in from sibling rows of the same species.
- PA status is derived: National Champion (from `f_national_champ`), Retired (from `f_retired`), Champion / Co-Champion (from per-species score ranking), Penn Charter (from `f_penn_charter`), Listed (default). PA's `f_multistemmed` and `f_tallest` flags are surfaced as small chips on the detail modal rather than as separate statuses.

## Deploy

`.github/workflows/pages.yml` publishes the repo as a static site on every push to `main`. Enable GitHub Pages in repository settings, source = GitHub Actions.

## License

Code: MIT. Data: NJ DEP (public records) and PA Big Trees program (volunteer-managed public registry). Photos: contributors to each registry — rights belong to the original photographers and the programs.
