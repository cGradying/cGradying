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


def _dither_field(H):
    """Flat void background + three deterministic <pattern> textures behind
    all three panels: halftone dots, 4x4 Bayer ordered dither, CRT scanlines.
    No SVG filters, so no feTurbulence/Safari risk - and unlike the filter
    version this replaces, these are actually visible at full opacity. A
    seeded pixel-art galaxy sits dim behind the tech-stack panel."""
    t = THEME
    defs = (
        pixel.halftone_pattern("scHalf", t["dim"], tile=6, dot_r=1.3)
        + pixel.bayer_pattern("scBayer", t["bg_top"], t["panel"])
        + pixel.scanline_pattern("scScan", "#000000", gap=4, opacity=0.35)
    )
    galaxy = pixel.pixel_galaxy(W * 0.72, 660, 360, 220, seed=17, palette=PALETTE)
    body = (
        f'<rect width="{W}" height="{H}" fill="{t["bg_top"]}"/>'
        f'<rect width="{W}" height="{H}" fill="url(#scBayer)" opacity="0.5"/>'
        f'<g class="galaxy" opacity="0.55">{galaxy}</g>'
        f'<rect width="{W}" height="{H}" fill="url(#scHalf)" opacity="0.5"/>'
        f'<rect class="scanPulse" width="{W}" height="{H}" fill="url(#scScan)"/>'
    )
    return defs, body


def render(stats, path=OUT):
    frags = [
        make_card.render(stats, "assets/_scene_card.svg", draw_bg=False),
        make_stack.render("assets/_scene_stack.svg", draw_bg=False)[0],
        make_stats.render(stats, "assets/_scene_stats.svg", draw_bg=False)[0],
    ]

    parts, styles, bodies, alts, y = [], [], [], [], 0.0
    for i, fp in enumerate(frags):
        svg_text = open(fp, encoding="utf-8").read()
        defs, style, body, w, h, alt = _split(svg_text)
        assert w == W, f"{fp}: width {w} != scene width {W}"
        parts.append(defs)
        styles.append(style)
        bodies.append(f'<g transform="translate(0,{y:.1f})">{body}</g>')
        alts.append(alt)
        y += h
        os.remove(fp)  # scratch fragment, not a committed asset

    H = round(y)
    field_defs, field_body = _dither_field(H)
    parts.insert(0, field_defs)

    style_block = "".join(styles) + (
        ".galaxy{animation:galaxyDrift 10s ease-in-out infinite}"
        "@keyframes galaxyDrift{0%,100%{opacity:.5}50%{opacity:.65}}"
        ".scanPulse{animation:scanPulse 5s ease-in-out infinite}"
        "@keyframes scanPulse{0%,100%{opacity:.3}50%{opacity:.42}}"
        "@media (prefers-reduced-motion: reduce){*{animation:none!important}}"
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
    for pid in ("scHalf", "scBayer", "scScan"):
        assert svg.count(f'id="{pid}"') == 1, f"pattern {pid} missing or duplicated"
    assert svg.count('class="galaxy"') == 1, "galaxy sprite missing"
    assert "feTurbulence" not in svg, "should be pattern-based, not filter-based"
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
