"""Generate the illustrative product images for the customizable catalog.

These are self-made SVG mock-ups (flat shapes + a dashed "your design here"
print area). They are labelled as illustrations, not product photos, so no
third-party image rights are involved. Re-running overwrites the same files.

    python scripts/make_catalog_images.py
"""

from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "seed" / "images" / "custom"

W, H = 600, 450


def frame(body: str, bg: str, label: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{label}">
  <rect width="{W}" height="{H}" fill="{bg}"/>
{body}
  <text x="{W - 16}" y="{H - 14}" text-anchor="end" font-family="Segoe UI, Arial, sans-serif" font-size="13" fill="#5f574f">Illustration</text>
</svg>
"""


def print_area(x: int, y: int, w: int, h: int, rx: int = 10) -> str:
    return (
        f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="none" '
        f'stroke="#1d1a16" stroke-opacity="0.55" stroke-width="3" stroke-dasharray="10 7"/>\n'
        f'  <text x="{x + w / 2}" y="{y + h / 2 + 6}" text-anchor="middle" '
        f'font-family="Segoe UI, Arial, sans-serif" font-size="18" fill="#1d1a16" fill-opacity="0.7">Your design</text>'
    )


def tshirt(color: str) -> str:
    return (
        f'  <path d="M210 90 L255 70 Q300 100 345 70 L390 90 L455 150 L415 195 L390 175 L390 390 '
        f'L210 390 L210 175 L185 195 L145 150 Z" fill="{color}" stroke="#1d1a16" stroke-opacity="0.25" stroke-width="3"/>\n'
        + print_area(240, 170, 120, 120)
    )


def hoodie(color: str) -> str:
    return (
        f'  <path d="M205 105 L250 80 Q300 40 350 80 L395 105 L460 260 L420 275 L395 205 L395 395 '
        f'L205 395 L205 205 L180 275 L140 260 Z" fill="{color}" stroke="#1d1a16" stroke-opacity="0.25" stroke-width="3"/>\n'
        '  <path d="M255 82 Q300 140 345 82" fill="none" stroke="#1d1a16" stroke-opacity="0.35" stroke-width="4"/>\n'
        '  <rect x="245" y="320" width="110" height="45" rx="8" fill="#000" fill-opacity="0.08"/>\n'
        + print_area(245, 165, 110, 110)
    )


def mug(color: str) -> str:
    return (
        f'  <rect x="185" y="110" width="200" height="240" rx="18" fill="{color}" stroke="#1d1a16" stroke-opacity="0.25" stroke-width="3"/>\n'
        '  <path d="M385 160 Q455 160 455 230 Q455 300 385 300" fill="none" stroke="#1d1a16" stroke-opacity="0.3" stroke-width="22"/>\n'
        f'  <path d="M385 160 Q455 160 455 230 Q455 300 385 300" fill="none" stroke="{color}" stroke-width="14"/>\n'
        + print_area(215, 165, 140, 130)
    )


def cap(color: str) -> str:
    return (
        f'  <path d="M170 280 Q170 120 300 120 Q430 120 430 280 Z" fill="{color}" stroke="#1d1a16" stroke-opacity="0.25" stroke-width="3"/>\n'
        f'  <path d="M150 280 L450 280 Q520 290 470 320 L150 320 Z" fill="{color}" stroke="#1d1a16" stroke-opacity="0.3" stroke-width="3"/>\n'
        '  <circle cx="300" cy="122" r="9" fill="#1d1a16" fill-opacity="0.35"/>\n'
        + print_area(240, 175, 120, 80)
    )


def tote(color: str) -> str:
    return (
        '  <path d="M240 150 Q240 70 300 70 Q360 70 360 150" fill="none" stroke="#8a5a1c" stroke-width="14"/>\n'
        f'  <rect x="170" y="140" width="260" height="260" rx="6" fill="{color}" stroke="#1d1a16" stroke-opacity="0.25" stroke-width="3"/>\n'
        + print_area(215, 190, 170, 160)
    )


IMAGES = {
    "classic-tee.svg": frame(tshirt("#ffffff"), "#e9e4da", "Classic cotton T-shirt illustration"),
    "heavyweight-tee.svg": frame(tshirt("#2f3b4c"), "#dfe6ee", "Heavyweight T-shirt illustration"),
    "pullover-hoodie.svg": frame(hoodie("#5b7a5e"), "#e5ece2", "Pullover hoodie illustration"),
    "ceramic-mug.svg": frame(mug("#ffffff"), "#efe5d8", "Ceramic mug illustration"),
    "baseball-cap.svg": frame(cap("#a2442f"), "#f2e2d9", "Baseball cap illustration"),
    "canvas-tote.svg": frame(tote("#e7d8b9"), "#f4efe3", "Canvas tote bag illustration"),
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, svg in IMAGES.items():
        (OUT / name).write_text(svg, encoding="utf-8")
        print(f"wrote {OUT / name}")


if __name__ == "__main__":
    main()
