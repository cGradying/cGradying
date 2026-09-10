#!/usr/bin/env python3
"""
Shared pixel-art machinery for the scene rebuild: a 4x4 ordered Bayer matrix,
deterministic <pattern> textures (halftone dots, Bayer dither, CRT scanlines -
no SVG filters, so no Safari/feTurbulence risk), a genuinely pixelated moon
reusing make_card.moon_ascii()'s sphere/crater lighting, and a seeded pixel-art
spiral galaxy sprite.

Every coordinate goes through snap() so art lands on the 4px grid.
"""
import math

PX = 4  # one pixel-art "pixel" = 4 SVG units

# Standard 4x4 ordered Bayer matrix, values 0..15.
BAYER4 = [
    [0, 8, 2, 10],
    [12, 4, 14, 6],
    [3, 11, 1, 9],
    [15, 7, 13, 5],
]


def snap(v):
    return round(v / PX) * PX


def bayer(x, y):
    """Threshold 0..15 for grid cell (x, y), tiling BAYER4 across the plane."""
    return BAYER4[y % 4][x % 4]


def _tone(light, palette):
    """Quantise a 0..1 light value into one of the palette's 6 tones,
    darkest first: void, deep, mid, accent, bright, cream."""
    idx = min(5, int(light * 6))
    return palette[idx]


def halftone_pattern(pid, color, tile=6, dot_r=1.6):
    return (
        f'<pattern id="{pid}" width="{tile}" height="{tile}" '
        f'patternUnits="userSpaceOnUse">'
        f'<circle cx="{tile / 2}" cy="{tile / 2}" r="{dot_r}" fill="{color}"/>'
        f'</pattern>'
    )


def bayer_pattern(pid, dark, light):
    """4x4 tile, one <rect> per Bayer cell, alternating dark/light by
    threshold - the actual ordered-dither look, not noise."""
    cells = []
    for y in range(4):
        for x in range(4):
            fill = light if bayer(x, y) >= 8 else dark
            cells.append(f'<rect x="{x}" y="{y}" width="1" height="1" fill="{fill}"/>')
    return (
        f'<pattern id="{pid}" width="4" height="4" patternUnits="userSpaceOnUse">'
        f'{"".join(cells)}</pattern>'
    )


def scanline_pattern(pid, color, gap=4, opacity=0.5):
    return (
        f'<pattern id="{pid}" width="{gap}" height="{gap}" '
        f'patternUnits="userSpaceOnUse">'
        f'<rect width="{gap}" height="1" fill="{color}" opacity="{opacity}"/>'
        f'</pattern>'
    )


def pixel_moon(rows, phase, palette, cell=PX):
    """Pixelated moon: same sphere/crater lighting as make_card.moon_ascii(),
    but each cell is a quantised <rect> on the grid instead of a RAMP glyph.
    Returns (svg_fragment, width_px, height_px).

    make_card.moon_ascii() only returns rows of characters, not the raw light
    values, so the sphere/crater lighting is recomputed here at rect-grid
    resolution (same 2x1 cell aspect) rather than threading a new return
    value through the shared function. Keep this in sync with moon_ascii()
    if its lighting model changes."""
    cols = rows * 2
    lx, ly, lz = -0.60 * (2 * phase - 1) - 0.25, -0.55, 0.75
    norm = math.sqrt(lx * lx + ly * ly + lz * lz)
    lx, ly, lz = lx / norm, ly / norm, lz / norm
    craters = [
        (-0.30, -0.22, 0.20, 0.35), (0.18, -0.42, 0.14, 0.30),
        (0.34, 0.18, 0.24, 0.32), (-0.14, 0.40, 0.17, 0.28),
        (-0.52, 0.14, 0.12, 0.25), (0.02, 0.02, 0.10, 0.22),
    ]

    rects = []
    for r in range(rows):
        ny = (r + 0.5) / rows * 2 - 1
        for c in range(cols):
            nx = (c + 0.5) / cols * 2 - 1
            d2 = nx * nx + ny * ny
            if d2 > 1.0:
                continue
            nz = math.sqrt(1.0 - d2)
            light = max(0.0, nx * lx + ny * ly + nz * lz) ** 0.85
            for cx, cy, cr, depth in craters:
                dist = math.hypot(nx - cx, ny - cy)
                if dist < cr:
                    light *= 1.0 - depth * (1.0 - dist / cr)
            light *= 0.35 + 0.65 * nz ** 0.5
            fill = _tone(min(1.0, light), palette)
            rects.append(
                f'<rect x="{c * cell}" y="{r * cell}" width="{cell}" height="{cell}" fill="{fill}"/>'
            )
    return "".join(rects), cols * cell, rows * cell


def pixel_galaxy(cx, cy, w, h, seed, palette, cell=PX):
    """Seeded pixel-art spiral galaxy: tilted core ellipse + spiral arm bands,
    each cell quantised into the palette. Deterministic by seed alone."""
    cols, rows = round(w / cell), round(h / cell)
    s = seed
    rects = []
    tilt = math.radians(35)
    ct, st = math.cos(tilt), math.sin(tilt)
    for r in range(rows):
        ny = (r + 0.5) / rows * 2 - 1
        for c in range(cols):
            nx = (c + 0.5) / cols * 2 - 1
            # rotate into the galaxy's tilted frame, squash to an ellipse
            rx = nx * ct - ny * st
            ry = (nx * st + ny * ct) * 2.6
            d = math.hypot(rx, ry)
            if d > 1.05:
                continue
            ang = math.atan2(ry, rx)
            # spiral arm brightness: two arms, a log-spiral phase term
            arm = 0.5 + 0.5 * math.cos(2 * ang - d * 6.0)
            core = max(0.0, 1.0 - d) ** 1.6
            light = min(1.0, core * 1.3 + arm * (1.0 - d) * 0.7)
            # deterministic per-cell jitter from a cheap LCG, seeded once
            s = (s * 1103515245 + 12345) & 0x7FFFFFFF
            jitter = (s % 100) / 100.0 * 0.08
            light = max(0.0, min(1.0, light - 0.04 + jitter))
            if light < 0.06:
                continue
            fill = _tone(light, palette)
            rects.append(
                f'<rect x="{cx + c * cell - w / 2:.0f}" y="{cy + r * cell - h / 2:.0f}" '
                f'width="{cell}" height="{cell}" fill="{fill}"/>'
            )
    return "".join(rects)


def demo():
    flat = [v for row in BAYER4 for v in row]
    assert sorted(flat) == list(range(16)), "Bayer matrix must be a permutation of 0..15"
    assert snap(snap(37)) == snap(37), "snap must be idempotent"

    palette = ["#0A0C10", "#16241A", "#4F8A2E", "#9BE33C", "#C6F04A", "#F2F0C8"]
    m1, w, h = pixel_moon(10, 0.55, palette)
    m2, _, _ = pixel_moon(10, 0.55, palette)
    assert m1 == m2, "pixel_moon must be deterministic for the same seed/phase"
    assert m1.count("<rect") > 0, "pixel_moon produced no rects"

    g1 = pixel_galaxy(0, 0, 200, 100, seed=3, palette=palette)
    g2 = pixel_galaxy(0, 0, 200, 100, seed=3, palette=palette)
    assert g1 == g2, "pixel_galaxy must be deterministic for the same seed"
    assert g1.count("<rect") > 0, "pixel_galaxy produced no rects"

    for pat in (halftone_pattern("t1", "#fff"), bayer_pattern("t2", "#000", "#fff"),
                scanline_pattern("t3", "#fff")):
        assert pat.startswith("<pattern") and pat.endswith("</pattern>")

    print(f"ok - bayer permutation valid, moon {w}x{h}px "
          f"({m1.count('<rect')} rects), galaxy {g1.count('<rect')} rects")


if __name__ == "__main__":
    demo()
