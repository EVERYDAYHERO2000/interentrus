"""Render the project's original network icon, without external assets."""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "custom_components/isp_balance/brand"
BRAND.mkdir(parents=True, exist_ok=True)
# Draw at 4x for smooth edges, preserving transparent outer corners.
S = 4
im = Image.new("RGBA", (512 * S, 512 * S))
d = ImageDraw.Draw(im)


def box(coords):
    return tuple(round(x * S) for x in coords)


d.rounded_rectangle(box((0, 0, 512, 512)), radius=112 * S, fill="#123449")
# Globe: the integration covers internet accounts across providers.
d.ellipse(box((82, 82, 430, 430)), outline="#32d5bf", width=21 * S)
d.ellipse(box((164, 82, 348, 430)), outline="#ffffff", width=15 * S)
d.arc(box((82, 143, 430, 301)), 0, 360, fill="#ffffff", width=15 * S)
d.arc(box((82, 211, 430, 369)), 0, 360, fill="#ffffff", width=15 * S)
d.line(box((88, 256, 424, 256)), fill="#32d5bf", width=17 * S)
# Three network nodes make the mark readable at small sizes.
for cx, cy in [(256, 82), (104, 340), (408, 340)]:
    d.ellipse(box((cx - 25, cy - 25, cx + 25, cy + 25)), fill="#32d5bf")
for size, filename in [(256, "icon.png"), (512, "icon@2x.png")]:
    im.resize((size, size), Image.Resampling.LANCZOS).save(BRAND / filename, optimize=True)
