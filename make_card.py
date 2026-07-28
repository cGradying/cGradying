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
import json
import math
import os
import random

# Last-fetched stats, written by update_stats.py. Kept beside the card so the
# design can be re-rendered locally without a GitHub token - otherwise the only
# copy of the numbers is the SVG itself, and tweaking the layout means either
# scraping them back out or clobbering them with stale ones.
STATS_PATH = "assets/stats.json"

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
    "red": "#EF4444",
    "red_light": "#F87171",
}

# INFO keys whose value gets the matrix-decode treatment.
GLITCH_KEYS = {"Host"}

# ASCII only, so every glyph is guaranteed the same advance width as the real
# text - a proportional fallback glyph would make the line jitter in width.
MATRIX_GLYPHS = "01ABCDEF#%&$@*+=/<>[]{}|?!~^"
FRAMES = 7  # scrambled frames shown before the text resolves


def _decode_frames(text, frames=FRAMES, seed=1):
    """Progressive 'matrix decode' states for `text`.

    Frame i has the first i/frames characters already resolved and the rest
    replaced with random glyphs, so playing the frames in order looks like the
    line resolving left to right. Spaces are never scrambled, which keeps the
    word shape readable while it decodes.

    Returns [(resolved_prefix, scrambled_suffix), ...]. Seeded so the render
    stays byte-identical across runs.
    """
    rng = random.Random(seed)
    out = []
    for f in range(frames):
        keep = int(len(text) * f / frames)
        tail = "".join(
            ch if ch == " " else rng.choice(MATRIX_GLYPHS) for ch in text[keep:]
        )
        out.append((text[:keep], tail))
    return out

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

    def row_text(cls, key, value_html, yy):
        dots = "." * max(2, label_cols - len(key))
        return (
            f'<text x="{info_x}" y="{yy:.1f}" font-family="{MONO}" '
            f'font-size="{info_fs}"{cls} xml:space="preserve">'
            f'<tspan fill="{t["emerald"]}">{_esc(key)}</tspan>'
            f'<tspan fill="{t["border"]}"> {dots} </tspan>'
            f'{value_html}</text>'
        )

    def glitch_stack(key, make_value, group, yy, fade_idx):
        """Stack FRAMES scrambled copies plus the resolved one.

        Every copy is a full row laid out by the same font, so they line up
        exactly without needing to know the font's advance width. CSS shows one
        at a time; the wrapping <g> keeps the normal staggered entrance.
        """
        parts = [f'<g class="fade f{fade_idx}">']
        for i in range(FRAMES):
            parts.append(row_text(f' class="gv gv{i} {group}"', key, make_value(i), yy))
        parts.append(row_text(f' class="gv gvR {group}"', key, make_value(None), yy))
        parts.append("</g>")
        return "".join(parts)

    y = info_top
    for row in INFO:
        if row is None:
            y += info_lh * 0.5
            continue
        key, val = row
        if key in GLITCH_KEYS:
            frames = _decode_frames(val, seed=len(val))

            def host_value(i, _val=val, _frames=frames):
                if i is None:
                    return f'<tspan fill="{t["text"]}">{_esc(_val)}</tspan>'
                keep, tail = _frames[i]
                # Alternate the scramble colour so it flickers between matrix
                # green and red on the way to resolving white.
                col = t["emerald_pale"] if i % 2 == 0 else t["red"]
                return (f'<tspan fill="{t["text"]}">{_esc(keep)}</tspan>'
                        f'<tspan fill="{col}">{_esc(tail)}</tspan>')

            body.append(glitch_stack(key, host_value, "gr-host", y, delay))
        else:
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

    def plain(v):
        return f'<tspan fill="{t["text"]}">{_esc(v)}</tspan>'

    add_txt = f'{n(stats["additions"])}++'
    del_txt = f'{n(stats["deletions"])}--'
    add_frames = _decode_frames(add_txt, seed=11)
    del_frames = _decode_frames(del_txt, seed=29)
    total_txt = n(stats["additions"] + stats["deletions"])

    def loc_value(i):
        """Frame i of the LOC row; i is None for the resolved state."""
        if i is None:
            add_html = f'<tspan fill="{t["text"]}">{_esc(add_txt)}</tspan>'
            del_html = f'<tspan fill="{t["text"]}">{_esc(del_txt)}</tspan>'
        else:
            ak, at = add_frames[i]
            dk, dt = del_frames[i]
            add_html = (f'<tspan fill="{t["text"]}">{_esc(ak)}</tspan>'
                        f'<tspan fill="{t["emerald_pale"]}">{_esc(at)}</tspan>')
            del_html = (f'<tspan fill="{t["text"]}">{_esc(dk)}</tspan>'
                        f'<tspan fill="{t["red"]}">{_esc(dt)}</tspan>')
        return (f'{plain(total_txt + " (")}{add_html}{plain(", ")}'
                f'{del_html}{plain(")")}')

    stat_rows = [
        ("Repos", plain(f'{n(stats["repos"])}  (contributed to {n(stats["contributed"])})')),
        ("Stars", plain(n(stats["stars"]))),
        ("Commits", plain(n(stats["commits"]))),
        ("Followers", plain(n(stats["followers"]))),
        ("Lines of Code", plain("skipped") if stats.get("loc_skipped") else None),
    ]
    for key, val_markup in stat_rows:
        if val_markup is None:  # the animated LOC row
            body.append(glitch_stack(key, loc_value, "gr-loc", y, delay))
        else:
            dots = "." * max(2, label_cols - len(key))
            body.append(
                f'<text x="{info_x}" y="{y:.1f}" font-family="{MONO}" '
                f'font-size="{info_fs}" class="fade f{delay}" xml:space="preserve">'
                f'<tspan fill="{t["emerald"]}">{_esc(key)}</tspan>'
                f'<tspan fill="{t["border"]}"> {dots} </tspan>'
                f'{val_markup}</text>'
            )
        styles.append(f".f{delay}{{animation-delay:{delay * 55}ms}}")
        delay += 1
        y += info_lh

    # Frame-switching CSS. The decode burst occupies W0%..W1% of the loop; the
    # rest of the cycle shows the resolved text. steps(1,end) makes each frame
    # snap into place instead of cross-fading, which is what sells the glitch.
    W0, W1, CYCLE = 84.0, 95.0, "7s"
    span = (W1 - W0) / FRAMES
    kf = [
        f".gv{{animation-duration:{CYCLE};animation-iteration-count:infinite;"
        f"animation-timing-function:steps(1,end)}}",
        f"@keyframes gvR{{0%,{W0:.2f}%{{opacity:1}}"
        f"{W0:.2f}%,{W1:.2f}%{{opacity:0}}{W1:.2f}%,100%{{opacity:1}}}}",
        ".gvR{animation-name:gvR}",
        # Offset so the two rows decode at different moments.
        ".gr-host{animation-delay:0s}.gr-loc{animation-delay:3.5s}",
    ]
    for i in range(FRAMES):
        a, b = W0 + i * span, W0 + (i + 1) * span
        kf.append(
            f"@keyframes gv{i}{{0%,{a:.2f}%{{opacity:0}}"
            f"{a:.2f}%,{b:.2f}%{{opacity:1}}{b:.2f}%,100%{{opacity:0}}}}"
            f".gv{i}{{animation-name:gv{i}}}"
        )
    glitch_css = "".join(kf)

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

  {glitch_css}
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
    # Deliberately NOT assets/card.svg - these are dummy numbers, and writing
    # them to the real card would overwrite the live stats the Action fetched.
    p = render(stats, "assets/_demo_card.svg")
    svg = open(p, encoding="utf-8").read()
    assert "117" in svg and "4,768" in svg, "stats missing from SVG"
    assert svg.count("<svg") == 1 and svg.rstrip().endswith("</svg>")
    # Regenerating with identical stats must not change the file.
    before = svg
    render(stats, p)
    assert open(p, encoding="utf-8").read() == before, "render is not deterministic"
    print(f"ok - {p} ({len(svg):,} bytes, moon {len(m)} rows)")
    print("\n".join(m))


def main():
    """Self-check, then re-render the real card from the last saved stats."""
    demo()
    if os.path.exists(STATS_PATH):
        with open(STATS_PATH, encoding="utf-8") as f:
            stats = json.load(f)
        render(stats, "assets/card.svg")
        print(f"re-rendered assets/card.svg from {STATS_PATH}")
    else:
        print(f"no {STATS_PATH} yet - assets/card.svg left untouched "
              f"(the Action writes it on its next run)")


if __name__ == "__main__":
    main()
