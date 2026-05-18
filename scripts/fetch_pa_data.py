"""Fetch the Pennsylvania big-trees registry into data/pa/trees.json.

Pulls every tree record from the pabigtrees.com public JSON API, fetches each
tree's photo manifest, derives a status label from the program's flags + per-
species ranking, and writes a normalized snapshot in the same schema the NJ
pipeline uses.

API endpoints (verified):
  - GET https://www.pabigtrees.com/trees?pageSize=2000
  - GET https://www.pabigtrees.com/trees/image/{TR_ID}
  - GET https://www.pabigtrees.com/uploads/{img_location}   (image bytes)

robots.txt requests a 20-second crawl delay. Since the /trees response is a
single request and the image-manifest calls are small JSON GETs, we throttle
modestly (~0.4s between manifest calls) and rely on local caching so most
re-runs hit zero network.

Run: .venv/bin/python scripts/fetch_pa_data.py
"""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

API = "https://www.pabigtrees.com"
TREES_URL = f"{API}/trees?pageSize=2000"
ROOT = Path(__file__).resolve().parent.parent
OUT_FILE = ROOT / "data" / "pa" / "trees.json"
MANIFEST_CACHE = ROOT / "scripts" / ".cache" / "pa_image_manifests.json"

UA = "BigTreesNE/1.0 (https://github.com/stephenstirling/big-trees) research mirror"

# Filenames that match this look like inspection/certification scans rather
# than tree photos. Currently rare in PA data but we tag them just in case.
CERT_RE = re.compile(r"(certificat|registr|nominat|measure)[a-z_-]*\.(jpe?g|png)$", re.IGNORECASE)


def parse_gps(s: str | None) -> tuple[float | None, float | None]:
    """'40.121290, -75.603872' → (40.121290, -75.603872). Empty/garbled → (None, None)."""
    if not s:
        return None, None
    parts = [p.strip() for p in s.split(",")]
    if len(parts) != 2:
        return None, None
    try:
        lat = float(parts[0])
        lng = float(parts[1])
    except ValueError:
        return None, None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None, None
    return lat, lng


def parse_pa_date(s: str | None) -> str | None:
    """'7/29/23 12:00:00 AM' → '2023-07-29'. '' → None."""
    if not s:
        return None
    s = s.strip()
    if not s:
        return None
    head = s.split()[0]
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(head, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def inches_to_eng(inches: int | None) -> str | None:
    if not inches:
        return None
    feet, rem = divmod(int(round(inches)), 12)
    return f"{feet}' {rem}\""


def botanical(species: dict | None) -> str:
    if not species:
        return ""
    genus = (species.get("genus") or {}).get("t_genus") or ""
    sp = species.get("t_species") or ""
    return f"{genus} {sp}".strip()


def fetch_trees() -> list[dict]:
    print(f"Fetching {TREES_URL} ...")
    r = requests.get(TREES_URL, headers={"User-Agent": UA}, timeout=120)
    r.raise_for_status()
    data = r.json()
    print(f"  got {data.get('count')} records ({len(data.get('trees', []))} in this page)")
    return data["trees"]


def load_manifest_cache() -> dict:
    if MANIFEST_CACHE.exists():
        try:
            return json.loads(MANIFEST_CACHE.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_manifest_cache(cache: dict) -> None:
    MANIFEST_CACHE.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_CACHE.write_text(json.dumps(cache, indent=2))


def fetch_image_manifest(
    tree_id: str, last_measured: str | None, cache: dict, throttle_sec: float
) -> tuple[list[dict], bool]:
    """Returns (image list, was_fetched_from_network) for a tree.

    Cache keyed by tree_id + d_last_measured. Caller throttles only on misses.
    """
    key = f"{tree_id}|{last_measured or ''}"
    if key in cache:
        return cache[key], False
    url = f"{API}/trees/image/{tree_id}"
    if throttle_sec > 0:
        time.sleep(throttle_sec)
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
        r.raise_for_status()
        items = r.json()
    except Exception as exc:  # noqa: BLE001
        print(f"  WARN: image manifest failed for {tree_id}: {exc}", file=sys.stderr)
        items = []
    # Only keep active images.
    items = [
        {
            "img_location": i["img_location"],
            "name": i["img_location"],
            "is_certificate": bool(CERT_RE.search(i.get("img_location", ""))),
            "manifest_id": i.get("id"),
        }
        for i in items
        if i.get("f_active") and i.get("img_location")
    ]
    cache[key] = items
    return items, True


def derive_status(tree: dict, species_rank: dict[str, list[dict]]) -> str:
    """Derive a single status label for a PA tree.

    Order matters: National Champion > Retired > Champion (top of species) >
    Co-Champion (within 5 pts of top) > Penn Charter > Listed.
    """
    if tree.get("f_national_champ"):
        return "National Champion"
    if tree.get("f_retired"):
        return "Retired"
    rank_list = species_rank.get(tree.get("k_species") or "", [])
    if rank_list:
        top = rank_list[0]
        if tree["id"] == top["id"]:
            return "Champion"
        # 2nd place within 5 points of #1 (American Forests convention)
        if len(rank_list) >= 2 and tree["id"] == rank_list[1]["id"]:
            diff = (top.get("i_points") or 0) - (tree.get("i_points") or 0)
            if diff <= 5:
                return "Co-Champion"
    if tree.get("f_penn_charter"):
        return "Penn Charter"
    return "Listed"


def normalize(tree: dict, status: str, images: list[dict]) -> dict:
    sp = tree.get("species") or {}
    common = (sp.get("t_common") or "").strip() or "Unknown species"
    bot = botanical(sp)
    cty = (tree.get("county") or {}).get("county") or ""
    lat, lng = parse_gps(tree.get("t_gps"))

    height = tree.get("i_height_feet")
    circ_in = tree.get("i_circum_inches")
    spread = tree.get("i_spread_feet")
    address = (tree.get("t_address") or "").strip() or None
    comments = (tree.get("t_comments") or "").strip() or None

    alt_bits = [common]
    if cty:
        alt_bits.append(f"in {cty} County, PA")
    if status:
        alt_bits.append(f"— {status}")
    measures = []
    if height:
        measures.append(f"{height} ft tall")
    if circ_in:
        eng = inches_to_eng(circ_in)
        measures.append(f"{eng} around" if eng else f"{circ_in} in. around")
    if measures:
        alt_bits.append(", ".join(measures))
    alt = " ".join(alt_bits).strip(" —,")

    # PA's API only exposes isPublic=1 records; we still record the field for
    # future-proofing the privacy fallback path the frontend already supports.
    public = bool(tree.get("isPublic", 1)) and bool(address or (lat and lng))

    return {
        "id": tree["id"],
        "state": "PA",
        "globalid": None,
        "common_name": common,
        "raw_common_name": None,
        "botanical_name": bot,
        "local_name": None,
        "status": status,
        "score": tree.get("i_points"),
        "circumference_in": circ_in,
        "circumference_eng": inches_to_eng(circ_in),
        "height_ft": height,
        "crown_avg_ft": spread,
        "dbh_in": None,
        "ranking_in_species": None,  # set in compute_species_rank
        "county": cty,
        "municipality": None,
        "street_address": address,
        "zipcode": None,
        "lat": lat,
        "lng": lng,
        "is_public_location": public,
        "display_lat": lat,
        "display_lng": lng,
        "display_precision": "exact" if (lat and lng) else "redacted",
        "display_address": address if public else None,
        # NJ-only fields, null for PA records.
        "permission_to_list": None,
        "permission_to_measure": None,
        "permission_to_photograph": None,
        "certificate": None,
        "alt_text": alt,
        "photos": images,
        # PA-only fields.
        "pa_nominator": (tree.get("t_original_nominator") or "").strip() or None,
        "pa_measure_crew": (tree.get("t_measure_crew") or "").strip() or None,
        "pa_date_nominated": parse_pa_date(tree.get("d_nominated")),
        "pa_date_last_measured": parse_pa_date(tree.get("d_last_measured")),
        "pa_comments": comments,
        "pa_multistemmed": bool(tree.get("f_multistemmed")),
        "pa_tallest_in_species": bool(tree.get("f_tallest")),
        "pa_penn_charter": bool(tree.get("f_penn_charter")),
    }


def compute_species_rank(trees: list[dict]) -> dict[str, list[dict]]:
    """Group by k_species, sorted by score desc. Excludes retired and trees with no score."""
    by_species: dict[str, list[dict]] = {}
    for t in trees:
        if t.get("f_retired"):
            continue
        if t.get("i_points") is None:
            continue
        sp = t.get("k_species") or ""
        by_species.setdefault(sp, []).append(t)
    for group in by_species.values():
        group.sort(key=lambda t: (-(t.get("i_points") or 0), t["id"]))
    return by_species


def assign_overall_rank(trees: list[dict]) -> None:
    """rank_overall: by score desc, excluding Retired trees. rank_in_status: within status."""
    rankable = [t for t in trees if t["status"] != "Retired" and t["score"] is not None]
    rankable.sort(key=lambda t: (-t["score"], t["id"]))
    for i, t in enumerate(rankable, start=1):
        t["rank_overall"] = i
    for t in trees:
        if "rank_overall" not in t:
            t["rank_overall"] = None

    by_status: dict[str, list[dict]] = {}
    for t in trees:
        by_status.setdefault(t["status"], []).append(t)
    for group in by_status.values():
        group.sort(key=lambda t: (t["score"] is None, -(t["score"] or 0), t["id"]))
        for i, t in enumerate(group, start=1):
            t["rank_in_status"] = i if t["score"] is not None else None


def assign_species_rank(trees: list[dict], by_species: dict[str, list[dict]], raw_trees: list[dict]) -> None:
    """Set ranking_in_species using PA's per-species sort. Keyed by tree id."""
    pa_id_to_kspecies = {t["id"]: t.get("k_species") for t in raw_trees}
    for t in trees:
        sp_key = pa_id_to_kspecies.get(t["id"])
        if not sp_key:
            continue
        group = by_species.get(sp_key, [])
        for i, g in enumerate(group, start=1):
            if g["id"] == t["id"]:
                t["ranking_in_species"] = i
                break


def main() -> int:
    raw_trees = fetch_trees()

    cache = load_manifest_cache()
    cache_size_before = len(cache)
    print(f"Fetching image manifests (cache has {cache_size_before} entries) ...")
    all_images: dict[str, list[dict]] = {}
    fetched = 0
    started = time.time()
    SAVE_EVERY = 200
    for i, t in enumerate(raw_trees, start=1):
        images, was_fetched = fetch_image_manifest(
            t["id"], t.get("d_last_measured"), cache, throttle_sec=0.4
        )
        all_images[t["id"]] = images
        if was_fetched:
            fetched += 1
        if i % 100 == 0:
            elapsed = time.time() - started
            rate = i / elapsed if elapsed else 0
            remaining = (len(raw_trees) - i) / max(rate, 0.1)
            print(f"  {i}/{len(raw_trees)}  ({fetched} fetched, {rate:.1f}/s, ~{remaining:.0f}s remaining)")
        # Periodically persist cache so a killed run is mostly recoverable.
        if was_fetched and fetched % SAVE_EVERY == 0:
            save_manifest_cache(cache)
    save_manifest_cache(cache)
    print(f"  manifests done. cache: {cache_size_before} -> {len(cache)}")

    species_rank = compute_species_rank(raw_trees)
    print(f"  species groups: {len(species_rank)}")

    trees: list[dict] = []
    for raw in raw_trees:
        status = derive_status(raw, species_rank)
        images = all_images.get(raw["id"], [])
        trees.append(normalize(raw, status, images))

    assign_overall_rank(trees)
    assign_species_rank(trees, species_rank, raw_trees)

    # Sort the output by score desc (same as NJ), so emeritus/retired show in
    # the grid by size but never appear in the top-10 (filtered by rank_overall).
    trees.sort(key=lambda t: (t["score"] is None, -(t["score"] or 0), t["id"]))

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": API,
        "count": len(trees),
        "trees": trees,
    }
    OUT_FILE.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {OUT_FILE} ({OUT_FILE.stat().st_size / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
