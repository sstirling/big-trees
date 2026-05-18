"""Render Open Graph / Twitter social cards via headless Chrome.

For each template HTML in og/template-*.html, screenshot at 1200x630 and write
to og/{name}.png. The HTML loads the same fonts and photos the live site uses,
so the social card stays visually consistent with the site without us having
to typeset by hand in Pillow.

Run: .venv/bin/python scripts/build_og_cards.py

Dependencies: a working headless Chrome on the host. We default to macOS's
Google Chrome.app; override CHROME_BIN to point elsewhere.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OG_DIR = ROOT / "og"

DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def chrome_bin() -> str:
    return os.environ.get("CHROME_BIN", DEFAULT_CHROME)


def render(template: Path, output: Path) -> bool:
    if not template.exists():
        print(f"  ! template missing: {template}", file=sys.stderr)
        return False
    cmd = [
        chrome_bin(),
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--force-device-scale-factor=1",
        "--window-size=1200,630",
        # Give the page time to load fonts + photo before snapshot.
        "--virtual-time-budget=4000",
        f"--screenshot={output}",
        f"file://{template.resolve()}",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=60)
    except subprocess.TimeoutExpired:
        print(f"  ! Chrome timed out rendering {template.name}", file=sys.stderr)
        return False
    if result.returncode != 0 or not output.exists():
        print(f"  ! Chrome failed for {template.name}: {result.stderr.decode()[:300]}", file=sys.stderr)
        return False
    return True


def main() -> int:
    if not Path(chrome_bin()).exists():
        print(f"Chrome not found at {chrome_bin()}. Set CHROME_BIN or install Chrome.", file=sys.stderr)
        return 1
    OG_DIR.mkdir(exist_ok=True)
    templates = sorted(OG_DIR.glob("template-*.html"))
    if not templates:
        print("No templates found in og/. Expected og/template-*.html.", file=sys.stderr)
        return 1
    started = time.time()
    rendered = 0
    for tpl in templates:
        name = tpl.stem.replace("template-", "")  # template-site -> site
        png_tmp = OG_DIR / f".{name}.png"
        out = OG_DIR / f"{name}.jpg"
        print(f"  rendering {tpl.name} -> {out.name}")
        if render(tpl, png_tmp):
            # Re-encode as JPEG. OG cards are photo-heavy; JPEG cuts ~85% file
            # size with no visible quality loss at OG sizes.
            img = Image.open(png_tmp).convert("RGB")
            img.save(out, "JPEG", quality=88, optimize=True, progressive=True)
            png_tmp.unlink()
            size_kb = out.stat().st_size / 1024
            print(f"    ok ({size_kb:.0f} KB)")
            rendered += 1
    print(f"\nDone in {time.time() - started:.1f}s. {rendered}/{len(templates)} cards rendered.")
    return 0 if rendered == len(templates) else 1


if __name__ == "__main__":
    sys.exit(main())
