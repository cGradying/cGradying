#!/usr/bin/env python3
"""
Renders assets/card.svg - the animated "about me" panel shown at the top of
README.md.

Everything is generated locally so it can be styled freely: the moon is real
ASCII art computed from sphere lighting (not an image), and the colours and
fade-in animations are plain CSS embedded in the SVG. GitHub serves the file
through its image proxy, which keeps CSS animations working but strips any
JavaScript - so nothing here relies on scripting.

Edit INFO below to change the text block. Edit THEME to restyle.
"""
import html
import math
import os

# --- theme: "astra moon" deep space + emerald green -------------------------
THEME = {
    "bg_top": "#0B1120",
    "bg_bottom": "#0F172A",
    "panel": "#111A2E",
    "border": "#1E293B",
    "emerald": "#10B981",
    "emerald_light": "#34D399",
    "emerald_pale": "#6EE7B7",
    "text": "#C9D1D9",
    "dim": "#7D8DA1",
}

INFO = [
    ("OS", "Windows"),
    ("Host", "Polytechnic University of the Philippines"),
    ("Role", "Student"),
    ("IDE", "VS Code"),
    None,
    ("Languages.Programming", "Python, C++, C#, Java, TypeScript"),
    ("Languages.Real", "English, Filipino"),
    None,
    ("Currently.WorkingOn", "Projects to improve my daily life"),
    ("Currently.Learning", "Cloud infrastructure & architecture"),
    ("LookingToCollaborate", "AI/ML engineers, game devs, full-stack"),
    ("AskMeAbout", "Building AI-integrated products"),
    None,
    ("Email", "cgradying@gmail.com"),
    ("LinkedIn", "in/janvinsalvador"),
]

MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'DejaVu Sans Mono', monospace"

# Dark to bright. The moon is drawn by picking a character per pixel from this
# ramp based on how much light that point on the sphere receives.
RAMP = " .'`:,-~+=*coO08#%@"


def moon_ascii(rows=26, phase=0.55):
    """ASCII moon lit from the upper-left.

    Each cell is mapped onto a unit sphere; cells outside it stay blank, which
    is what makes the art transparent rather than a filled rectangle. `phase`
    slides the light source sideways: 1.0 is nearly full, lower values carve
    out a crescent.
    """
    cols = rows * 2  # monospace cells are about half as wide as they are tall
    # Light direction: upper-left, tilted toward the viewer.
    lx, ly, lz = -0.60 * (2 * phase - 1) - 0.25, -0.55, 0.75
    norm = math.sqrt(lx * lx + ly * ly + lz * lz)
    lx, ly, lz = lx / norm, ly / norm, lz / norm

    # Fixed craters as (x, y, radius, depth) in sphere coordinates.
    craters = [
        (-0.30, -0.22, 0.20, 0.35), (0.18, -0.42, 0.14, 0.30),
        (0.34, 0.18, 0.24, 0.32), (-0.14, 0.40, 0.17, 0.28),
        (-0.52, 0.14, 0.12, 0.25), (0.02, 0.02, 0.10, 0.22),
    ]

    lines = []
    for r in range(rows):
        # +0.5 samples the centre of the cell, so the disc stays symmetric.
        ny = (r + 0.5) / rows * 2 - 1
        row = []
        for c in range(cols):
            nx = (c + 0.5) / cols * 2 - 1
            d2 = nx * nx + ny * ny
            if d2 > 1.0:
                row.append(" ")
                continue
            nz = math.sqrt(1.0 - d2)
            light = nx * lx + ny * ly + nz * lz
            light = max(0.0, light) ** 0.85

            for cx, cy, cr, depth in craters:
                dist = math.hypot(nx - cx, ny - cy)
                if dist < cr:
                    # Fade the crater out toward its rim so it does not look
                    # like a hard-edged hole.
                    light *= 1.0 - depth * (1.0 - dist / cr)

            # Darken the very edge so the disc reads as a sphere, not a circle.
            light *= 0.35 + 0.65 * nz ** 0.5

            idx = int(light * (len(RAMP) - 1) + 0.5)
            row.append(RAMP[min(idx, len(RAMP) - 1)])
        lines.append("".join(row).rstrip())
    # Drop blank rows top and bottom so the art vertically centres cleanly.
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def _esc(s):
    return html.escape(str(s), quote=False)


def render(stats, path="assets/card.svg"):
    """Write the card. `stats` keys: repos, contributed, stars, commits,
    followers, additions, deletions, loc_skipped."""
    t = THEME
    W, H = 940, 560
    moon = moon_ascii(rows=26)

    moon_fs, moon_lh = 11.0, 12.4
    moon_h = len(moon) * moon_lh
    moon_x, moon_y = 190, (H - moon_h) / 2 + 30

    info_fs, info_lh = 13.0, 20.0
    info_x, info_top = 372, 96

    delay = 0
    styles, body = [], []

    # --- moon -----------------------------------------------------------
    body.append(
        f'<text x="{moon_x}" y="{moon_y}" text-anchor="middle" '
        f'font-family="{MONO}" font-size="{moon_fs}" fill="url(#moonGrad)" '
        f'filter="url(#glow)" class="moon" xml:space="preserve">'
    )
    for i, line in enumerate(moon):
        body.append(
            f'<tspan x="{moon_x}" dy="{0 if i == 0 else moon_lh}">{_esc(line)}</tspan>'
        )
    body.append("</text>")

    # --- header ---------------------------------------------------------
    body.append(
        f'<text x="{info_x}" y="60" font-family="{MONO}" font-size="17" '
        f'font-weight="700" fill="{t["emerald_light"]}" class="fade f{delay}">'
        f'cGradying<tspan fill="{t["dim"]}">@github</tspan></text>'
    )
    styles.append(f".f{delay}{{animation-delay:{delay * 55}ms}}")
    delay += 1
    body.append(
        f'<line x1="{info_x}" y1="72" x2="{W - 44}" y2="72" '
        f'stroke="{t["border"]}" stroke-width="1" class="fade f{delay}"/>'
    )
    styles.append(f".f{delay}{{animation-delay:{delay * 55}ms}}")
    delay += 1

    # --- info lines -----------------------------------------------------
    # Leader dots are drawn as a separate dim tspan so the key and value keep
    # their own colours while still lining up in the monospace grid.
    label_cols = 24
    y = info_top
    for row in INFO:
        if row is None:
            y += info_lh * 0.5
            continue
        key, val = row
        dots = "." * max(2, label_cols - len(key))
        body.append(
            f'<text x="{info_x}" y="{y:.1f}" font-family="{MONO}" '
            f'font-size="{info_fs}" class="fade f{delay}" xml:space="preserve">'
            f'<tspan fill="{t["emerald"]}">{_esc(key)}</tspan>'
            f'<tspan fill="{t["border"]}"> {dots} </tspan>'
            f'<tspan fill="{t["text"]}">{_esc(val)}</tspan></text>'
        )
        styles.append(f".f{delay}{{animation-delay:{delay * 55}ms}}")
        delay += 1
        y += info_lh

    # --- stats ----------------------------------------------------------
    y += info_lh * 0.4
    body.append(
        f'<text x="{info_x}" y="{y:.1f}" font-family="{MONO}" font-size="{info_fs}" '
        f'font-weight="700" fill="{t["emerald_pale"]}" class="fade f{delay}">'
        f'&#9679; GitHub Stats</text>'
    )
    styles.append(f".f{delay}{{animation-delay:{delay * 55}ms}}")
    delay += 1
    y += info_lh

    def n(v):
        return f"{v:,}"

    if stats.get("loc_skipped"):
        loc = "skipped"
    else:
        loc = (f'{n(stats["additions"] + stats["deletions"])} '
               f'({n(stats["additions"])}++, {n(stats["deletions"])}--)')

    stat_rows = [
        ("Repos", f'{n(stats["repos"])}  (contributed to {n(stats["contributed"])})'),
        ("Stars", n(stats["stars"])),
        ("Commits", n(stats["commits"])),
        ("Followers", n(stats["followers"])),
        ("Lines of Code", loc),
    ]
    for key, val in stat_rows:
        dots = "." * max(2, label_cols - len(key))
        body.append(
            f'<text x="{info_x}" y="{y:.1f}" font-family="{MONO}" '
            f'font-size="{info_fs}" class="fade f{delay}" xml:space="preserve">'
            f'<tspan fill="{t["emerald"]}">{_esc(key)}</tspan>'
            f'<tspan fill="{t["border"]}"> {dots} </tspan>'
            f'<tspan fill="{t["text"]}">{_esc(val)}</tspan></text>'
        )
        styles.append(f".f{delay}{{animation-delay:{delay * 55}ms}}")
        delay += 1
        y += info_lh

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="cGradying GitHub profile card">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="0.6" y2="1">
    <stop offset="0%" stop-color="{t["bg_top"]}"/>
    <stop offset="100%" stop-color="{t["bg_bottom"]}"/>
  </linearGradient>
  <linearGradient id="moonGrad" x1="0" y1="0" x2="0.7" y2="1">
    <stop offset="0%" stop-color="#EAFFF6"/>
    <stop offset="45%" stop-color="{t["emerald_pale"]}"/>
    <stop offset="100%" stop-color="{t["emerald"]}"/>
  </linearGradient>
  <radialGradient id="halo" cx="0.5" cy="0.5" r="0.5">
    <stop offset="0%" stop-color="{t["emerald"]}" stop-opacity="0.28"/>
    <stop offset="100%" stop-color="{t["emerald"]}" stop-opacity="0"/>
  </radialGradient>
  <filter id="glow" x="-40%" y="-40%" width="180%" height="180%">
    <feGaussianBlur stdDeviation="2.2" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
</defs>
<style>
  .fade {{ opacity:0; animation: fade .5s ease-out forwards; }}
  @keyframes fade {{ from {{ opacity:0; transform:translateX(-6px); }}
                     to   {{ opacity:1; transform:translateX(0); }} }}
  .moon {{ opacity:0; animation: moonIn 1.1s ease-out .1s forwards, breathe 6s ease-in-out 1.2s infinite; }}
  @keyframes moonIn {{ from {{ opacity:0; }} to {{ opacity:1; }} }}
  @keyframes breathe {{ 0%,100% {{ opacity:1; }} 50% {{ opacity:.82; }} }}
  .halo {{ animation: pulse 6s ease-in-out infinite; transform-origin:190px {H // 2}px; }}
  @keyframes pulse {{ 0%,100% {{ opacity:.75; transform:scale(1); }}
                      50% {{ opacity:1; transform:scale(1.06); }} }}
  .star {{ animation: twinkle 4s ease-in-out infinite; }}
  @keyframes twinkle {{ 0%,100% {{ opacity:.15; }} 50% {{ opacity:.7; }} }}
  {" ".join(styles)}
</style>
<rect width="{W}" height="{H}" rx="14" fill="url(#bg)"/>
<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14" fill="none" stroke="{t["border"]}"/>
{_starfield(W, H)}
<ellipse cx="190" cy="{H // 2}" rx="185" ry="185" fill="url(#halo)" class="halo"/>
{"".join(body)}
</svg>
'''
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    # newline="\n" keeps output identical on Windows and on the Ubuntu runner.
    # Without it Python would emit CRLF locally and LF in CI, so every workflow
    # run would rewrite all 40 lines and collide with any local regeneration.
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(svg)
    return path


def _starfield(W, H, count=54, seed=7):
    """Deterministic background stars.

    Seeded by hand rather than with `random` so regenerating the card produces
    a byte-identical file when the stats have not changed - otherwise every
    workflow run would commit a pointless diff.
    """
    out, s = [], seed
    for i in range(count):
        s = (s * 1103515245 + 12345) & 0x7FFFFFFF
        x = s % W
        s = (s * 1103515245 + 12345) & 0x7FFFFFFF
        y = s % H
        s = (s * 1103515245 + 12345) & 0x7FFFFFFF
        r = 0.6 + (s % 100) / 100.0
        out.append(
            f'<circle cx="{x}" cy="{y}" r="{r:.2f}" fill="#9FE8CB" class="star" '
            f'style="animation-delay:{(i % 9) * 450}ms"/>'
        )
    return "".join(out)


def demo():
    """Self-check: the moon must be a non-empty, transparent-edged disc and the
    SVG must contain the injected stats."""
    m = moon_ascii(rows=26)
    assert m, "moon produced no rows"
    assert all(len(line) <= 52 for line in m), "moon wider than expected"
    mid = m[len(m) // 2]
    assert mid.strip(), "moon has an empty middle row"
    # Edges of the bounding box must stay blank -> the art is a disc, not a box.
    assert not m[0].startswith("@"), "top row should not be fully lit"
    assert any(ch != " " for ch in "".join(m)), "moon is entirely blank"

    stats = dict(repos=5, contributed=0, stars=0, commits=117, followers=0,
                 additions=4768, deletions=114, loc_skipped=False)
    p = render(stats, "assets/card.svg")
    svg = open(p, encoding="utf-8").read()
    assert "117" in svg and "4,768" in svg, "stats missing from SVG"
    assert svg.count("<svg") == 1 and svg.rstrip().endswith("</svg>")
    # Regenerating with identical stats must not change the file.
    before = svg
    render(stats, p)
    assert open(p, encoding="utf-8").read() == before, "render is not deterministic"
    print(f"ok - {p} ({len(svg):,} bytes, moon {len(m)} rows)")
    print("\n".join(m))


if __name__ == "__main__":
    demo()
