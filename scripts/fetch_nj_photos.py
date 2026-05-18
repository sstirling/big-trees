"""Download every NJDEP tree photo, resize to web sizes, strip EXIF.

For each tree photo in data/nj/trees.json:
  - Downloads the original JPEG from the ArcGIS attachment endpoint
  - Resizes to MAIN_WIDTH and THUMB_WIDTH (defined in _common.py)
  - Strips all EXIF metadata (removes camera GPS, owner info, etc.)
  - Writes photos/nj/{OBJECTID}/{idx}.jpg, {idx}-thumb.jpg, manifest.json

Skips registration certificates (is_certificate=True) by default — they're
scanned forms, not useful photography.

Re-runs are cheap: skips work when outputs already exist.

Run: .venv/bin/python scripts/fetch_nj_photos.py [--include-certificates] [--force]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests

from _common import process_image_bytes

LAYER = (
    "https://services1.arcgis.com/QWdNfRs7lkPq4g4Q/ArcGIS/rest/services/"
    "NJDEP_Big_and_Heritage_Trees_in_New_Jersey/FeatureServer/19"
)
ROOT = Path(__file__).resolve().parent.parent
TREES = ROOT / "data" / "nj" / "trees.json"
PHOTOS = ROOT / "photos" / "nj"


def attachment_url(object_id: str, attachment_id: int) -> str:
    return f"{LAYER}/{object_id}/attachments/{attachment_id}"


def process_one(object_id: str, idx: int, attachment_id: int, force: bool) -> tuple[bool, str]:
    tree_dir = PHOTOS / str(object_id)
    main_path = tree_dir / f"{idx}.jpg"
    thumb_path = tree_dir / f"{idx}-thumb.jpg"
    if not force and main_path.exists() and thumb_path.exists():
        return False, "cached"

    url = attachment_url(object_id, attachment_id)
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    w, h = process_image_bytes(r.content, main_path, thumb_path)
    return True, f"{w}x{h}"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--include-certificates",
        action="store_true",
        help="Also download scanned registration certificates (default: skip)",
    )
    p.add_argument("--force", action="store_true", help="Re-download and re-process even if outputs exist")
    p.add_argument("--limit", type=int, default=0, help="Process only this many trees (0 = all)")
    args = p.parse_args()

    data = json.loads(TREES.read_text())
    trees = data["trees"]
    if args.limit:
        trees = trees[: args.limit]

    PHOTOS.mkdir(parents=True, exist_ok=True)

    total_photos = sum(
        1 for t in trees for ph in t["photos"] if args.include_certificates or not ph["is_certificate"]
    )
    print(f"Processing up to {total_photos} photos across {len(trees)} trees ...")

    done = 0
    downloaded = 0
    errors: list[str] = []
    started = time.time()

    for t in trees:
        oid = t["id"]
        photos = [ph for ph in t["photos"] if args.include_certificates or not ph["is_certificate"]]
        manifest_entries = []
        for idx, photo in enumerate(photos, start=1):
            try:
                did_download, msg = process_one(oid, idx, photo["attachment_id"], args.force)
                if did_download:
                    downloaded += 1
                done += 1
                manifest_entries.append(
                    {
                        "idx": idx,
                        "attachment_id": photo["attachment_id"],
                        "original_name": photo["name"],
                        "is_certificate": photo["is_certificate"],
                        "main": f"{idx}.jpg",
                        "thumb": f"{idx}-thumb.jpg",
                    }
                )
                if done % 25 == 0:
                    elapsed = time.time() - started
                    rate = done / elapsed if elapsed > 0 else 0
                    remaining = (total_photos - done) / max(rate, 0.1)
                    print(f"  {done}/{total_photos}  ({downloaded} downloaded, {rate:.1f}/s, ~{remaining:.0f}s remaining)")
            except Exception as exc:  # noqa: BLE001
                msg = f"oid={oid} attachment={photo['attachment_id']}: {exc}"
                errors.append(msg)
                print(f"  ERROR {msg}", file=sys.stderr)

        if manifest_entries:
            (PHOTOS / str(oid) / "manifest.json").write_text(json.dumps(manifest_entries, indent=2))

    elapsed = time.time() - started
    print(f"\nDone in {elapsed:.0f}s. {done} processed, {downloaded} newly downloaded, {len(errors)} errors.")
    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"  {e}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
