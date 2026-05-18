"""Download every pabigtrees.com tree photo, resize to web sizes, strip EXIF.

For each photo referenced by data/pa/trees.json:
  - GET https://www.pabigtrees.com/uploads/{img_location}
  - Resize and EXIF-strip via _common.process_image_bytes
  - Writes photos/pa/{TR_ID}/{idx}.jpg, {idx}-thumb.jpg, manifest.json

Throttles between fetches (default 1.0 sec) to be polite — robots.txt asks for
20 sec; we're well under that but well above hammering. The site uses
LiteSpeed which has its own rate-limiting, so this is mostly belt-and-suspenders.

Run: .venv/bin/python scripts/fetch_pa_photos.py [--limit N] [--force]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests

from _common import process_image_bytes

API = "https://www.pabigtrees.com"
ROOT = Path(__file__).resolve().parent.parent
TREES = ROOT / "data" / "pa" / "trees.json"
PHOTOS = ROOT / "photos" / "pa"

UA = "BigTreesNE/1.0 (https://github.com/stephenstirling/big-trees) research mirror"


def image_url(filename: str) -> str:
    # The live site loads images from /treeImages/, not /uploads/. The
    # /uploads/ path returns the React app shell for unknown filenames
    # (Express falls through to the SPA), so requests look like HTTP 200 but
    # serve HTML instead of the JPEG.
    return f"{API}/treeImages/{quote(filename, safe='')}"


def process_one(tree_id: str, idx: int, filename: str, force: bool) -> tuple[bool, str]:
    tree_dir = PHOTOS / tree_id
    main_path = tree_dir / f"{idx}.jpg"
    thumb_path = tree_dir / f"{idx}-thumb.jpg"
    if not force and main_path.exists() and thumb_path.exists():
        return False, "cached"

    url = image_url(filename)
    r = requests.get(url, headers={"User-Agent": UA}, timeout=90)
    if r.status_code == 404:
        return False, "404"
    r.raise_for_status()
    if not r.content or r.headers.get("content-type", "").startswith("text"):
        return False, "non-image"
    w, h = process_image_bytes(r.content, main_path, thumb_path)
    return True, f"{w}x{h}"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--force", action="store_true", help="Re-download and re-process even if outputs exist")
    p.add_argument("--limit", type=int, default=0, help="Process only this many trees (0 = all)")
    p.add_argument("--throttle", type=float, default=1.0, help="Seconds between network fetches")
    args = p.parse_args()

    data = json.loads(TREES.read_text())
    trees = data["trees"]
    if args.limit:
        trees = trees[: args.limit]

    PHOTOS.mkdir(parents=True, exist_ok=True)

    total_photos = sum(1 for t in trees for ph in t["photos"] if not ph["is_certificate"])
    print(f"Processing up to {total_photos} photos across {len(trees)} trees ...")

    done = 0
    downloaded = 0
    skipped = 0
    errors: list[str] = []
    started = time.time()

    for t in trees:
        tid = t["id"]
        photos = [ph for ph in t["photos"] if not ph["is_certificate"]]
        manifest_entries = []
        for idx, photo in enumerate(photos, start=1):
            try:
                did_download, msg = process_one(tid, idx, photo["img_location"], args.force)
                if did_download:
                    downloaded += 1
                    if args.throttle > 0:
                        time.sleep(args.throttle)
                elif msg == "404" or msg == "non-image":
                    skipped += 1
                done += 1
                manifest_entries.append(
                    {
                        "idx": idx,
                        "original_name": photo["img_location"],
                        "is_certificate": photo.get("is_certificate", False),
                        "main": f"{idx}.jpg",
                        "thumb": f"{idx}-thumb.jpg",
                    }
                )
                if done % 25 == 0:
                    elapsed = time.time() - started
                    rate = done / elapsed if elapsed else 0
                    remaining = (total_photos - done) / max(rate, 0.1)
                    print(
                        f"  {done}/{total_photos}  ({downloaded} downloaded, {skipped} skipped, "
                        f"{rate:.1f}/s, ~{remaining/60:.1f} min remaining)"
                    )
            except Exception as exc:  # noqa: BLE001
                msg = f"oid={tid} img={photo.get('img_location')}: {exc}"
                errors.append(msg)
                print(f"  ERROR {msg}", file=sys.stderr)

        if manifest_entries:
            tree_dir = PHOTOS / tid
            tree_dir.mkdir(parents=True, exist_ok=True)
            (tree_dir / "manifest.json").write_text(json.dumps(manifest_entries, indent=2))

    elapsed = time.time() - started
    print(
        f"\nDone in {elapsed:.0f}s. {done} processed, {downloaded} newly downloaded, "
        f"{skipped} skipped (404/non-image), {len(errors)} errors."
    )
    if errors:
        print("\nFirst 10 errors:")
        for e in errors[:10]:
            print(f"  {e}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
