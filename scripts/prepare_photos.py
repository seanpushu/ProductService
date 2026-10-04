"""Turn the licensed source photos into web-sized catalog images.

    python scripts/prepare_photos.py <photos_dir>

Each output is a 1200x900 (4:3, matches the card) progressive JPEG, centre-
cropped, EXIF stripped, quality 82. Sources and licences are recorded in
seed/images/photos/SOURCES.md. Requires Pillow (dev-only, not a service dep).
"""

import sys
from pathlib import Path

from PIL import Image, ImageOps

OUT = Path(__file__).resolve().parents[1] / "seed" / "images" / "photos"
SIZE = (1200, 900)

# output name -> (source file, horizontal focus 0..1, vertical focus 0..1)
PLAN = {
    "classic-tee.jpg": ("classic-tee-white.jpg", 0.5, 0.5),
    "heavyweight-tee.jpg": ("classic-tee-white-alternative.jpg", 0.5, 0.5),
    "pullover-hoodie.jpg": ("pullover-hoodie-brown.jpg", 0.5, 0.42),
    "ceramic-mug.jpg": ("ceramic-mug-white.jpg", 0.5, 0.5),
    "baseball-cap.jpg": ("baseball-cap-white.jpg", 0.5, 0.5),
    "canvas-tote.jpg": ("canvas-tote-lifestyle.jpg", 0.5, 0.5),
}


def main(src_dir: Path) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for out_name, (src_name, fx, fy) in PLAN.items():
        with Image.open(src_dir / src_name) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            im.draft("RGB", (SIZE[0] * 2, SIZE[1] * 2))  # fast decode for very large JPEGs
            fitted = ImageOps.fit(im, SIZE, method=Image.Resampling.LANCZOS, centering=(fx, fy))
            dest = OUT / out_name
            fitted.save(dest, "JPEG", quality=82, optimize=True, progressive=True)
            print(f"{out_name}: {src_name} {im.size} -> {SIZE}, {dest.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
