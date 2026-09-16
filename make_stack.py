#!/usr/bin/env python3
"""
Renders assets/tech-stack.svg - the animated tech-stack panel in README.md.

Three side-by-side cards (Languages / Frameworks / Tools & Infra). Each card
cycles through PAGE_N pre-rendered pages of chips, like a trading card flipping
between its move sets, and a holo sweep crosses the cards in sequence.

GitHub strips <script> from embedded SVGs but keeps CSS, so the pages are not
swapped in code: all PAGE_N are stacked at the same coordinates and switched by
an `opacity` keyframe on a shared clock with steps(1, end) so they snap rather
than cross-fade. Same trick as MULTI_N in make_card.py.

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

PAGE_N = 3  # every column must have exactly this many pages - they share one clock

# (column title, accent colour key, [(page name, [(label, simple-icons slug), ...]), ...])
# Page 0 is what a reader sees first, so the headline tech lives there.
COLUMNS = [
    ("Languages", "emerald_light", [
        ("shipping", [
            ("Swift", "swift"), ("Python", "python"), ("TypeScript", "typescript"),
            ("JavaScript", "javascript"),
        ]),
        ("systems", [
            # simple-icons@13 has no "csharp" slug - .NET is the closest mark.
            ("C#", "dotnet"), ("C++", "cplusplus"), ("Java", "openjdk"),
            ("Kotlin", "kotlin"), ("Go", "go"), ("Rust", "rust"),
        ]),
        ("markup / query / shell", [
            ("HTML", "html5"), ("CSS", "css3"), ("SQL", "mysql"),
            ("Bash", "gnubash"), ("Lua", "lua"),
        ]),
    ]),
    ("Frameworks", "emerald", [
        ("native", [
            ("SwiftUI", "swift"), ("AppKit", "apple"), ("WebKit", "safari"),
        ]),
        ("web", [
            ("Next.js", "nextdotjs"), ("React", "react"),
            ("Tailwind", "tailwindcss"), ("FastAPI", "fastapi"),
        ]),
        ("ai / ml", [
            ("PyTorch", "pytorch"), ("Gymnasium", "openaigym"),
            ("NumPy", "numpy"), ("OpenCV", "opencv"),
        ]),
    ]),
    ("Tools & Infra", "emerald_pale", [
        ("daily", [
            ("Git", "git"), ("Docker", "docker"), ("Linux", "linux"),
            ("Xcode", "xcode"),
        ]),
        ("hosting", [
            ("Postgres", "postgresql"), ("Supabase", "supabase"),
            ("Vercel", "vercel"),
        ]),
        ("models", [
            ("Ollama", "ollama"), ("Claude", "claude"),
            ("llama.cpp", "meta"), ("Hugging Face", "huggingface"),
        ]),
    ]),
]

W = 940
PAD = 22
GUT = 14
TITLE = "Tech Stack"
HEADER_H = 48          # room for the panel title + rule above the cards
CARD_PAD = 12
CARD_TOP = 46          # card padding-top -> first chip row (clears title + page name)
CHIP_H = 28
CHIP_GAP = 7
ROW_GAP = 7
ICON = 13
FS = 11.0
CHAR_W = FS * 0.60     # monospace advance width, so chip widths are exact
COL_W = round((W - 2 * PAD - 2 * GUT) / 3, 1)
INNER_W = COL_W - 2 * CARD_PAD

PAGE_S = 3.2           # seconds a page is held
STAGGER = 0.45         # seconds each column lags the one to its left

# Mosaic-tile wipe: a grid of small squares over each card brightens in a
# diagonal band that sweeps corner to corner once per page-turn, masking the
# chip swap underneath (reference: a glowing square-grid gradient). Every
# tile shares one keyframe shape and is only offset in time by its distance
# along the diagonal, same trick as the meteor sequence in make_card.py uses
# IMPACT/M_HIT to drive one wave from one scalar.
TILE = 16
WAVE_SPREAD = 1.1      # seconds the band takes to cross a card, corner to corner
WAVE_HOLD = 0.5        # seconds one tile's brighten-then-dim takes
TILE_BASE = 0.12       # resting opacity - tiles read as a faint grid, not blank
TILE_LEVELS = (0.35, 0.65, 1.0)  # brighten steps, then mirrored on the way down


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


def _tile_keyframes():
    """Percentage stops for one tile's slot of its own PAGE_S clock: a quick
    brighten-then-dim near phase 0, flat at TILE_BASE the rest of the way.
    Every tile shares this shape; only animation-delay differs, so the
    diagonal offset in mosaic_tiles() is what turns identical tiles into a
    travelling band rather than a synchronized blink.
    """
    hold_pct = WAVE_HOLD / PAGE_S * 100
    step = hold_pct / (2 * len(TILE_LEVELS))
    stops = [(0, TILE_BASE)]
    stops += [((i + 1) * step, v) for i, v in enumerate(TILE_LEVELS)]
    stops += [((len(TILE_LEVELS) + i) * step, v)
              for i, v in enumerate(reversed(TILE_LEVELS[:-1]))]
    stops += [(hold_pct, TILE_BASE), (100, TILE_BASE)]
    return " ".join(f"{p:.4g}%{{opacity:{v:g};}}" for p, v in stops)


def mosaic_tiles(cx, card_y, card_h, accent, col_delay):
    """One card's tile grid: <rect>s covering the card, each delayed by its
    distance along the diagonal so together they read as one glowing band
    sweeping corner to corner, once per page-turn (PAGE_S), on loop. Built
    once per card, not once per page - the wave shape doesn't depend on
    which page is underneath it. `col_delay` staggers card against card.

    CSS animation-delay does not cascade from parent to child, so each
    tile carries its own full offset rather than nesting under a delayed
    wrapper group.
    """
    cols = -(-round(COL_W) // TILE)  # ceil
    rows = -(-card_h // TILE)
    span = cols + rows - 2 or 1
    out = []
    for j in range(rows):
        for i in range(cols):
            d = (i + j) / span  # 0 at top-left corner, 1 at bottom-right
            delay = col_delay - d * WAVE_SPREAD
            out.append(
                f'<rect class="tile" style="animation-delay:{delay:.3f}s" '
                f'x="{cx + i * TILE:.1f}" y="{card_y + j * TILE:.1f}" '
                f'width="{TILE - 1}" height="{TILE - 1}" fill="{accent}"/>'
            )
    return "".join(out)


def chip_width(label, has_icon):
    inner = len(label) * CHAR_W
    if has_icon:
        inner += ICON + 6
    return round(inner + 20, 1)


def wrap_page(items, icons):
    """Greedy-wrap one page's chips into rows that fit INNER_W."""
    rows, cur, used = [], [], 0.0
    for label, slug in items:
        w = chip_width(label, bool(icons.get(slug)))
        if cur and used + CHIP_GAP + w > INNER_W:
            rows.append(cur)
            cur, used = [], 0.0
        used += w + (CHIP_GAP if cur else 0)
        cur.append((label, slug, w))
    if cur:
        rows.append(cur)
    return rows


def _chip(x, y, label, d, accent, t):
    parts = [
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{chip_width(label, bool(d)):.1f}" '
        f'height="{CHIP_H}" rx="7" fill="{t["panel"]}" stroke="{t["border"]}"/>'
    ]
    tx = x + 10
    if d:
        # Simple Icons use a 24x24 viewBox; scale it down in place.
        s = ICON / 24
        parts.append(
            f'<g transform="translate({x + 10:.1f} {y + (CHIP_H - ICON) / 2:.1f}) '
            f'scale({s:.4f})"><path d="{d}" fill="{accent}"/></g>'
        )
        tx += ICON + 6
    parts.append(
        f'<text x="{tx:.1f}" y="{y + CHIP_H / 2 + 3.9:.1f}" font-family="{MONO}" '
        f'font-size="{FS}" fill="{t["text"]}">{_esc(label)}</text>'
    )
    return "".join(parts)


def render(path=OUT):
    t = THEME
    icons = load_icons([s for _, _, pages in COLUMNS for _, items in pages for _, s in items])

    # Every card is as tall as the tallest page anywhere, so swapping pages
    # never resizes the panel and the three cards stay aligned.
    wrapped = [[wrap_page(items, icons) for _, items in pages] for _, _, pages in COLUMNS]
    max_rows = max(len(rows) for col in wrapped for rows in col)
    card_h = round(CARD_TOP + max_rows * (CHIP_H + ROW_GAP) - ROW_GAP + CARD_PAD)
    card_y = PAD + HEADER_H
    H = card_y + card_h + PAD

    cards, mosaics, clips, n_chips = [], [], [], 0

    for c, (title, accent_key, pages) in enumerate(COLUMNS):
        accent = t[accent_key]
        cx = PAD + c * (COL_W + GUT)
        clips.append(
            f'<clipPath id="cc{c}"><rect x="{cx:.1f}" y="{card_y}" '
            f'width="{COL_W:.1f}" height="{card_h}" rx="10"/></clipPath>'
        )

        body = [
            f'<rect x="{cx:.1f}" y="{card_y}" width="{COL_W:.1f}" height="{card_h}" '
            f'rx="10" fill="{t["bg_top"]}" stroke="{t["border"]}"/>',
            f'<rect x="{cx + CARD_PAD:.1f}" y="{card_y + CARD_PAD + 1}" width="3" '
            f'height="11" rx="1.5" fill="{accent}"/>',
            f'<text x="{cx + CARD_PAD + 10:.1f}" y="{card_y + CARD_PAD + 10.5}" '
            f'font-family="{PIXFONT}" font-size="9" fill="{accent}" '
            f'letter-spacing="0.4">&gt; {_esc(title)}</text>',
        ]

        for k, ((page_name, _), rows) in enumerate(zip(pages, wrapped[c])):
            # Negative delay so all pages share one keyframe and start
            # mid-clock; the column stagger rides on the same offset.
            delay = -(k * PAGE_S + c * STAGGER)
            page = [f'<g class="pg" style="animation-delay:{delay:.2f}s">']

            page.append(
                f'<text x="{cx + CARD_PAD:.1f}" y="{card_y + CARD_PAD + 25}" '
                f'font-family="{MONO}" font-size="9" fill="{t["dim"]}">'
                f'{_esc(page_name)}</text>'
            )
            # Page dots, pokemon-card style: the active one is this page's.
            for j in range(PAGE_N):
                fill = accent if j == k else t["border"]
                page.append(
                    f'<circle cx="{cx + COL_W - CARD_PAD - (PAGE_N - 1 - j) * 9:.1f}" '
                    f'cy="{card_y + CARD_PAD + 22}" r="2.5" fill="{fill}"/>'
                )

            y = card_y + CARD_TOP
            for row in rows:
                x = cx + CARD_PAD
                for label, slug, w in row:
                    d = icons.get(slug, "")
                    page.append(_chip(x, y, label, d, accent, t))
                    x += w + CHIP_GAP
                    n_chips += 1
                y += CHIP_H + ROW_GAP

            page.append("</g>")
            body.append("".join(page))

        cards.append(f'<g class="fade" style="animation-delay:{c * 90}ms">{"".join(body)}</g>')

        # Mosaic-tile wipe, clipped to this card, offset by the column
        # stagger so the three cards' waves sweep in sequence rather than
        # in lockstep.
        mosaics.append(
            f'<g clip-path="url(#cc{c})">'
            f'{mosaic_tiles(cx, card_y, card_h, accent, -c * STAGGER)}</g>'
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
        f"{title} - " + ", ".join(
            lbl for _, items in pages for lbl, _ in items
        ) for title, _, pages in COLUMNS
    )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{_esc(alt)}">
<defs>
  <linearGradient id="sbg" x1="0" y1="0" x2="0.5" y2="1">
    <stop offset="0%" stop-color="{t["bg_top"]}"/>
    <stop offset="100%" stop-color="{t["bg_bottom"]}"/>
  </linearGradient>
  {"".join(clips)}
  {pixel_texture("stackTex", t["emerald"])}
</defs>
<style>
  {pixel_font_face()}
  .fade {{ opacity:0; animation: sfade .45s ease-out forwards; }}
  @keyframes sfade {{ from {{ opacity:0; }} to {{ opacity:1; }} }}
  /* Matches the card's starfield - _starfield() emits class="star". */
  .star {{ animation: twinkle 4s ease-in-out infinite; }}
  @keyframes twinkle {{ 0%,100% {{ opacity:.15; }} 50% {{ opacity:.7; }} }}
  .tex {{ animation: texPulse 5s ease-in-out infinite; }}
  @keyframes texPulse {{ 0%,100% {{ opacity:.6; }} 50% {{ opacity:1; }} }}
  /* Page swap: all {PAGE_N} pages sit at the same coordinates, one visible per
     slot of the shared clock, hard cut with steps(1,end) - the mosaic wave
     below is what visually covers the instant of the swap. */
  .pg {{ opacity:0; animation: pgTurn {PAGE_N * PAGE_S:g}s steps(1,end) infinite; }}
  @keyframes pgTurn {{ 0% {{ opacity:1; }}
                       {100 / PAGE_N:.4f}%,100% {{ opacity:0; }} }}
  /* Mosaic-tile wipe: every tile runs the identical brighten/dim shape, only
     animation-delay differs (set per tile in mosaic_tiles()), so the shared
     keyframes plus a diagonal spread of delays is what turns a static grid
     into one glowing band sweeping corner to corner every page-turn. */
  .tile {{ opacity:{TILE_BASE:g}; animation: tileWave {PAGE_S:g}s steps(1,end) infinite; }}
  @keyframes tileWave {{ {_tile_keyframes()} }}
</style>
<rect width="{W}" height="{H}" rx="14" fill="url(#sbg)"/>
<rect width="{W}" height="{H}" rx="14" fill="url(#stackTex)" class="tex"/>
<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14" fill="none" stroke="{t["border"]}"/>
{_starfield(W, H, count=40, seed=23)}
{header_svg}
{"".join(cards)}
{"".join(mosaics)}
</svg>
'''
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    # See the note in make_card.render: LF everywhere, or Windows and CI fight.
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(svg)
    return path, W, H, n_chips


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def demo():
    """Self-check: pages are uniform, every chip fits inside its own card, and
    the file is well-formed and deterministic."""
    for title, _, pages in COLUMNS:
        assert len(pages) == PAGE_N, f"{title!r} has {len(pages)} pages, expected {PAGE_N}"

    p, w, h, n = render()
    svg = open(p, encoding="utf-8").read()
    assert svg.count("<svg") == 1 and svg.rstrip().endswith("</svg>")
    # Must be well-formed XML or browsers render nothing at all - an unescaped
    # "&" in a label silently produced a blank image once already, and
    # "Tools & Infra" is exactly that shape.
    import xml.etree.ElementTree as ET
    ET.parse(p)
    assert n == sum(len(i) for _, _, pg in COLUMNS for _, i in pg), "chip count mismatch"

    # No chip may be wider than a card, spill out of its column, or fall
    # outside the canvas.
    bounds = [(PAD + c * (COL_W + GUT), PAD + c * (COL_W + GUT) + COL_W)
              for c in range(len(COLUMNS))]
    for x, y, cw in re.findall(
        r'<rect x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="28" rx="7"', svg
    ):
        x, y, cw = float(x), float(y), float(cw)
        assert cw <= INNER_W + 0.5, f"chip too wide for a card: {cw}"
        assert any(lo + CARD_PAD - 0.5 <= x and x + cw <= hi - CARD_PAD + 0.5
                   for lo, hi in bounds), f"chip outside its column: x={x}"
        assert y + CHIP_H <= h, f"chip overflows bottom: y={y}"

    # Tiles overhanging a card's right/bottom edge are expected (grid width is
    # rounded up to a whole number of tiles) - the per-card clip-path is what
    # actually contains them, so just confirm every mosaic group is clipped
    # and something was drawn.
    assert svg.count('<g clip-path="url(#cc') == len(COLUMNS), "mosaic group missing its clip"
    assert svg.count('class="tile"') > 0, "no mosaic tiles rendered"

    before = svg
    render(p)
    assert open(p, encoding="utf-8").read() == before, "render is not deterministic"
    print(f"ok - {p} ({w}x{h}, {n} chips over {PAGE_N} pages, {len(svg):,} bytes)")


if __name__ == "__main__":
    demo()
