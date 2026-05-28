#!/usr/bin/env python3
"""Generate local placeholder images for Trail 5 theme."""
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    raise SystemExit("Install Pillow: pip install Pillow")

ASSETS = [
    ("body-exfoliation.jpg", (180, 200, 210), (120, 140, 155)),
    ("body-care.jpg", (200, 190, 175), (150, 130, 110)),
    ("hero-wellness.jpg", (40, 60, 80), (8, 145, 178)),
    ("beauty-face.jpg", (230, 210, 200), (200, 170, 160)),
    ("lab-science.jpg", (220, 225, 230), (160, 170, 185)),
    ("moisturizer.jpg", (245, 240, 235), (200, 210, 220)),
    ("skincare-products.jpg", (210, 215, 205), (170, 180, 165)),
    ("home-featured.jpg", (30, 40, 50), (8, 145, 178)),
    ("author.jpg", (200, 195, 190), (140, 130, 125)),
    ("reviewer.jpg", (195, 200, 205), (130, 145, 160)),
    ("expert-1.jpg", (220, 215, 210), (160, 150, 140)),
    ("expert-2.jpg", (215, 220, 225), (150, 160, 175)),
    ("expert-3.jpg", (210, 205, 200), (145, 135, 125)),
    ("expert-4.jpg", (205, 210, 215), (140, 150, 165)),
]

W, H = 800, 520


def make_image(path: Path, c1: tuple, c2: tuple) -> None:
    img = Image.new("RGB", (W, H), c1)
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        r = int(c1[0] * (1 - t) + c2[0] * t)
        g = int(c1[1] * (1 - t) + c2[1] * t)
        b = int(c1[2] * (1 - t) + c2[2] * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))
    draw.ellipse([W // 4, H // 5, 3 * W // 4, 4 * H // 5], outline=(255, 255, 255, 40))
    img.save(path, "JPEG", quality=85)


def main() -> None:
    out = Path(__file__).resolve().parent / "shared" / "assets"
    out.mkdir(parents=True, exist_ok=True)
    for name, c1, c2 in ASSETS:
        make_image(out / name, c1, c2)
    print(f"Generated {len(ASSETS)} images in {out}")


if __name__ == "__main__":
    main()
