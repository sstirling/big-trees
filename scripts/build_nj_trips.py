"""Build one-way driving field-trips through NJ big trees, by region.

Reads data/nj/trees.json. Within each of five reader-facing regions, greedily
builds clusters of 3-6 trees that can be driven through in 60-120 minutes,
ordering each cluster as the shortest open path (TSP, brute force on small N).
Uses the OSRM public demo router for road times + route geometry; falls back
to haversine * 1.4 if OSRM is unreachable.

Output: data/nj/trips.json

Run: .venv/bin/python scripts/build_nj_trips.py [--max-trips-per-region N]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import datetime, timezone
from itertools import permutations
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
IN_FILE = ROOT / "data" / "nj" / "trees.json"
OUT_FILE = ROOT / "data" / "nj" / "trips.json"

REGIONS = {
    "Northwest": {"Sussex", "Warren", "Morris"},
    "North": {"Essex", "Bergen", "Hudson", "Passaic"},
    "Central": {"Somerset", "Union", "Middlesex", "Hunterdon", "Mercer"},
    "South": {"Burlington", "Camden", "Gloucester", "Salem", "Cumberland"},
    "Shore": {"Monmouth", "Ocean", "Atlantic", "Cape May"},
}
REGION_ORDER = ["Northwest", "North", "Central", "South", "Shore"]

OSRM = "https://router.project-osrm.org"

MAX_DRIVE_MINUTES = 120
MIN_DRIVE_MINUTES = 60
TARGET_DRIVE_MINUTES = 90  # try to extend trips toward this
MAX_STOPS = 5
MIN_STOPS = 3
NEAREST_RADIUS_MI = 35.0
# Minimum haversine distance between any two stops in a cluster. Forces the
# greedy expander to skip near-duplicates and produce trips with real driving
# between stops, not a dense knot of 6 trees in the same neighborhood.
MIN_STOP_SPACING_MI = 4.5


def haversine_mi(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in miles."""
    R = 3958.7613
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def osrm_route(stops: list[dict]) -> dict | None:
    """Call OSRM /route for stops in order. Returns {minutes, miles, geojson} or None."""
    coords = ";".join(f"{s['lng']},{s['lat']}" for s in stops)
    url = f"{OSRM}/route/v1/driving/{coords}"
    params = {"overview": "full", "geometries": "geojson"}
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        if data.get("code") != "Ok" or not data.get("routes"):
            return None
        route = data["routes"][0]
        return {
            "minutes": route["duration"] / 60,
            "miles": route["distance"] / 1609.34,
            "geojson": route["geometry"],
            "legs": [{"minutes": leg["duration"] / 60, "miles": leg["distance"] / 1609.34} for leg in route["legs"]],
        }
    except Exception as exc:  # noqa: BLE001
        print(f"  WARN: OSRM request failed: {exc}", file=sys.stderr)
        return None


def haversine_route(stops: list[dict]) -> dict:
    """Fallback: estimate route via haversine * 1.4 for drive time, straight lines."""
    total_mi = 0.0
    legs = []
    for i in range(len(stops) - 1):
        d = haversine_mi(stops[i]["lat"], stops[i]["lng"], stops[i + 1]["lat"], stops[i + 1]["lng"])
        total_mi += d * 1.4  # NJ roads are not as the crow flies
        legs.append({"minutes": d * 1.4 / 40 * 60, "miles": d * 1.4})  # assume 40 mph average
    return {
        "minutes": total_mi / 40 * 60,
        "miles": total_mi,
        "geojson": {
            "type": "LineString",
            "coordinates": [[s["lng"], s["lat"]] for s in stops],
        },
        "legs": legs,
        "fallback": True,
    }


def best_open_path(stops: list[dict]) -> list[dict]:
    """Brute-force the shortest open path (TSP open) by haversine. Small N."""
    if len(stops) <= 2:
        return stops[:]
    best_order = None
    best_d = float("inf")
    for perm in permutations(range(len(stops))):
        d = sum(
            haversine_mi(stops[perm[i]]["lat"], stops[perm[i]]["lng"], stops[perm[i + 1]]["lat"], stops[perm[i + 1]]["lng"])
            for i in range(len(stops) - 1)
        )
        if d < best_d:
            best_d = d
            best_order = perm
    return [stops[i] for i in best_order]


def thumbnail(tree: dict) -> str | None:
    # Use the first non-cert photo if present.
    photos = [p for p in tree.get("photos", []) if not p.get("is_certificate")]
    if not photos:
        return None
    return f"photos/nj/{tree['id']}/1-thumb.jpg"


def trip_seed(candidates: list[dict], assigned: set[str]) -> dict | None:
    """Pick the highest-scoring unassigned tree as the trip seed."""
    for t in candidates:
        if t["id"] not in assigned:
            return t
    return None


def grow_trip(seed: dict, pool: list[dict], assigned: set[str]) -> list[dict]:
    """Greedy expansion from seed.

    Picks the nearest-to-cluster unassigned tree that's still at least
    MIN_STOP_SPACING_MI from every existing stop. The minimum-spacing rule
    prevents a tight knot of stops in one neighborhood; the result is a trip
    where each leg actually requires driving.
    """
    cluster = [seed]
    cluster_ids = {seed["id"]}
    while len(cluster) < MAX_STOPS:
        best = None
        best_d = NEAREST_RADIUS_MI
        for t in pool:
            if t["id"] in assigned or t["id"] in cluster_ids:
                continue
            distances = [haversine_mi(c["lat"], c["lng"], t["lat"], t["lng"]) for c in cluster]
            min_dist = min(distances)
            if min_dist < MIN_STOP_SPACING_MI:
                continue  # too close to an existing stop
            if min_dist < best_d:
                best_d = min_dist
                best = t
        if best is None:
            break
        cluster.append(best)
        cluster_ids.add(best["id"])
    return cluster


def trip_to_stops(cluster: list[dict]) -> list[dict]:
    """Order via brute-force TSP open path, then return slim per-stop dicts."""
    ordered = best_open_path(cluster)
    return [
        {
            "tree_id": t["id"],
            "order": i + 1,
            "lat": t["lat"],
            "lng": t["lng"],
            "common_name": t["common_name"],
            "botanical_name": t.get("botanical_name"),
            "score": t.get("score"),
            "status": t.get("status"),
            "visit_context": t.get("visit_context"),
            "visit_context_key": t.get("visit_context_key", "residence"),
            "thumbnail": thumbnail(t),
            "county": t.get("county"),
            "municipality": t.get("municipality"),
            "street_address": t.get("street_address"),
            "is_public_location": t.get("is_public_location", True),
        }
        for i, t in enumerate(ordered)
    ]


def build_region_trips(
    region: str,
    trees: list[dict],
    max_trips: int,
    use_osrm: bool,
) -> list[dict]:
    """Yield up to max_trips well-formed trips for this region."""
    # Sort by score desc — seeds pick the most interesting unassigned tree.
    candidates = sorted(
        [t for t in trees if t.get("status") != "Emeritus" and t.get("lat") and t.get("lng") and t.get("score")],
        key=lambda t: -(t.get("score") or 0),
    )
    assigned: set[str] = set()
    trips: list[dict] = []
    attempts = 0
    max_attempts = max_trips * 4  # safety to bound iteration

    while len(trips) < max_trips and attempts < max_attempts:
        attempts += 1
        seed = trip_seed(candidates, assigned)
        if not seed:
            break

        cluster = grow_trip(seed, candidates, assigned)
        if len(cluster) < MIN_STOPS:
            # too thin — burn the seed and move on
            assigned.add(seed["id"])
            continue

        # Order, then call OSRM. If too long, drop the trailing stop until it fits.
        while len(cluster) >= MIN_STOPS:
            stops = trip_to_stops(cluster)
            route = osrm_route(stops) if use_osrm else None
            if not route:
                route = haversine_route(stops)
            if route["minutes"] <= MAX_DRIVE_MINUTES:
                break
            cluster = cluster[:-1]
        else:
            # Couldn't shrink to fit, abandon and burn seed
            assigned.add(seed["id"])
            continue

        if route["minutes"] < MIN_DRIVE_MINUTES:
            # Too short — not a real trip. Burn this seed so we don't try again.
            assigned.add(seed["id"])
            continue

        # Accept the trip.
        access_mix: dict[str, int] = {}
        for s in stops:
            k = s["visit_context_key"]
            access_mix[k] = access_mix.get(k, 0) + 1

        trips.append(
            {
                "id": f"nj-{region.lower().replace(' ', '-')}-{len(trips) + 1}",
                "region": region,
                "name": f"{region} Trip {len(trips) + 1}",
                "drive_minutes": round(route["minutes"]),
                "drive_miles": round(route["miles"], 1),
                "stop_count": len(stops),
                "access_mix": access_mix,
                "stops": stops,
                "route_geojson": route["geojson"],
                "legs": route.get("legs", []),
                "osrm_fallback": route.get("fallback", False),
            }
        )
        for s in stops:
            assigned.add(s["tree_id"])

        # Be polite to OSRM's public demo.
        if use_osrm:
            time.sleep(0.6)

    return trips


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-trips-per-region", type=int, default=4)
    parser.add_argument("--no-osrm", action="store_true", help="Skip OSRM, use haversine fallback only")
    args = parser.parse_args()

    if not IN_FILE.exists():
        print(f"Missing {IN_FILE}. Run fetch_nj_data.py first.", file=sys.stderr)
        return 1

    data = json.loads(IN_FILE.read_text())
    trees = data["trees"]
    print(f"Loaded {len(trees)} NJ trees.")

    use_osrm = not args.no_osrm
    if use_osrm:
        # Probe once to confirm OSRM is reachable.
        probe = osrm_route([
            {"lat": 40.84, "lng": -74.84},
            {"lat": 40.50, "lng": -74.27},
        ])
        if not probe:
            print("OSRM probe failed — switching to haversine fallback.", file=sys.stderr)
            use_osrm = False
        else:
            print(f"OSRM up: probe {probe['minutes']:.0f} min, {probe['miles']:.0f} mi")

    all_trips: list[dict] = []
    for region in REGION_ORDER:
        counties = REGIONS[region]
        region_trees = [t for t in trees if t.get("county") in counties]
        print(f"\n=== {region} ({len(region_trees)} trees) ===")
        trips = build_region_trips(region, region_trees, args.max_trips_per_region, use_osrm)
        for t in trips:
            print(f"  {t['id']}  {t['drive_minutes']} min / {t['drive_miles']} mi / {t['stop_count']} stops "
                  f"({', '.join(f'{n} {k}' for k, n in sorted(t['access_mix'].items()))})")
        all_trips.extend(trips)

    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "OSRM public demo (https://router.project-osrm.org) + NJDEP",
        "count": len(all_trips),
        "trips": all_trips,
    }
    OUT_FILE.write_text(json.dumps(payload, indent=2))
    print(f"\nWrote {OUT_FILE} ({OUT_FILE.stat().st_size / 1024:.1f} KB)")
    print(f"Total trips: {len(all_trips)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
