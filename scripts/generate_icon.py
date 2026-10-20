"""Render the project's original wallet/network icon, without external assets."""

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
d.rounded_rectangle(box((80, 174, 420, 410)), radius=42 * S, fill="#32d5bf")
d.rounded_rectangle(box((80, 145, 382, 226)), radius=28 * S, fill="#8aeee0")
d.rounded_rectangle(box((303, 257, 442, 342)), radius=23 * S, fill="#123449")
d.ellipse(box((331, 285, 361, 315)), fill="#ffffff")
# Wi-Fi waves emerging above the wallet.
d.arc(box((196, 42, 392, 238)), 220, 320, fill="#ffffff", width=19 * S)
d.arc(box((235, 83, 353, 201)), 220, 320, fill="#ffffff", width=18 * S)
d.ellipse(box((284, 136, 304, 156)), fill="#ffffff")
for size, filename in [(256, "icon.png"), (512, "icon@2x.png")]:
    im.resize((size, size), Image.Resampling.LANCZOS).save(BRAND / filename, optimize=True)
