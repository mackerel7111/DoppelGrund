"""Equirectangular hex index image (contract C6 ``earth_index_4096x2048.png``).

Pixel value = ``row + 1`` encoded ``R*65536 + G*256 + B``; 0 = no hex; x = 0 at longitude -180 and
y = 0 at latitude +90. Hexes that cross the antimeridian are drawn twice, once at each image edge.
"""

from __future__ import annotations

from collections.abc import Sequence

import h3
from PIL import Image, ImageDraw

INDEX_W, INDEX_H = 4096, 2048


def unwrap(lngs: list[float]) -> list[float]:
    """One polygon's longitudes as a continuous run: a span over 180 degrees is shifted east."""
    if max(lngs) - min(lngs) > 180.0:
        return [x + 360.0 if x < 0 else x for x in lngs]
    return lngs


def rasterise_index(
    cells: Sequence[str], width: int = INDEX_W, height: int = INDEX_H
) -> Image.Image:
    """Rasterise H3 cells onto a ``width`` x ``height`` RGB image; value = row + 1 (C6)."""
    img = Image.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    sx, sy = width / 360.0, height / 180.0
    for row, cell in enumerate(cells):
        v = row + 1
        colour = ((v >> 16) & 255, (v >> 8) & 255, v & 255)
        boundary = h3.cell_to_boundary(cell)
        lats = [p[0] for p in boundary]
        lngs = unwrap([p[1] for p in boundary])
        shifts = [0.0, -360.0] if max(lngs) > 180.0 else [0.0]
        for shift in shifts:
            pts = [
                ((x + shift + 180.0) * sx, (90.0 - y) * sy) for x, y in zip(lngs, lats, strict=True)
            ]
            draw.polygon(pts, fill=colour)
    return img
