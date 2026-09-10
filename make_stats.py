#!/usr/bin/env python3
"""
Renders assets/github-stats.svg - one panel replacing the four third-party
widgets the README used to embed (github-readme-stats, top-langs,
streak-stats and the activity graph).

Everything is drawn from data update_stats.py already fetches, so the panel has
no runtime dependency on anyone else's uptime - two of the original four
services had started returning HTTP 402.

Keeps all the original numbers: stars / commits / PRs / issues / contributed,
the rank badge, the language breakdown, the streak trio, and the contribution
graph. Adds a busiest-day callout and a peak marker on the graph.

    python make_stats.py
"""
import datetime
import math
import os
import random
import re

import pixel
from make_card import MONO, PALETTE, PIXFONT, THEME, _esc, _starfield, pixel_font_face

OUT = "assets/github-stats.svg"
W, PAD = 940, 24


def rank(commits, prs, issues, stars, followers):
    """A letter grade from a weighted score of the headline counts.

    This is our own heuristic, loosely modelled on how github-readme-stats
    grades a profile (each metric against a median, run through a saturating
    curve so no single number dominates). It is NOT an official GitHub rank and
    will not always agree with the old widget's letter.
    """
    def cdf(x, median):
        return 1 - 2 ** (-(x / median)) if median else 0.0

    score = (0.28 * cdf(commits, 250) + 0.21 * cdf(prs, 50)
             + 0.14 * cdf(issues, 25) + 0.21 * cdf(stars, 50)
             + 0.16 * cdf(followers, 10))
    for threshold, letter in ((.85, "S"), (.70, "A+"), (.55, "A"), (.45, "A-"),
                              (.35, "B+"), (.25, "B"), (.17, "B-"), (.10, "C+")):
        if score >= threshold:
            return letter, score
    return "C", score


def streaks(days):
    """(current, longest) streaks from ascending [(date, count), ...].

    A zero on the final day is skipped rather than breaking the current streak,
    matching how streak trackers treat a day that is still in progress.
    """
    best = (0, None, None)
    run, run_start = 0, None
    for date, count in days:
        if count > 0:
            run += 1
            if run == 1:
                run_start = date
            if run > best[0]:
                best = (run, run_start, date)
        else:
            run = 0

    i = len(days) - 1
    if i >= 0 and days[i][1] == 0:
        i -= 1
    cur, cur_start, cur_end = 0, None, None
    while i >= 0 and days[i][1] > 0:
        if cur_end is None:
            cur_end = days[i][0]
        cur_start = days[i][0]
        cur += 1
        i -= 1
    return (cur, cur_start, cur_end), best


def _fmt_day(iso):
    if not iso:
        return "-"
    d = datetime.date.fromisoformat(iso)
    return f"{d.strftime('%b')} {d.day}"


def _n(v):
    return f"{v:,}"


RANK_CYCLE_S = 10  # sealed -> cracking -> open (letter revealed) -> reseal


def _pixel_disc(cx, cy, r, accent, panel, seam=False, knockout=0.0):
    """A pixel-grid disc for the rank capsule's sealed/cracking states -
    same knockout-cell vocabulary as make_stack.py's tech-stack capsules,
    but circular instead of a pill."""
    cell = pixel.PX
    n = round(2 * r / cell)
    rng = random.Random(2000 + n)
    seam_w = 2 if seam else 0
    out = []
    for ry in range(-n, n + 1):
        for rx in range(-n, n + 1):
            if rx * rx + ry * ry > n * n:
                continue
            if seam and abs(rx) < seam_w:
                continue
            if knockout and rng.random() < knockout:
                continue
            tone = accent if ry < -n * 0.4 else panel
            out.append(
                f'<rect x="{cx + rx * cell - cell / 2:.0f}" y="{cy + ry * cell - cell / 2:.0f}" '
                f'width="{cell}" height="{cell}" fill="{tone}"/>'
            )
    return "".join(out)


def render(stats, path=OUT, draw_bg=True):
    t = THEME
    fade = []          # (element markup, stagger index)
    idx = [0]

    def add(markup):
        fade.append((markup, idx[0]))
        idx[0] += 1

    days = [(d["date"], d["count"]) for d in stats.get("calendar", [])]
    (cur_n, cur_a, cur_b), (long_n, long_a, long_b) = streaks(days)
    letter, score = rank(stats["commits"], stats.get("prs", 0),
                         stats.get("issues", 0), stats["stars"],
                         stats["followers"])

    # ---- header ---------------------------------------------------------
    add(f'<text x="{PAD}" y="{PAD + 16}" font-family="{PIXFONT}" font-size="13" '
        f'fill="{t["emerald_light"]}" letter-spacing="0.5">'
        f'&gt; GitHub Stats</text>')
    add(f'<line x1="{PAD}" y1="{PAD + 32}" x2="{W - PAD}" y2="{PAD + 32}" '
        f'stroke="{t["border"]}" stroke-width="1"/>')
    add(f'<line x1="{PAD}" y1="{PAD + 35}" x2="{W - PAD}" y2="{PAD + 35}" '
        f'stroke="{t["border"]}" stroke-width="1" opacity="0.4"/>')

    # ---- overview list --------------------------------------------------
    ov_x, ov_y = PAD + 6, 98
    add(f'<text x="{ov_x}" y="{ov_y - 20}" font-family="{PIXFONT}" font-size="9" '
        f'fill="{t["emerald_pale"]}">&gt; Overview</text>')
    rows = [
        ("Total Stars", _n(stats["stars"])),
        ("Total Commits", _n(stats["commits"])),
        ("Total PRs", _n(stats.get("prs", 0))),
        ("Total Issues", _n(stats.get("issues", 0))),
        ("Contributed (1y)", _n(stats.get("contributed", 0))),
        ("Followers", _n(stats["followers"])),
    ]
    for i, (k, v) in enumerate(rows):
        dots = "." * max(2, 18 - len(k))
        add(f'<text x="{ov_x}" y="{ov_y + i * 20}" font-family="{MONO}" '
            f'font-size="13" xml:space="preserve">'
            f'<tspan fill="{t["emerald"]}">{_esc(k)}</tspan>'
            f'<tspan fill="{t["border"]}"> {dots} </tspan>'
            f'<tspan fill="{t["text"]}">{_esc(v)}</tspan></text>')

    # ---- rank badge -----------------------------------------------------
    # Pixel HUD gauge: grid-snapped tick marks, a pixel_arc progress ring, and
    # a rank capsule at the centre that dissolves (sealed -> cracking -> open)
    # to reveal the letter - same three-state vocabulary as the tech-stack
    # chips, one slower-cycle instance.
    rx, ry, rr = 350, 150, 38
    RANK_FS = 30

    ticks, TICKN = [], 24
    for i in range(TICKN):
        ang = math.radians(i * (360 / TICKN) - 90)
        lit = (i / TICKN) < score
        r2 = 47 if i % 3 == 0 else 45
        tx1, ty1 = pixel.snap(rx + 42 * math.cos(ang)), pixel.snap(ry + 42 * math.sin(ang))
        tx2, ty2 = pixel.snap(rx + r2 * math.cos(ang)), pixel.snap(ry + r2 * math.sin(ang))
        ticks.append(
            f'<rect x="{tx2 - 2}" y="{ty2 - 2}" width="4" height="4" '
            f'fill="{t["emerald_light"] if lit else t["border"]}"/>'
        )
    add(f'<g>{"".join(ticks)}</g>')

    add(pixel.pixel_bar(rx - rr - 4, ry - rr - 4, 2 * (rr + 4), 2 * (rr + 4),
                         t["panel"])[0])
    add(f'<g filter="url(#ringGlow)">'
        f'{pixel.pixel_arc(rx, ry, rr, min(max(score, 0.06), 1.0), t["emerald_light"])}'
        f'</g>')

    disc_r = 30
    sealed = _pixel_disc(rx, ry, disc_r, t["emerald_light"], t["panel"])
    cracking = _pixel_disc(rx, ry, disc_r, t["emerald_light"], t["panel"], seam=True, knockout=0.08)
    letter_svg = (
        f'<text x="{rx}" y="{ry + RANK_FS * 0.355:.1f}" text-anchor="middle" '
        f'font-family="{PIXFONT}" font-size="{RANK_FS}" '
        f'fill="{t["text"]}">{_esc(letter)}</text>'
    )
    add(f'<g class="rankCap" style="animation-duration:{RANK_CYCLE_S}s">'
        f'<g class="rc rcSealed">{sealed}</g>'
        f'<g class="rc rcCracking">{cracking}</g>'
        f'<g class="rc rcOpen">{letter_svg}</g></g>')
    # Label moved outside the ring - inside it collided with the letter.
    add(f'<text x="{rx}" y="{ry + 68}" text-anchor="middle" font-family="{MONO}" '
        f'font-size="9.5" letter-spacing="1.5" fill="{t["dim"]}">RANK '
        f'<tspan fill="{t["emerald"]}">{score * 100:.0f}%</tspan></text>')

    # ---- languages ------------------------------------------------------
    lx, lw = 500, W - PAD - 500
    add(f'<text x="{lx}" y="78" font-family="{PIXFONT}" font-size="9" '
        f'fill="{t["emerald_pale"]}">&gt; Most Used Languages</text>')

    langs = stats.get("languages", [])[:6]
    total_pct = sum(l["pct"] for l in langs) or 1.0
    bx = lx
    bar = []
    for l in langs:
        seg = max(lw * l["pct"] / total_pct, pixel.PX)
        bar.append(pixel.pixel_bar(bx, 92, seg, 12, l.get("color") or t["emerald"])[0])
        bx += seg
    add(f'<g class="bar">{"".join(bar)}</g>')

    for i, l in enumerate(langs):
        col, rowi = i % 2, i // 2
        gx = lx + col * (lw / 2)
        gy = 128 + rowi * 21
        add(f'<circle cx="{gx + 4}" cy="{gy - 4}" r="4.5" '
            f'fill="{l.get("color") or t["emerald"]}"/>'
            f'<text x="{gx + 15}" y="{gy}" font-family="{MONO}" font-size="12" '
            f'fill="{t["text"]}">{_esc(l["name"])} '
            f'<tspan fill="{t["dim"]}">{l["pct"]:.2f}%</tspan></text>')

    # ---- streak trio ----------------------------------------------------
    sy = 250
    add(f'<line x1="{PAD}" y1="{sy - 18}" x2="{W - PAD}" y2="{sy - 18}" '
        f'stroke="{t["border"]}" stroke-width="1"/>')
    total_contrib = stats.get("total_contributions", 0)
    span = f'{_fmt_day(days[0][0])} - Present' if days else "-"
    trio = [
        (170, _n(total_contrib), "Total Contributions", span, False),
        (470, _n(cur_n), "Current Streak", f"{_fmt_day(cur_a)} - {_fmt_day(cur_b)}", True),
        (770, _n(long_n), "Longest Streak", f"{_fmt_day(long_a)} - {_fmt_day(long_b)}", False),
    ]
    for cx, big, label, sub, accent in trio:
        add(f'<text x="{cx}" y="{sy + 36 + 20 * 0.355:.1f}" text-anchor="middle" '
            f'font-family="{PIXFONT}" font-size="20" '
            f'fill="{t["emerald_light"] if accent else t["text"]}"'
            f'{" filter=\"url(#ringGlow)\"" if accent else ""}>{_esc(big)}</text>')
        if accent:
            # An underline instead of a ring - same emphasis, no circle.
            add(f'<rect class="uline" x="{cx - 26}" y="{sy + 58}" width="52" '
                f'height="3" rx="1.5" fill="{t["emerald_light"]}"/>')
        add(f'<text x="{cx}" y="{sy + 80}" text-anchor="middle" font-family="{MONO}" '
            f'font-size="12" fill="{t["emerald"] if accent else t["dim"]}">'
            f'{_esc(label)}</text>')
        add(f'<text x="{cx}" y="{sy + 97}" text-anchor="middle" font-family="{MONO}" '
            f'font-size="10.5" fill="{t["dim"]}">{_esc(sub)}</text>')
    for dx in (320, 620):
        add(f'<line x1="{dx}" y1="{sy + 6}" x2="{dx}" y2="{sy + 92}" '
            f'stroke="{t["border"]}" stroke-width="1"/>')

    # ---- contribution graph ---------------------------------------------
    gy0, gy1 = 404, 556
    gx0, gx1 = PAD + 46, W - PAD
    add(f'<line x1="{PAD}" y1="{gy0 - 34}" x2="{W - PAD}" y2="{gy0 - 34}" '
        f'stroke="{t["border"]}" stroke-width="1"/>')

    recent = days[-30:] if days else []
    peak = max((c for _, c in recent), default=0)
    top = max(peak, 1)
    add(f'<text x="{PAD}" y="{gy0 - 14}" font-family="{PIXFONT}" font-size="9" '
        f'fill="{t["emerald_pale"]}">'
        f'&gt; Contribution Graph <tspan fill="{t["dim"]}" font-family="{MONO}">- last {len(recent)} days'
        f', peak {peak}</tspan></text>')

    if len(recent) >= 2:
        step = (gx1 - gx0) / (len(recent) - 1)
        col_w = max(pixel.PX, pixel.snap(step * 0.6))
        cols_svg, xs = [], []
        for i, (_, c) in enumerate(recent):
            cx = gx0 + i * step
            xs.append(cx)
            ch = pixel.snap((c / top) * (gy1 - gy0)) if c else 0
            if ch <= 0:
                continue
            tone = t["emerald_light"] if c == peak and peak > 0 else t["emerald"]
            cols_svg.append(pixel.pixel_bar(cx - col_w / 2, gy1 - ch, col_w, ch, tone)[0])
        add(f'<g class="area">{"".join(cols_svg)}</g>')

        for f in (0.0, 0.5, 1.0):  # gridlines + y axis labels
            yy = gy1 - f * (gy1 - gy0)
            add(f'<line x1="{gx0}" y1="{yy:.1f}" x2="{gx1}" y2="{yy:.1f}" '
                f'stroke="{t["border"]}" stroke-width="1" stroke-dasharray="3 5"/>'
                f'<text x="{gx0 - 10}" y="{yy + 4:.1f}" text-anchor="end" '
                f'font-family="{MONO}" font-size="10" fill="{t["dim"]}">'
                f'{int(round(top * f))}</text>')

        # Peak marker - a 2x2 pixel block instead of a smooth circle.
        pi = max(range(len(recent)), key=lambda i: recent[i][1])
        if peak > 0:
            px = xs[pi]
            py = gy1 - pixel.snap((peak / top) * (gy1 - gy0))
            add(pixel.pixel_bar(px - pixel.PX, py - pixel.PX, 2 * pixel.PX, 2 * pixel.PX,
                                 t["emerald_pale"])[0])
            add(f'<text x="{min(px, gx1 - 46):.1f}" y="{py - 11:.1f}" '
                f'text-anchor="middle" font-family="{MONO}" font-size="10" '
                f'fill="{t["emerald_pale"]}">{peak} on {_fmt_day(recent[pi][0])}</text>')

        for i, x in enumerate(xs):  # x axis labels, thinned out
            if i % 4 == 0 or i == len(xs) - 1:
                add(f'<text x="{x:.1f}" y="{gy1 + 18}" text-anchor="middle" '
                    f'font-family="{MONO}" font-size="9.5" fill="{t["dim"]}">'
                    f'{int(recent[i][0][-2:])}</text>')

    H = gy1 + 46

    body = "".join(
        f'<g class="fd" style="animation-delay:{i * 26}ms">{m}</g>' for m, i in fade
    )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="GitHub statistics: {_n(stats["stars"])} stars, {_n(stats["commits"])} commits, rank {letter}, {_n(total_contrib)} contributions, {cur_n} day current streak">
<defs>
  <linearGradient id="statbg" x1="0" y1="0" x2="0.5" y2="1">
    <stop offset="0%" stop-color="{t["bg_top"]}"/>
    <stop offset="100%" stop-color="{t["bg_bottom"]}"/>
  </linearGradient>
  <filter id="ringGlow" x="-60%" y="-60%" width="220%" height="220%">
    <feGaussianBlur stdDeviation="2.6" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
</defs>
<style>
  {pixel_font_face()}
  .fd {{ opacity:0; animation: fdIn .5s ease-out forwards; }}
  @keyframes fdIn {{ from {{ opacity:0; transform:translateY(6px); }}
                     to   {{ opacity:1; transform:translateY(0); }} }}
  .star {{ animation: twinkle 4s ease-in-out infinite; }}
  @keyframes twinkle {{ 0%,100% {{ opacity:.15; }} 50% {{ opacity:.7; }} }}
  .area {{ opacity:0; animation: fdIn .8s ease-out 1.6s forwards; }}
  .uline {{ transform-box:fill-box; transform-origin:center;
            animation: wipe .7s ease-out .5s backwards; }}
  @keyframes wipe {{ from {{ transform:scaleX(0); }} to {{ transform:scaleX(1); }} }}
  /* Rank capsule: same sealed -> cracking -> open dissolve as the tech-stack
     chips, one slower-cycle instance revealing the rank letter. */
  .rc {{ opacity:0; animation-duration:{RANK_CYCLE_S}s;
         animation-iteration-count:infinite; animation-timing-function:steps(1,end); }}
  .rcSealed {{ animation-name:rcSealed; }}
  .rcCracking {{ animation-name:rcCracking; }}
  .rcOpen {{ animation-name:rcOpen; }}
  @keyframes rcSealed {{ 0%,58% {{ opacity:1; }} 58.01%,100% {{ opacity:0; }} }}
  @keyframes rcCracking {{ 0%,58% {{ opacity:0; }} 58.01%,66% {{ opacity:1; }}
                           66.01%,100% {{ opacity:0; }} }}
  @keyframes rcOpen {{ 0%,66% {{ opacity:0; }} 66.01%,92% {{ opacity:1; }}
                       92.01%,100% {{ opacity:0; }} }}
  @media (prefers-reduced-motion: reduce) {{
    *{{animation:none!important}} .rcOpen{{opacity:1!important}}
  }}
</style>
{f'<rect width="{W}" height="{H}" rx="14" fill="url(#statbg)"/><rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14" fill="none" stroke="{t["border"]}"/>' if draw_bg else ''}
{_starfield(W, H, count=34, seed=41)}
{body}
</svg>
'''
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(svg)
    return path, W, H


def demo():
    """Self-check with a synthetic profile."""
    base = datetime.date(2026, 7, 29)
    counts = [0] * 24 + [2, 12, 20, 30, 5, 3]
    cal = [{"date": str(base - datetime.timedelta(days=len(counts) - 1 - i)),
            "count": c} for i, c in enumerate(counts)]
    stats = dict(repos=5, contributed=0, stars=0, commits=131, followers=0,
                 additions=4778, deletions=124, loc_skipped=False,
                 prs=0, issues=0, total_contributions=123, calendar=cal,
                 languages=[{"name": "HTML", "pct": 86.51, "color": "#e34c26"},
                            {"name": "JavaScript", "pct": 8.99, "color": "#f1e05a"},
                            {"name": "Python", "pct": 4.0, "color": "#3572A5"},
                            {"name": "CSS", "pct": 0.5, "color": "#563d7c"}])

    (cur, ca, cb), (lng, la, lb) = streaks([(d["date"], d["count"]) for d in cal])
    assert cur == 6 and lng == 6, f"streaks wrong: current={cur} longest={lng}"
    # A trailing zero must not break the current streak, only a real gap does.
    z = [("2026-07-27", 3), ("2026-07-28", 4), ("2026-07-29", 0)]
    assert streaks(z)[0][0] == 2, "trailing zero should not reset the streak"
    g = [("2026-07-26", 3), ("2026-07-27", 0), ("2026-07-28", 4), ("2026-07-29", 1)]
    assert streaks(g)[0][0] == 2 and streaks(g)[1][0] == 2, "gap handling wrong"
    assert streaks([])[0][0] == 0, "empty calendar should not explode"

    assert rank(0, 0, 0, 0, 0)[0] == "C", "an empty profile should rank C"
    assert rank(9e4, 9e3, 9e3, 9e4, 9e3)[0] == "S", "a huge profile should rank S"

    p, w, h = render(stats, "assets/_demo_stats.svg")
    svg = open(p, encoding="utf-8").read()
    import xml.etree.ElementTree as ET
    ET.parse(p)  # malformed SVG renders as nothing at all
    for token in ("HTML", "Total Commits", "Current Streak", "Contribution Graph", "RANK"):
        assert token in svg, f"missing {token!r}"
    assert "<polyline" not in svg and "<polygon" not in svg, \
        "graph must be pixel columns, not vector paths"
    before = svg
    render(stats, p)
    assert open(p, encoding="utf-8").read() == before, "render is not deterministic"
    print(f"ok - {p} ({w}x{h}, {len(svg):,} bytes, rank {rank(131,0,0,0,0)[0]})")


def main():
    demo()
    import json
    from make_card import STATS_PATH
    if os.path.exists(STATS_PATH):
        with open(STATS_PATH, encoding="utf-8") as f:
            stats = json.load(f)
        if "calendar" in stats:
            render(stats, OUT)
            print(f"re-rendered {OUT} from {STATS_PATH}")
        else:
            print(f"{STATS_PATH} has no calendar yet - the Action fills it on "
                  f"its next run")


if __name__ == "__main__":
    main()
