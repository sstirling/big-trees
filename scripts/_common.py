"""Shared helpers for the NJ + PA photo pipelines.

We resize to the same target dimensions across both states so the frontend
can use a single set of <img> sizes. EXIF (including GPS) is always stripped.

Target sizes are kept here as the single source of truth.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageOps

MAIN_WIDTH = 900
THUMB_WIDTH = 350
MAIN_QUALITY = 78
THUMB_QUALITY = 72


def resize_to_width(img: Image.Image, width: int) -> Image.Image:
    if img.width <= width:
        return img.copy()
    h = round(img.height * (width / img.width))
    return img.resize((width, h), Image.LANCZOS)


def process_image_bytes(content: bytes, main_path: Path, thumb_path: Path) -> tuple[int, int]:
    """Decode, EXIF-strip, resize, and save both main and thumb sizes.

    Returns (source_width, source_height) so callers can log it.
    """
    src = Image.open(io.BytesIO(content))
    # Apply any EXIF orientation, then drop EXIF on save.
    src = ImageOps.exif_transpose(src)
    if src.mode != "RGB":
        src = src.convert("RGB")

    main_path.parent.mkdir(parents=True, exist_ok=True)
    main = resize_to_width(src, MAIN_WIDTH)
    thumb = resize_to_width(src, THUMB_WIDTH)
    main.save(main_path, "JPEG", quality=MAIN_QUALITY, optimize=True, progressive=True)
    thumb.save(thumb_path, "JPEG", quality=THUMB_QUALITY, optimize=True, progressive=True)
    return src.width, src.height


def inches_to_eng(inches: int | float | None) -> str | None:
    """323 -> "26' 11\"" (matching the NJ source field format)."""
    if inches is None:
        return None
    inches = int(round(inches))
    feet, rem = divmod(inches, 12)
    return f"{feet}' {rem}\""
