"""Fetch the NJDEP Big and Heritage Trees registry into data/trees.json.

Pulls every feature from the public FeatureServer, attaches photo metadata,
and writes a normalized JSON snapshot the static site reads at load time.

Run: .venv/bin/python scripts/fetch_data.py
Source: https://services1.arcgis.com/QWdNfRs7lkPq4g4Q/ArcGIS/rest/services/NJDEP_Big_and_Heritage_Trees_in_New_Jersey/FeatureServer/19
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

from _visit_context import classify as classify_visit_context

LAYER = (
    "https://services1.arcgis.com/QWdNfRs7lkPq4g4Q/ArcGIS/rest/services/"
    "NJDEP_Big_and_Heritage_Trees_in_New_Jersey/FeatureServer/19"
)
ROOT = Path(__file__).resolve().parent.parent
OUT_FILE = ROOT / "data" / "nj" / "trees.json"
MUNI_FILE = ROOT / "data" / "nj" / "municipalities.json"

PAGE_SIZE = 2000  # service max; whole dataset is ~716 so one page is enough
ATTACH_BATCH = 50

# Filenames matching this pattern are scanned registration certificates,
# not photos of the tree itself. We keep them but flag separately so the
# carousel can default to real photos.
CERT_RE = re.compile(r"^reg[_\-\s]", re.IGNORECASE)


def yes(v: object) -> bool:
    return isinstance(v, str) and v.strip().upper() == "YES"


def unscore(s: str | None) -> str:
    """Replace underscores with spaces. NJDEP's source uses underscores in several
    string fields (statuses, county sometimes, occasionally common names)."""
    if not s:
        return ""
    return s.replace("_", " ").strip()


def looks_botanical(name: str) -> bool:
    """Heuristic: 'Platanus_occidentalis' or 'Platanus occidentalis' looks botanical
    (genus + species, lowercase species). Real common names rarely match this."""
    parts = name.replace("_", " ").split()
    if len(parts) != 2:
        return False
    genus, species = parts
    return genus[:1].isupper() and species.islower() and species.isalpha()


def build_common_name_lookup(features: list[dict]) -> dict[str, str]:
    """Map botanical_name (normalized) -> most frequent real common name in the dataset.

    Some rows have the botanical name in the common-name field. When that happens,
    we fall back to the common name another row used for the same botanical species.
    """
    from collections import Counter

    counts: dict[str, Counter] = {}
    for f in features:
        a = f["attributes"]
        bot = unscore(a.get("BOTANICALNAME")).lower()
        com = (a.get("COMMONNAME") or "").strip()
        if not bot or not com:
            continue
        if "_" in com or looks_botanical(com):
            continue  # skip rows where common is itself botanical
        counts.setdefault(bot, Counter())[com] += 1
    return {bot: c.most_common(1)[0][0] for bot, c in counts.items()}


def fetch_features() -> list[dict]:
    """Page through the layer and return all features (attributes + geometry in WGS84)."""
    out: list[dict] = []
    offset = 0
    while True:
        params = {
            "where": "1=1",
            "outFields": "*",
            "outSR": 4326,
            "returnGeometry": "true",
            "resultOffset": offset,
            "resultRecordCount": PAGE_SIZE,
            "orderByFields": "OBJECTID ASC",
            "f": "json",
        }
        r = requests.get(f"{LAYER}/query", params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise RuntimeError(f"ArcGIS error: {data['error']}")
        feats = data.get("features", [])
        out.extend(feats)
        if not data.get("exceededTransferLimit") or not feats:
            break
        offset += len(feats)
    return out


def fetch_attachments(object_ids: list[int]) -> dict[int, list[dict]]:
    """Return {OBJECTID: [{id, name, contentType, size, is_certificate}, ...]}."""
    by_oid: dict[int, list[dict]] = {oid: [] for oid in object_ids}
    for i in range(0, len(object_ids), ATTACH_BATCH):
        batch = object_ids[i : i + ATTACH_BATCH]
        params = {
            "objectIds": ",".join(str(o) for o in batch),
            "returnUrl": "false",
            "f": "json",
        }
        r = requests.get(f"{LAYER}/queryAttachments", params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise RuntimeError(f"ArcGIS error: {data['error']}")
        for group in data.get("attachmentGroups", []):
            oid = group["parentObjectId"]
            for att in group.get("attachmentInfos", []):
                name = att.get("name", "")
                by_oid.setdefault(oid, []).append(
                    {
                        "attachment_id": att["id"],
                        "name": name,
                        "content_type": att.get("contentType"),
                        "size": att.get("size"),
                        "is_certificate": bool(CERT_RE.match(name)),
                    }
                )
    return by_oid


def normalize(feature: dict, attachments: list[dict], common_lookup: dict[str, str]) -> dict:
    a = feature["attributes"]
    geom = feature.get("geometry") or {}
    public = yes(a.get("PERMISSIONTOLIST"))

    raw_common = (a.get("COMMONNAME") or "").strip()
    botanical = unscore(a.get("BOTANICALNAME"))
    # If COMMONNAME holds a botanical-looking string, swap in a real common
    # name from another row with the same botanical species. Preserves the
    # original in raw_common_name for transparency.
    if raw_common and ("_" in raw_common or looks_botanical(raw_common)):
        fallback = common_lookup.get(botanical.lower())
        common = fallback or unscore(raw_common)
    else:
        common = raw_common or "Unknown species"

    height = a.get("HEIGHT")
    circ_in = a.get("CIRCUMFERENCE")
    circ_eng = (a.get("CIRCUM_ENG") or "").strip()
    municipality = unscore(a.get("MUNICIPALITY"))
    county = unscore(a.get("COUNTY"))
    status = unscore(a.get("STATUS"))

    alt_bits = [common]
    if municipality and county:
        alt_bits.append(f"in {municipality}, {county} County, NJ")
    if status:
        alt_bits.append(f"— {status}")
    measures = []
    if height:
        measures.append(f"{height} ft tall")
    if circ_eng:
        measures.append(f"{circ_eng} around")
    elif circ_in:
        measures.append(f"{circ_in} in. around")
    if measures:
        alt_bits.append(", ".join(measures))
    alt = " ".join(alt_bits).strip(" —,")

    street_address = (a.get("STREETADDRESS") or "").strip() or None
    visit_label, visit_key = classify_visit_context(street_address)

    return {
        "id": str(a["OBJECTID"]),
        "state": "NJ",
        "globalid": a.get("GLOBALID"),
        "common_name": common,
        "raw_common_name": raw_common or None,
        "botanical_name": botanical,
        "local_name": (a.get("LOCALNAME") or "").strip() or None,
        "status": status,
        "score": a.get("POINT"),
        "circumference_in": circ_in,
        "circumference_eng": circ_eng or None,
        "height_ft": height,
        "crown_avg_ft": a.get("CROWNAVG"),
        "dbh_in": a.get("DBH"),
        "ranking_in_species": a.get("RANKING"),
        "county": county,
        "municipality": municipality,
        "street_address": street_address,
        "visit_context": visit_label,
        "visit_context_key": visit_key,
        "zipcode": (a.get("ZIPCODE") or "").strip() or None,
        "lat": geom.get("y"),
        "lng": geom.get("x"),
        "permission_to_list": yes(a.get("PERMISSIONTOLIST")),
        "permission_to_measure": yes(a.get("PERMISSIONTOMEASURE")),
        "permission_to_photograph": yes(a.get("PERMISSIONTOPHOTOGRAPH")),
        "certificate": yes(a.get("CERTIFICATE")),
        "is_public_location": public,
        "alt_text": alt,
        "photos": attachments,
        # PA-only fields, null for NJ records so the frontend can read uniformly.
        "pa_nominator": None,
        "pa_measure_crew": None,
        "pa_date_nominated": None,
        "pa_date_last_measured": None,
        "pa_comments": None,
        "pa_multistemmed": None,
        "pa_tallest_in_species": None,
    }


def apply_display_geo(trees: list[dict]) -> None:
    """Set display_lat/display_lng and display_address based on the privacy rule.

    PERMISSIONTOLIST=YES → precise pin and full address.
    Otherwise → municipality centroid (from data/municipalities.json) and address hidden.
    Falls back to county-level when no centroid match (rare; flagged via display_precision).
    """
    muni: dict[str, dict] = {}
    if MUNI_FILE.exists():
        muni = json.loads(MUNI_FILE.read_text())

    for t in trees:
        if t["is_public_location"]:
            t["display_lat"] = t["lat"]
            t["display_lng"] = t["lng"]
            t["display_precision"] = "exact"
            t["display_address"] = t["street_address"]
            continue
        key = f"{t['municipality']}|{t['county']}"
        c = muni.get(key)
        if c:
            t["display_lat"] = c["lat"]
            t["display_lng"] = c["lng"]
            t["display_precision"] = "municipality"
        else:
            # No centroid available — fall back to original coords but mark it
            # so the UI can warn (or skip the map). Better than silently
            # exposing a precise residence.
            t["display_lat"] = None
            t["display_lng"] = None
            t["display_precision"] = "redacted"
        t["display_address"] = None


def rank(trees: list[dict]) -> None:
    """Assign rank_overall (by score desc) and rank_in_status (within status).

    Emeritus trees are excluded from rank_overall — they're former champions
    that have been displaced (a bigger tree was found) or are no longer standing.
    Either way, they shouldn't compete in the live leaderboard. Within-status
    ranks are still computed so Emeritus trees can be sorted among themselves.
    """
    rankable = [t for t in trees if t["score"] is not None and t["status"] != "Emeritus"]
    rankable.sort(key=lambda t: (-t["score"], t["id"]))
    for i, t in enumerate(rankable, start=1):
        t["rank_overall"] = i
    for t in trees:
        if t.get("rank_overall") is None:
            t["rank_overall"] = None  # ensure key exists

    by_status: dict[str, list[dict]] = {}
    for t in trees:
        by_status.setdefault(t["status"], []).append(t)
    for group in by_status.values():
        group.sort(key=lambda t: (t["score"] is None, -(t["score"] or 0), t["id"]))
        for i, t in enumerate(group, start=1):
            t["rank_in_status"] = i if t["score"] is not None else None


def main() -> int:
    print(f"Fetching features from {LAYER} ...")
    features = fetch_features()
    print(f"  got {len(features)} features")

    oids = [f["attributes"]["OBJECTID"] for f in features]
    print(f"Fetching attachment metadata for {len(oids)} trees ...")
    attachments = fetch_attachments(oids)

    photo_count = sum(len(v) for v in attachments.values())
    print(f"  got {photo_count} attachments across {sum(1 for v in attachments.values() if v)} trees")

    common_lookup = build_common_name_lookup(features)
    trees = [
        normalize(f, attachments.get(f["attributes"]["OBJECTID"], []), common_lookup)
        for f in features
    ]
    apply_display_geo(trees)
    rank(trees)

    # Sort by score descending so the grid is always "biggest first" regardless
    # of Emeritus status. Top 10 separately filters out trees with no
    # rank_overall (i.e. Emeritus), so they appear in the grid by size but
    # never on the leaderboard.
    trees.sort(key=lambda t: (t["score"] is None, -(t["score"] or 0), t["id"]))

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": LAYER,
        "count": len(trees),
        "trees": trees,
    }
    OUT_FILE.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {OUT_FILE} ({OUT_FILE.stat().st_size / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
