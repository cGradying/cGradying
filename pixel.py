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


def value_noise(seed):
    """Seeded 2-octave value noise. Returns f(nx, ny) -> 0..1, smooth and
    deterministic. Pure Python (no numpy - the repo's one dep stays put)."""
    def _hash(ix, iy):
        h = (ix * 374761393 + iy * 668265263 + seed * 2246822519) & 0xFFFFFFFF
        h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
        h ^= h >> 16
        return (h & 0xFFFFFFFF) / 0xFFFFFFFF

    def _smooth(t):
        return t * t * (3 - 2 * t)

    def _lattice(x, y):
        x0, y0 = math.floor(x), math.floor(y)
        sx, sy = _smooth(x - x0), _smooth(y - y0)
        n00, n10 = _hash(x0, y0), _hash(x0 + 1, y0)
        n01, n11 = _hash(x0, y0 + 1), _hash(x0 + 1, y0 + 1)
        top = n00 + sx * (n10 - n00)
        bot = n01 + sx * (n11 - n01)
        return top + sy * (bot - top)

    def f(nx, ny):
        a = _lattice(nx * 4, ny * 4)
        b = _lattice(nx * 8, ny * 8)
        return max(0.0, min(1.0, a * 0.65 + b * 0.35))
    return f


def nebula(cols, rows, seed):
    """Per-cell 0..1 light grid: value_noise warped by distance from a seeded
    light origin, so brightness genuinely falls off across the field instead
    of reading as uniform noise. This is the 'generated image' the ASCII
    shader reads from."""
    noise = value_noise(seed)
    ox = 0.28 + (seed % 7) / 10.0
    oy = 0.22 + (seed % 5) / 10.0
    grid = []
    for r in range(rows):
        ny = r / max(1, rows - 1)
        row = []
        for c in range(cols):
            nx = c / max(1, cols - 1)
            base = noise(nx, ny)
            dist = math.hypot(nx - ox, ny - oy)
            falloff = max(0.0, 1.0 - dist * 1.05)
            row.append(max(0.0, min(1.0, base * 0.55 + falloff * 0.55)))
        grid.append(row)
    return grid


def _esc_ascii(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def ascii_field(grid, palette, ramp, cw, ch, density=1.0):
    """Render a light grid as a full glyph field: one <text> per row, adjacent
    same-tone cells merged into a single <tspan> run so the node count stays
    manageable (~1.5k per state, not one node per cell). `density` scales the
    light before the ramp/tone lookup - the knob that makes pre-rendered
    states A/B/C actually differ."""
    lines = []
    for r, row in enumerate(grid):
        y = (r + 1) * ch
        runs = []
        for v in row:
            light = max(0.0, min(1.0, v * density))
            gi = min(len(ramp) - 1, int(light * (len(ramp) - 1) + 0.5))
            glyph, color = ramp[gi], _tone(light, palette)
            if runs and runs[-1][1] == color:
                runs[-1][0] += glyph
            else:
                runs.append([glyph, color])
        tspans = "".join(
            f'<tspan fill="{color}">{_esc_ascii(text)}</tspan>' for text, color in runs
        )
        lines.append(
            f'<text x="0" y="{y:.1f}" font-family="monospace" font-size="{ch}" '
            f'textLength="{len(row) * cw}" lengthAdjust="spacingAndGlyphs" '
            f'xml:space="preserve">{tspans}</text>'
        )
    return "".join(lines)


def halftone_field(grid, color, cell=6):
    """Screened-photo halftone: one <circle> per cell, radius scaled by that
    cell's light value (not the fixed-radius dot screen halftone_pattern
    draws) - the gradient in dot size is what reads as a photograph."""
    maxr = cell * 0.42
    out = []
    for r, row in enumerate(grid):
        cy = (r + 0.5) * cell
        for c, v in enumerate(row):
            rad = maxr * max(0.0, min(1.0, v))
            if rad < 0.3:
                continue
            cx = (c + 0.5) * cell
            out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{rad:.2f}" fill="{color}"/>')
    return "".join(out)


def pixel_clip(pid, cell=PX):
    """A <mask> that screens whatever it's applied to into cell-sized squares
    with 1px gaps - gives a smooth vector path (a logo) a pixel-screened look
    with no bezier rasterizer.

    ponytail: this screens the source rather than resampling it into a true
    occupancy grid, so edge cells are partial coverage, not clean pixels.
    Upgrade to a real bezier -> 24x24 occupancy-grid rasterizer only if that
    reads badly at the sizes actually shipped."""
    tile, sq = cell, max(1, cell - 1)
    return (
        f'<pattern id="{pid}Tiles" width="{tile}" height="{tile}" '
        f'patternUnits="userSpaceOnUse">'
        f'<rect width="{tile}" height="{tile}" fill="#000"/>'
        f'<rect width="{sq}" height="{sq}" fill="#fff"/></pattern>'
        f'<mask id="{pid}"><rect width="100%" height="100%" fill="url(#{pid}Tiles)"/></mask>'
    )


def pixel_arc(cx, cy, r, frac, color, cell=PX):
    """Progress arc as grid-snapped squares instead of a smooth stroked path -
    same use as an SVG <circle> arc, but reads as pixel art."""
    n = max(8, int(2 * math.pi * r / cell))
    steps = max(0, int(n * max(0.0, min(1.0, frac))))
    out = []
    for i in range(steps + 1):
        ang = -math.pi / 2 + 2 * math.pi * i / n
        sx, sy = snap(cx + r * math.cos(ang)), snap(cy + r * math.sin(ang))
        out.append(
            f'<rect x="{sx - cell / 2:.0f}" y="{sy - cell / 2:.0f}" '
            f'width="{cell}" height="{cell}" fill="{color}"/>'
        )
    return "".join(out)


def pixel_bar(x, y, w, h, color, cell=PX):
    """A solid block quantised onto the grid, width/height rounded to whole
    cells - used for the language bar and the contribution-graph columns."""
    cols, rows = max(1, round(w / cell)), max(1, round(h / cell))
    out = []
    for r in range(rows):
        for c in range(cols):
            out.append(
                f'<rect x="{x + c * cell:.0f}" y="{y + r * cell:.0f}" '
                f'width="{cell}" height="{cell}" fill="{color}"/>'
            )
    return "".join(out), cols * cell, rows * cell


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

    noise = value_noise(9)
    v1, v2 = noise(0.3, 0.4), noise(0.3, 0.4)
    assert v1 == v2, "value_noise must be deterministic for the same seed/coords"
    assert 0.0 <= v1 <= 1.0, "value_noise out of range"

    grid = nebula(20, 20, seed=9)
    flat = [v for row in grid for v in row]
    assert max(flat) - min(flat) > 0.15, "nebula must not be a flat field"

    ramp = " .'`:,-~+=*coO08#%@"
    field = ascii_field(grid, palette, ramp, cw=8, ch=14)
    import re as _re
    glyphs = "".join(_re.findall(r">([^<]*)<", field))
    assert glyphs, "ascii_field produced no glyph text"
    assert set(glyphs) <= set(ramp), "ascii_field emitted a non-ramp character"
    assert '<text' in field

    half = halftone_field(grid, "#fff", cell=6)
    assert half.count("<circle") > 0, "halftone_field produced no dots"

    arc = pixel_arc(50, 50, 30, 0.5, "#fff")
    assert arc.count("<rect") > 0
    bar, bw, bh = pixel_bar(0, 0, 33, 9, "#fff")
    assert bw % PX == 0 and bh % PX == 0, "pixel_bar must snap to the grid"

    clip = pixel_clip("t4")
    assert "<mask" in clip and "<pattern" in clip

    print(f"ok - bayer permutation valid, moon {w}x{h}px "
          f"({m1.count('<rect')} rects), galaxy {g1.count('<rect')} rects, "
          f"nebula range {max(flat) - min(flat):.2f}")


if __name__ == "__main__":
    demo()
