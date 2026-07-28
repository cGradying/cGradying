#!/usr/bin/env python3
"""
Renders assets/stack.svg - the compact, animated tech-stack panel in README.md.

shields.io badges are flat images and cannot animate, so the whole grid is
built here instead: chips are laid out and wrapped in Python, logo paths come
from Simple Icons, and the motion is CSS embedded in the SVG.

Two animations run: chips fade up in a staggered wave on load, then a shine
sweeps across them on a loop, clipped to the chip shapes so it reads as light
moving over the badges rather than a bar sliding over the page.

Icon paths are cached in assets/icons.json, so this only needs network access
the first time a new slug is added. Edit STACK below to change the contents.

    python make_stack.py
"""
import json
import os
import re

from make_card import MONO, THEME

ICON_CACHE = "assets/icons.json"
OUT = "assets/stack.svg"
CDN = "https://cdn.jsdelivr.net/npm/simple-icons@13/icons/{slug}.svg"

# (section title, accent colour key, [(label, simple-icons slug), ...])
STACK = [
    ("Game Development", "emerald_pale", [
        ("Unity", "unity"), ("Unreal", "unrealengine"), ("Godot", "godotengine"),
        (".NET", "dotnet"), ("Blender", "blender"), ("Aseprite", "aseprite"),
        ("Steamworks", "steam"),
    ]),
    ("AI / Machine Learning", "emerald_light", [
        ("PyTorch", "pytorch"), ("TensorFlow", "tensorflow"), ("Keras", "keras"),
        ("scikit-learn", "scikitlearn"), ("Hugging Face", "huggingface"),
        ("OpenCV", "opencv"), ("NumPy", "numpy"), ("Pandas", "pandas"),
        ("Jupyter", "jupyter"),
    ]),
    ("Software Engineering", "emerald", [
        ("Python", "python"), ("C++", "cplusplus"), ("Java", "openjdk"),
        ("TypeScript", "typescript"), ("Git", "git"), ("Docker", "docker"),
        ("Linux", "linux"), ("AWS", "amazonwebservices"),
    ]),
    ("Web - Frontend & Backend", "emerald_pale", [
        ("React", "react"), ("Next.js", "nextdotjs"), ("Tailwind", "tailwindcss"),
        ("Node.js", "nodedotjs"), ("FastAPI", "fastapi"),
        ("PostgreSQL", "postgresql"), ("MongoDB", "mongodb"), ("Vercel", "vercel"),
    ]),
]

W = 940
PAD = 22
CHIP_H = 28
CHIP_GAP = 7
ROW_GAP = 7
ICON = 13
FS = 11.0
CHAR_W = FS * 0.60  # monospace advance width, so chip widths are exact
SEC_TITLE_FS = 12.0


def load_icons(slugs):
    """Return {slug: path-data}, fetching only what the cache is missing."""
    cache = {}
    if os.path.exists(ICON_CACHE):
        with open(ICON_CACHE, encoding="utf-8") as f:
            cache = json.load(f)

    # `not cache.get(s)` rather than `s not in cache`: a failed fetch caches an
    # empty string, and treating that as present would make the failure stick
    # forever instead of retrying on the next run.
    missing = [s for s in slugs if not cache.get(s)]
    if missing:
        import requests  # only needed when the cache is cold
        for slug in missing:
            url = CDN.format(slug=slug)
            try:
                r = requests.get(url, timeout=20)
                r.raise_for_status()
                m = re.search(r'\sd="([^"]+)"', r.text)
                if not m:
                    raise ValueError("no path data in response")
                cache[slug] = m.group(1)
                print(f"fetched {slug}")
            except Exception as e:
                # A missing logo degrades to a text-only chip rather than
                # failing the whole render.
                print(f"WARNING: could not fetch '{slug}': {e}")
                cache[slug] = ""
        os.makedirs(os.path.dirname(ICON_CACHE) or ".", exist_ok=True)
        with open(ICON_CACHE, "w", encoding="utf-8", newline="\n") as f:
            json.dump(cache, f, indent=0, sort_keys=True)
    return cache


def chip_width(label, has_icon):
    inner = len(label) * CHAR_W
    if has_icon:
        inner += ICON + 6
    return round(inner + 20, 1)


def render(path=OUT):
    t = THEME
    icons = load_icons([s for _, _, items in STACK for _, s in items])

    chips, seps, titles, clips = [], [], [], []
    y = PAD
    idx = 0

    for title, accent_key, items in STACK:
        accent = t[accent_key]
        titles.append(
            f'<g class="fade" style="animation-delay:{idx * 28}ms">'
            f'<rect x="{PAD}" y="{y + 1}" width="3" height="11" rx="1.5" fill="{accent}"/>'
            f'<text x="{PAD + 10}" y="{y + 10.5}" font-family="{MONO}" '
            f'font-size="{SEC_TITLE_FS}" font-weight="700" fill="{accent}" '
            f'letter-spacing="0.4">{title}</text></g>'
        )
        idx += 1
        y += 22

        x = PAD
        for label, slug in items:
            d = icons.get(slug, "")
            w = chip_width(label, bool(d))
            if x + w > W - PAD:  # wrap
                x = PAD
                y += CHIP_H + ROW_GAP

            delay = idx * 28
            parts = [
                f'<g class="chip" style="animation-delay:{delay}ms">',
                f'<rect x="{x}" y="{y}" width="{w}" height="{CHIP_H}" rx="7" '
                f'fill="{t["panel"]}" stroke="{t["border"]}"/>',
            ]
            tx = x + 10
            if d:
                # Simple Icons use a 24x24 viewBox; scale it down in place.
                s = ICON / 24
                gx, gy = x + 10, y + (CHIP_H - ICON) / 2
                parts.append(
                    f'<g transform="translate({gx:.1f} {gy:.1f}) scale({s:.4f})">'
                    f'<path d="{d}" fill="{accent}"/></g>'
                )
                tx += ICON + 6
            parts.append(
                f'<text x="{tx:.1f}" y="{y + CHIP_H / 2 + 3.9:.1f}" font-family="{MONO}" '
                f'font-size="{FS}" fill="{t["text"]}">{_esc(label)}</text>'
            )
            parts.append("</g>")
            chips.append("".join(parts))
            # Same rect again, as the shine's clip - the sweep only lights chips.
            clips.append(
                f'<rect x="{x}" y="{y}" width="{w}" height="{CHIP_H}" rx="7"/>'
            )
            idx += 1
            x += w + CHIP_GAP

        y += CHIP_H + 16
        seps.append(y - 9)

    seps.pop()  # no divider after the last section
    H = round(y + PAD - 16)

    divider_svg = "".join(
        f'<line x1="{PAD}" y1="{sy}" x2="{W - PAD}" y2="{sy}" stroke="{t["border"]}" '
        f'stroke-width="1" class="fade"/>' for sy in seps
    )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Tech stack: game development, AI and machine learning, software engineering, web frontend and backend">
<defs>
  <linearGradient id="sbg" x1="0" y1="0" x2="0.5" y2="1">
    <stop offset="0%" stop-color="{t["bg_top"]}"/>
    <stop offset="100%" stop-color="{t["bg_bottom"]}"/>
  </linearGradient>
  <linearGradient id="shine" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%"   stop-color="{t["emerald_pale"]}" stop-opacity="0"/>
    <stop offset="50%"  stop-color="{t["emerald_pale"]}" stop-opacity="0.55"/>
    <stop offset="100%" stop-color="{t["emerald_pale"]}" stop-opacity="0"/>
  </linearGradient>
  <clipPath id="chipShapes">{"".join(clips)}</clipPath>
</defs>
<style>
  .fade {{ opacity:0; animation: sfade .45s ease-out forwards; }}
  @keyframes sfade {{ from {{ opacity:0; }} to {{ opacity:1; }} }}
  .chip {{ opacity:0; animation: chipIn .5s cubic-bezier(.2,.8,.3,1) forwards; }}
  @keyframes chipIn {{ from {{ opacity:0; transform:translateY(8px); }}
                       to   {{ opacity:1; transform:translateY(0); }} }}
  /* Sweep starts after the last chip has landed, then loops. */
  .shine {{ animation: sweep 4.5s ease-in-out {len(clips) * 28 + 500}ms infinite; }}
  @keyframes sweep {{ 0% {{ transform:translateX(-320px); }}
                      55%,100% {{ transform:translateX({W + 320}px); }} }}
</style>
<rect width="{W}" height="{H}" rx="14" fill="url(#sbg)"/>
<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14" fill="none" stroke="{t["border"]}"/>
{divider_svg}
{"".join(titles)}
{"".join(chips)}
<g clip-path="url(#chipShapes)">
  <rect class="shine" x="-320" y="0" width="260" height="{H}" fill="url(#shine)" transform="skewX(-18)"/>
</g>
</svg>
'''
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    # See the note in make_card.render: LF everywhere, or Windows and CI fight.
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(svg)
    return path, W, H, len(clips)


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def demo():
    """Self-check: every chip is laid out inside the canvas and the file is
    well-formed and deterministic."""
    p, w, h, n = render()
    svg = open(p, encoding="utf-8").read()
    assert svg.count("<svg") == 1 and svg.rstrip().endswith("</svg>")
    assert n == sum(len(i) for _, _, i in STACK), "chip count mismatch"
    # No chip may spill past the right edge or below the canvas.
    for x, y, cw, ch in re.findall(
        r'<rect x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="(28)"', svg
    ):
        assert float(x) + float(cw) <= w - PAD + 0.5, f"chip overflows right: x={x}"
        assert float(y) + float(ch) <= h, f"chip overflows bottom: y={y}"
    before = svg
    render(p)
    assert open(p, encoding="utf-8").read() == before, "render is not deterministic"
    print(f"ok - {p} ({w}x{h}, {n} chips, {len(svg):,} bytes)")


if __name__ == "__main__":
    demo()
