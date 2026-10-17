"""Draw the app's PNG and .ico icons from public/favicon.svg.

The SVG is the one source: a background rectangle, a filled spade and a
stroked "2". This reads those three shapes and draws them with Pillow, so no
SVG library is needed. Only the path commands the icon uses (M, C, L, Z,
absolute) are understood.

    python frontend/scripts/make_icons.py

Writes into frontend/public:
  icon-180.png   iPhone home screen (apple-touch-icon); square, iOS rounds it
  icon-192.png   web app manifest
  icon-512.png   web app manifest
  favicon.ico    16, 32 and 48 px, rounded corners, for browsers without SVG icons
"""
from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw

PUBLIC = Path(__file__).resolve().parent.parent / 'public'
SUPERSAMPLE = 8          # draw this many times larger, then scale down
STEPS = 24               # points per curve segment


def parse_path(d: str) -> list[tuple[float, float]]:
    """The path's outline as points, curves flattened into short lines."""
    tokens = re.findall(r'[MCLZ]|-?\d+(?:\.\d+)?', d)
    points: list[tuple[float, float]] = []
    i = 0
    cmd = ''
    while i < len(tokens):
        if tokens[i] in 'MCLZ':
            cmd = tokens[i]
            i += 1
            if cmd == 'Z':
                continue
        nums = lambda n: [float(t) for t in tokens[i:i + n]]
        if cmd in 'ML':
            x, y = nums(2)
            points.append((x, y))
            i += 2
        elif cmd == 'C':
            x1, y1, x2, y2, x, y = nums(6)
            x0, y0 = points[-1]
            for s in range(1, STEPS + 1):
                t = s / STEPS
                u = 1 - t
                points.append((
                    u**3 * x0 + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t**3 * x,
                    u**3 * y0 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t**3 * y,
                ))
            i += 6
        else:
            raise ValueError(f'unsupported path command {cmd!r}')
    return points


def read_svg(path: Path) -> dict:
    svg = path.read_text(encoding='utf-8')
    rect = re.search(r'<rect [^>]*rx="([\d.]+)"[^>]*fill="(#[0-9a-fA-F]{6})"', svg)
    shapes = re.findall(r'<path d="([^"]+)"([^>]*)/>', svg)
    fill_d, fill_attrs = shapes[0]
    stroke_d, stroke_attrs = shapes[1]
    return {
        'radius': float(rect.group(1)),
        'background': rect.group(2),
        'fill': (parse_path(fill_d), re.search(r'fill="(#\w+)"', fill_attrs).group(1)),
        'stroke': (parse_path(stroke_d), re.search(r'stroke="(#\w+)"', stroke_attrs).group(1),
                   float(re.search(r'stroke-width="([\d.]+)"', stroke_attrs).group(1))),
    }


def render(icon: dict, size: int, rounded: bool, stroke_scale: float = 1.0) -> Image.Image:
    big = size * SUPERSAMPLE
    k = big / 100
    img = Image.new('RGBA', (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    if rounded:
        draw.rounded_rectangle([0, 0, big - 1, big - 1], radius=icon['radius'] * k, fill=icon['background'])
    else:
        draw.rectangle([0, 0, big - 1, big - 1], fill=icon['background'])

    outline, colour = icon['fill']
    draw.polygon([(x * k, y * k) for x, y in outline], fill=colour)

    # A round-capped, round-joined stroke: a line per segment, a dot per point.
    line, colour, width = icon['stroke']
    w = width * k * stroke_scale
    pts = [(x * k, y * k) for x, y in line]
    draw.line(pts, fill=colour, width=round(w))
    for x, y in pts:
        draw.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=colour)

    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    icon = read_svg(PUBLIC / 'favicon.svg')
    # Home-screen and manifest icons are full squares: the phone cuts the corners.
    for size in (180, 192, 512):
        render(icon, size, rounded=False).convert('RGB').save(PUBLIC / f'icon-{size}.png', optimize=True)
    # At 16px a 7-unit stroke is barely a pixel: thicken the 2 a little.
    sizes = {16: render(icon, 16, True, 1.3), 32: render(icon, 32, True), 48: render(icon, 48, True)}
    sizes[48].save(PUBLIC / 'favicon.ico', sizes=[(16, 16), (32, 32), (48, 48)],
                   append_images=[sizes[16], sizes[32]])
    for name in ('icon-180.png', 'icon-192.png', 'icon-512.png', 'favicon.ico'):
        print(PUBLIC / name, (PUBLIC / name).stat().st_size, 'bytes')


if __name__ == '__main__':
    main()
