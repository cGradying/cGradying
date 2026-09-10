#!/usr/bin/env python3
"""
PREVIEW - composes card + tech-stack + stats into one tall assets/scene.svg,
so the README embeds a single seamless image instead of three <img> tags with
a markdown gap between each.

Not wired into README.md or the workflow yet - this is a preview build only.
Run it, look at assets/scene.svg (or push a branch and view it on github.com),
then decide whether it replaces the three-panel README.

Each panel keeps rendering its own file unchanged (render(..., draw_bg=True)
default); this only asks each one for a version with its own background
suppressed (draw_bg=False), so one continuous gradient + dither field can run
behind all three instead of three separate panel backgrounds.

This is the merge-and-reskin slice of the pixel-scene plan. NOT yet included:
the 5x7 bitmap heading font and the logo pixel-rasterizer - those are a
separate slice pending the Safari/mobile filter check.
"""
import json
import os
import re

import make_card
import make_stack
import make_stats
import pixel
from make_card import PALETTE, STATS_PATH, THEME

OUT = "assets/scene.svg"
W = 940


def _root_attrs(svg_text):
    head = svg_text.split(">", 1)[0] + ">"
    w = float(re.search(r'width="([\d.]+)"', head).group(1))
    h = float(re.search(r'height="([\d.]+)"', head).group(1))
    m = re.search(r'aria-label="([^"]*)"', head)
    return w, h, (m.group(1) if m else "")


def _split(svg_text):
    """Pull (defs-inner, style-inner, body-inner, w, h, alt) out of one
    panel's rendered SVG, so its pieces can be re-stacked into the scene."""
    w, h, alt = _root_attrs(svg_text)
    defs = re.search(r"<defs>(.*?)</defs>", svg_text, re.S).group(1)
    style = re.search(r"<style>(.*?)</style>", svg_text, re.S).group(1)
    body = svg_text.split("</style>", 1)[1].rsplit("</svg>", 1)[0]
    return defs, style, body, w, h, alt


CELL_W, CELL_H = 10, 16  # glyph field cell size; coarsen if scene.svg clears ~2MB
RAMP = " .'`:,-~+=*coO08#%@"


def _atmosphere(H):
    """Full-canvas ASCII glyph shader over a seeded nebula, three pre-rendered
    density states cross-fading so it breathes rather than reading as static
    wallpaper. Halftone dots are radius-scaled by the same nebula (screened-
    photo look), bloom lifts the bright cells, a vignette pulls focus to
    centre, and CRT scanlines sit over everything. A seeded pixel-art galaxy
    sits dim behind the tech-stack panel."""
    t = THEME
    cols, rows = round(W / CELL_W), round(H / CELL_H)
    grid = pixel.nebula(cols, rows, seed=17)

    atm_a = pixel.ascii_field(grid, PALETTE, RAMP, CELL_W, CELL_H, density=0.82)
    atm_b = pixel.ascii_field(grid, PALETTE, RAMP, CELL_W, CELL_H, density=1.0)
    atm_c = pixel.ascii_field(grid, PALETTE, RAMP, CELL_W, CELL_H, density=1.18)
    half = pixel.halftone_field(grid, t["dim"], cell=CELL_W)

    # Bloom: only the bright cells (light > 0.75), blurred through the same
    # #glow filter make_card.py/make_stats.py already ship (proven through
    # Camo) and screened back over the field - this is the "soothing" glow.
    bright = [[v if v > 0.75 else 0.0 for v in row] for row in grid]
    bloom_field = pixel.halftone_field(bright, t["emerald_light"], cell=CELL_W)

    defs = pixel.scanline_pattern("scScan", "#000000", gap=4, opacity=0.35) + (
        f'<radialGradient id="vignette" cx="0.5" cy="0.42" r="0.75">'
        f'<stop offset="0%" stop-color="{t["bg_top"]}" stop-opacity="0"/>'
        f'<stop offset="100%" stop-color="{t["bg_top"]}" stop-opacity="0.55"/>'
        f'</radialGradient>'
    )
    galaxy = pixel.pixel_galaxy(W * 0.72, 660, 360, 220, seed=17, palette=PALETTE)
    body = (
        f'<rect width="{W}" height="{H}" fill="{t["bg_top"]}"/>'
        f'<g opacity="0.6">{half}</g>'
        f'<g class="galaxy" opacity="0.55">{galaxy}</g>'
        f'<g class="atm atmA">{atm_a}</g>'
        f'<g class="atm atmB">{atm_b}</g>'
        f'<g class="atm atmC">{atm_c}</g>'
        f'<g class="bloom" filter="url(#glow)">{bloom_field}</g>'
        f'<rect class="scanPulse" width="{W}" height="{H}" fill="url(#scScan)"/>'
        f'<rect width="{W}" height="{H}" fill="url(#vignette)"/>'
    )
    return defs, body


def render(stats, path=OUT):
    frags = [
        make_card.render(stats, "assets/_scene_card.svg", draw_bg=False),
        make_stack.render("assets/_scene_stack.svg", draw_bg=False)[0],
        make_stats.render(stats, "assets/_scene_stats.svg", draw_bg=False)[0],
    ]

    t = THEME
    plate_gap = 10  # atmosphere only shows in this margin, between/around plates
    parts, styles, bodies, alts, y = [], [], [], [], 0.0
    for i, fp in enumerate(frags):
        svg_text = open(fp, encoding="utf-8").read()
        defs, style, body, w, h, alt = _split(svg_text)
        assert w == W, f"{fp}: width {w} != scene width {W}"
        parts.append(defs)
        styles.append(style)
        # Solid plate behind the panel's own text/graphics - full-bleed
        # atmosphere reads through only in plate_gap around/between panels,
        # not directly behind any glyph.
        plate = (
            f'<rect x="{plate_gap}" y="{plate_gap:.1f}" width="{W - 2 * plate_gap}" '
            f'height="{h - 2 * plate_gap:.1f}" rx="14" fill="{t["panel"]}" '
            f'stroke="{t["border"]}"/>'
        )
        bodies.append(f'<g transform="translate(0,{y:.1f})">{plate}{body}</g>')
        alts.append(alt)
        y += h
        os.remove(fp)  # scratch fragment, not a committed asset

    # Each panel embeds its own @font-face (base64 pixel font, ~160KB) so it
    # stands alone as card.svg/tech-stack.svg/github-stats.svg - but merged
    # into one scene that's 3 identical copies. Keep only the first.
    from make_card import pixel_font_face
    face = pixel_font_face()
    styles = [face] + [s.replace(face, "", 1) for s in styles]

    H = round(y)
    field_defs, field_body = _atmosphere(H)
    parts.insert(0, field_defs)

    style_block = "".join(styles) + (
        ".galaxy{animation:galaxyDrift 10s ease-in-out infinite}"
        "@keyframes galaxyDrift{0%,100%{opacity:.5}50%{opacity:.65}}"
        ".scanPulse{animation:scanPulse 5s ease-in-out infinite}"
        "@keyframes scanPulse{0%,100%{opacity:.3}50%{opacity:.42}}"
        # Atmosphere breathes: three pre-rendered density states cross-fade on
        # a soft ease (not steps() - the one place tweening is wanted, since
        # that's what makes it read as breathing rather than flicker).
        ".atm{opacity:0;animation:atmCycle 14s ease-in-out infinite}"
        ".atmA{animation-delay:0s}.atmB{animation-delay:-4.67s}.atmC{animation-delay:-9.33s}"
        "@keyframes atmCycle{0%,88%,100%{opacity:0}11%,33%{opacity:1}}"
        ".bloom{animation:bloomPulse 7s ease-in-out infinite}"
        "@keyframes bloomPulse{0%,100%{opacity:.5}50%{opacity:.8}}"
        "@media (prefers-reduced-motion: reduce){*{animation:none!important}.atmB{opacity:1!important}}"
    )
    alt_text = "; ".join(a for a in alts if a)

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{alt_text}">
<defs>{"".join(parts)}</defs>
<style>{style_block}</style>
{field_body}
{"".join(bodies)}
</svg>
'''
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(svg)
    return path, H


def demo():
    stats = dict(repos=5, contributed=0, stars=0, commits=117, followers=0,
                 additions=4768, deletions=114, loc_skipped=False)
    p, h = render(stats, "assets/_demo_scene.svg")
    svg = open(p, encoding="utf-8").read()
    assert svg.count("<svg") == 1 and svg.rstrip().endswith("</svg>")
    assert "<script" not in svg, "scene must stay script-free (GitHub strips it anyway)"
    import xml.etree.ElementTree as ET
    ET.parse(p)  # malformed SVG renders as nothing at all
    assert 'aria-label="' in svg.split("\n", 1)[0], "missing composed alt text"
    assert "prefers-reduced-motion" in svg, "missing reduced-motion guard"
    assert svg.count('id="scScan"') == 1, "scanline pattern missing or duplicated"
    assert svg.count('class="galaxy"') == 1, "galaxy sprite missing"
    assert "feTurbulence" not in svg, "should be pattern-based, not filter-based"
    for cls in ("atmA", "atmB", "atmC"):
        assert f'class="atm {cls}"' in svg, f"missing atmosphere layer {cls}"
    assert 'class="bloom"' in svg, "missing bloom layer"
    assert 'id="vignette"' in svg, "missing vignette"
    # The three density states must actually differ, or the breathing
    # animation would be cross-fading between identical frames.
    import re as _re
    atm_bodies = _re.findall(r'class="atm atm[ABC]">(.*?)</g>', svg, _re.S)
    assert len(atm_bodies) == 3 and len(set(atm_bodies)) == 3, \
        "atmosphere density states must differ from each other"
    before = svg
    render(stats, p)
    assert open(p, encoding="utf-8").read() == before, "render is not deterministic"
    print(f"ok - {p} (940x{h}, {len(svg):,} bytes)")


def main():
    demo()
    if os.path.exists(STATS_PATH):
        with open(STATS_PATH, encoding="utf-8") as f:
            stats = json.load(f)
        render(stats, OUT)
        print(f"re-rendered {OUT} from {STATS_PATH}")
    else:
        print(f"no {STATS_PATH} yet - {OUT} left untouched")


if __name__ == "__main__":
    main()
