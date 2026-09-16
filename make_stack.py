#!/usr/bin/env python3
"""
Renders assets/tech-stack.svg - the tech-stack panel in README.md.

One seamless panel (same shape as make_card.py/make_stats.py - starfield,
pixel texture, single rounded border), not a row of individually-boxed mini
cards. Three columns of content separated by a thin rule, each tech drawn as
a small pixel "item slot" (icon centered, label underneath) rather than a
variable-width text pill - reads as a retro game inventory grid, on-theme
with the PressStart2P headings used everywhere else.

Earlier versions of this file rotated pages of chips behind a mosaic-tile
wipe timed to the page swap. Three rounds of sync tuning later, the fix was
to remove the thing that needed syncing: every chip is shown at once now, and
the only motion left is a tiny reused twinkle flourish next to each header -
decorative, not load-bearing, nothing to keep in phase with anything else.

Icon paths are cached in assets/icons.json, so this only needs network access
the first time a new slug is added. Edit COLUMNS below to change the contents.

    python make_stack.py
"""
import json
import os
import re

from make_card import MONO, PIXFONT, THEME, _starfield, pixel_font_face, pixel_texture

ICON_CACHE = "assets/icons.json"
OUT = "assets/tech-stack.svg"
CDN = "https://cdn.jsdelivr.net/npm/simple-icons@13/icons/{slug}.svg"

# (column title, accent colour key, [(label, simple-icons slug), ...])
COLUMNS = [
    ("Languages", "emerald_light", [
        ("Swift", "swift"), ("Python", "python"), ("TypeScript", "typescript"),
        ("JavaScript", "javascript"),
        # simple-icons@13 has no "csharp" slug - .NET is the closest mark.
        ("C#", "dotnet"), ("C++", "cplusplus"), ("Java", "openjdk"),
        ("Kotlin", "kotlin"), ("Go", "go"), ("Rust", "rust"),
        ("HTML", "html5"), ("CSS", "css3"), ("SQL", "mysql"),
        ("Bash", "gnubash"), ("Lua", "lua"),
    ]),
    ("Frameworks", "emerald", [
        ("SwiftUI", "swift"), ("AppKit", "apple"), ("WebKit", "safari"),
        ("Next.js", "nextdotjs"), ("React", "react"),
        ("Tailwind", "tailwindcss"), ("FastAPI", "fastapi"),
        ("PyTorch", "pytorch"), ("Gymnasium", "openaigym"),
        ("NumPy", "numpy"), ("OpenCV", "opencv"),
    ]),
    ("Tools & Infra", "emerald_pale", [
        ("Git", "git"), ("Docker", "docker"), ("Linux", "linux"),
        ("Xcode", "xcode"),
        ("Postgres", "postgresql"), ("Supabase", "supabase"),
        ("Vercel", "vercel"),
        ("Ollama", "ollama"), ("Claude", "claude"),
        ("llama.cpp", "meta"), ("Hugging Face", "huggingface"),
    ]),
]

W = 940
PAD = 22
GUT = 14
TITLE = "Tech Stack"
HEADER_H = 48          # room for the panel title + rule above the columns
COL_HEADER_H = 26      # column title row -> first slot row
COL_W = round((W - 2 * PAD - 2 * GUT) / 3, 1)

SLOT = 48               # item-slot cell, square
SLOT_GAP = 8
ICON = 18
FS_LABEL = 7.0           # small - a caption under the icon, not body text


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
                # A missing logo degrades to a text-only slot rather than
                # failing the whole render.
                print(f"WARNING: could not fetch '{slug}': {e}")
                cache[slug] = ""
        os.makedirs(os.path.dirname(ICON_CACHE) or ".", exist_ok=True)
        with open(ICON_CACHE, "w", encoding="utf-8", newline="\n") as f:
            json.dump(cache, f, indent=0, sort_keys=True)
    return cache


def slot_grid(items):
    """Fixed-width rows: how many SLOT-sized cells fit COL_W, items wrapped
    that many per row. Simpler than measuring text (today's chips had to
    size themselves to their label) since every slot is the same size."""
    cols_per_row = max(1, int((COL_W + SLOT_GAP) // (SLOT + SLOT_GAP)))
    rows = [items[i:i + cols_per_row] for i in range(0, len(items), cols_per_row)]
    return rows, cols_per_row


def _slot(x, y, label, d, accent, t):
    parts = [
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{SLOT}" height="{SLOT}" rx="4" '
        f'fill="{t["panel"]}" stroke="{t["border"]}"/>'
    ]
    cx = x + SLOT / 2
    if d:
        # Simple Icons use a 24x24 viewBox; scale it down in place.
        s = ICON / 24
        parts.append(
            f'<g transform="translate({x + (SLOT - ICON) / 2:.1f} {y + 7:.1f}) '
            f'scale({s:.4f})"><path d="{d}" fill="{accent}"/></g>'
        )
        label_y = y + SLOT - 8
    else:
        label_y = y + SLOT / 2 + 3  # no icon - centre the label in the slot
    parts.append(
        f'<text x="{cx:.1f}" y="{label_y:.1f}" font-family="{MONO}" '
        f'font-size="{FS_LABEL}" fill="{t["text"]}" text-anchor="middle">'
        f'{_esc(label)}</text>'
    )
    return "".join(parts)


def render(path=OUT):
    t = THEME
    icons = load_icons([s for _, _, items in COLUMNS for _, s in items])

    grids = [slot_grid(items) for _, _, items in COLUMNS]
    max_rows = max(len(rows) for rows, _ in grids)
    content_h = max_rows * (SLOT + SLOT_GAP) - SLOT_GAP
    col_y = PAD + HEADER_H + COL_HEADER_H
    H = col_y + content_h + PAD

    body, n_slots = [], 0

    for c, ((title, accent_key, items), (rows, _)) in enumerate(zip(COLUMNS, grids)):
        accent = t[accent_key]
        cx = PAD + c * (COL_W + GUT)
        hy = PAD + HEADER_H

        col = [
            f'<rect x="{cx:.1f}" y="{hy + 1}" width="3" height="11" rx="1.5" fill="{accent}"/>',
            f'<text x="{cx + 10:.1f}" y="{hy + 10.5}" font-family="{PIXFONT}" '
            f'font-size="9" fill="{accent}" letter-spacing="0.4">&gt; {_esc(title)}</text>',
        ]
        # Tiny flourish, right-aligned in the column: reuses the exact
        # .star/twinkle rule _starfield() already defines - no new keyframes,
        # nothing timed against anything else.
        fx = cx + COL_W - 3 * 7
        col += [
            f'<rect class="star" style="animation-delay:{i * 220}ms" '
            f'x="{fx + i * 7:.1f}" y="{hy + 2:.1f}" width="3" height="3" fill="{accent}"/>'
            for i in range(3)
        ]

        y = col_y
        for row in rows:
            x = cx
            for label, slug in row:
                col.append(_slot(x, y, label, icons.get(slug, ""), accent, t))
                x += SLOT + SLOT_GAP
                n_slots += 1
            y += SLOT + SLOT_GAP

        body.append(f'<g class="fade" style="animation-delay:{c * 90}ms">{"".join(col)}</g>')

    dividers = "".join(
        f'<line x1="{PAD + c * (COL_W + GUT) + COL_W + GUT / 2:.1f}" y1="{col_y - 6}" '
        f'x2="{PAD + c * (COL_W + GUT) + COL_W + GUT / 2:.1f}" y2="{col_y + content_h}" '
        f'stroke="{t["border"]}" stroke-width="1" class="fade"/>'
        for c in range(len(COLUMNS) - 1)
    )

    # Panel title, so the README needs no markdown heading above the image.
    header_svg = (
        f'<text x="{PAD}" y="{PAD + 16}" font-family="{PIXFONT}" font-size="13" '
        f'fill="{t["emerald_light"]}" class="fade" '
        f'letter-spacing="0.5">&gt; {_esc(TITLE)}</text>'
        f'<line x1="{PAD}" y1="{PAD + 32}" x2="{W - PAD}" y2="{PAD + 32}" '
        f'stroke="{t["border"]}" stroke-width="1" class="fade"/>'
    )

    alt = "Tech stack: " + "; ".join(
        f"{title} - " + ", ".join(lbl for lbl, _ in items)
        for title, _, items in COLUMNS
    )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{_esc(alt)}">
<defs>
  <linearGradient id="sbg" x1="0" y1="0" x2="0.5" y2="1">
    <stop offset="0%" stop-color="{t["bg_top"]}"/>
    <stop offset="100%" stop-color="{t["bg_bottom"]}"/>
  </linearGradient>
  {pixel_texture("stackTex", t["emerald"])}
</defs>
<style>
  {pixel_font_face()}
  .fade {{ opacity:0; animation: sfade .45s ease-out forwards; }}
  @keyframes sfade {{ from {{ opacity:0; }} to {{ opacity:1; }} }}
  /* Matches the card's starfield - _starfield() emits class="star", reused
     here for the header flourish too. */
  .star {{ animation: twinkle 4s ease-in-out infinite; }}
  @keyframes twinkle {{ 0%,100% {{ opacity:.15; }} 50% {{ opacity:.7; }} }}
  .tex {{ animation: texPulse 5s ease-in-out infinite; }}
  @keyframes texPulse {{ 0%,100% {{ opacity:.6; }} 50% {{ opacity:1; }} }}
</style>
<rect width="{W}" height="{H}" rx="14" fill="url(#sbg)"/>
<rect width="{W}" height="{H}" rx="14" fill="url(#stackTex)" class="tex"/>
<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14" fill="none" stroke="{t["border"]}"/>
{_starfield(W, H, count=40, seed=23)}
{header_svg}
{dividers}
{"".join(body)}
</svg>
'''
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    # See the note in make_card.render: LF everywhere, or Windows and CI fight.
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(svg)
    return path, W, H, n_slots


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def demo():
    """Self-check: every slot fits inside its own column, the file is
    well-formed, and the render is deterministic."""
    p, w, h, n = render()
    svg = open(p, encoding="utf-8").read()
    assert svg.count("<svg") == 1 and svg.rstrip().endswith("</svg>")
    # Must be well-formed XML or browsers render nothing at all - an unescaped
    # "&" in a label silently produced a blank image once already, and
    # "Tools & Infra" is exactly that shape.
    import xml.etree.ElementTree as ET
    ET.parse(p)
    assert n == sum(len(items) for _, _, items in COLUMNS), "slot count mismatch"

    bounds = [(PAD + c * (COL_W + GUT), PAD + c * (COL_W + GUT) + COL_W)
              for c in range(len(COLUMNS))]
    for x, y in re.findall(rf'<rect x="([\d.]+)" y="([\d.]+)" width="{SLOT}" height="{SLOT}" rx="4"', svg):
        x, y = float(x), float(y)
        assert any(lo - 0.5 <= x and x + SLOT <= hi + 0.5 for lo, hi in bounds), \
            f"slot outside its column: x={x}"
        assert y + SLOT <= h, f"slot overflows bottom: y={y}"

    before = svg
    render(p)
    assert open(p, encoding="utf-8").read() == before, "render is not deterministic"
    print(f"ok - {p} ({w}x{h}, {n} slots, {len(svg):,} bytes)")


if __name__ == "__main__":
    demo()
