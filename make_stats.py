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

from make_card import MONO, THEME, _esc, _starfield

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


def render(stats, path=OUT):
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
    add(f'<text x="{PAD}" y="{PAD + 19}" font-family="{MONO}" font-size="18" '
        f'font-weight="700" fill="{t["emerald_light"]}" letter-spacing="0.5">'
        f'GitHub Stats</text>')
    add(f'<line x1="{PAD}" y1="{PAD + 32}" x2="{W - PAD}" y2="{PAD + 32}" '
        f'stroke="{t["border"]}" stroke-width="1"/>')

    # ---- overview list --------------------------------------------------
    ov_x, ov_y = PAD + 6, 98
    add(f'<text x="{ov_x}" y="{ov_y - 20}" font-family="{MONO}" font-size="12.5" '
        f'font-weight="700" fill="{t["emerald_pale"]}">Overview</text>')
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
    # A HUD-style gauge: a slowly rotating dashed outer ring, a dial of tick
    # marks that fill up to the score, and the progress arc itself.
    # Centred in the gap between the overview list (ends ~x200) and the
    # language block (starts x500), rather than pushed up against the latter.
    rx, ry, rr = 350, 150, 38
    RANK_FS = 30
    circ = 2 * math.pi * rr
    arc = circ * min(max(score, 0.06), 1.0)

    add(f'<circle class="dial" cx="{rx}" cy="{ry}" r="52" fill="none" '
        f'stroke="{t["border"]}" stroke-width="1" stroke-dasharray="2 7"/>')

    ticks, TICKN = [], 24
    for i in range(TICKN):
        ang = math.radians(i * (360 / TICKN) - 90)
        lit = (i / TICKN) < score
        r2 = 47 if i % 3 == 0 else 45
        ticks.append(
            f'<line x1="{rx + 42 * math.cos(ang):.1f}" y1="{ry + 42 * math.sin(ang):.1f}" '
            f'x2="{rx + r2 * math.cos(ang):.1f}" y2="{ry + r2 * math.sin(ang):.1f}" '
            f'stroke="{t["emerald_light"] if lit else t["border"]}" '
            f'stroke-width="{2 if lit else 1.4}" stroke-linecap="round"/>'
        )
    add(f'<g>{"".join(ticks)}</g>')

    add(f'<circle cx="{rx}" cy="{ry}" r="{rr}" fill="{t["panel"]}" '
        f'stroke="{t["border"]}" stroke-width="5"/>')
    # The -90 lives on a wrapper: a CSS transform on the circle itself would
    # override the presentation attribute and swing the arc's start to 3 o'clock.
    add(f'<g transform="rotate(-90 {rx} {ry})">'
        f'<circle class="ring" cx="{rx}" cy="{ry}" r="{rr}" fill="none" '
        f'stroke="{t["emerald_light"]}" stroke-width="5" stroke-linecap="round" '
        f'stroke-dasharray="{arc:.1f} {circ - arc:.1f}" filter="url(#ringGlow)"/></g>')
    # 0.355 * font-size puts the cap-height midpoint on the circle's centre;
    # the previous hand-picked offset sat the letter a couple of pixels high.
    add(f'<text x="{rx}" y="{ry + RANK_FS * 0.355:.1f}" text-anchor="middle" '
        f'font-family="{MONO}" font-size="{RANK_FS}" font-weight="700" '
        f'fill="{t["text"]}">{_esc(letter)}</text>')
    # Label moved outside the ring - inside it collided with the letter.
    add(f'<text x="{rx}" y="{ry + 68}" text-anchor="middle" font-family="{MONO}" '
        f'font-size="9.5" letter-spacing="1.5" fill="{t["dim"]}">RANK '
        f'<tspan fill="{t["emerald"]}">{score * 100:.0f}%</tspan></text>')

    # ---- languages ------------------------------------------------------
    lx, lw = 500, W - PAD - 500
    add(f'<text x="{lx}" y="78" font-family="{MONO}" font-size="12.5" '
        f'font-weight="700" fill="{t["emerald_pale"]}">Most Used Languages</text>')

    langs = stats.get("languages", [])[:6]
    total_pct = sum(l["pct"] for l in langs) or 1.0
    bx = lx
    bar = []
    for i, l in enumerate(langs):
        seg = lw * l["pct"] / total_pct
        r_ = 5 if i == 0 else 0
        bar.append(
            f'<rect x="{bx:.1f}" y="92" width="{max(seg, 1.2):.1f}" height="11" '
            f'fill="{l.get("color") or t["emerald"]}" rx="{r_}"/>'
        )
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
        add(f'<text x="{cx}" y="{sy + 36 + 30 * 0.355:.1f}" text-anchor="middle" '
            f'font-family="{MONO}" font-size="30" font-weight="700" '
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
    add(f'<text x="{PAD}" y="{gy0 - 14}" font-family="{MONO}" font-size="12.5" '
        f'font-weight="700" fill="{t["emerald_pale"]}">'
        f'Contribution Graph <tspan fill="{t["dim"]}">- last {len(recent)} days'
        f', peak {peak}</tspan></text>')

    if len(recent) >= 2:
        step = (gx1 - gx0) / (len(recent) - 1)
        pts = [(gx0 + i * step, gy1 - (c / top) * (gy1 - gy0))
               for i, (_, c) in enumerate(recent)]

        for f in (0.0, 0.5, 1.0):  # gridlines + y axis labels
            yy = gy1 - f * (gy1 - gy0)
            add(f'<line x1="{gx0}" y1="{yy:.1f}" x2="{gx1}" y2="{yy:.1f}" '
                f'stroke="{t["border"]}" stroke-width="1" stroke-dasharray="3 5"/>'
                f'<text x="{gx0 - 10}" y="{yy + 4:.1f}" text-anchor="end" '
                f'font-family="{MONO}" font-size="10" fill="{t["dim"]}">'
                f'{int(round(top * f))}</text>')

        line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        add(f'<polygon class="area" points="{gx0:.1f},{gy1} {line} {gx1:.1f},{gy1}" '
            f'fill="url(#areaGrad)"/>')
        add(f'<polyline class="spark" points="{line}" fill="none" '
            f'stroke="{t["emerald_light"]}" stroke-width="2" '
            f'stroke-linejoin="round" stroke-linecap="round"/>')

        # Peak marker - the one point worth calling out.
        pi = max(range(len(recent)), key=lambda i: recent[i][1])
        px, py = pts[pi]
        if peak > 0:
            add(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" '
                f'fill="{t["bg_top"]}" stroke="{t["emerald_pale"]}" stroke-width="2"/>'
                f'<text x="{min(px, gx1 - 46):.1f}" y="{py - 11:.1f}" '
                f'text-anchor="middle" font-family="{MONO}" font-size="10" '
                f'fill="{t["emerald_pale"]}">{peak} on {_fmt_day(recent[pi][0])}</text>')

        for i, (x, y) in enumerate(pts):  # x axis labels, thinned out
            if i % 4 == 0 or i == len(pts) - 1:
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
  <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="{t["emerald"]}" stop-opacity="0.42"/>
    <stop offset="100%" stop-color="{t["emerald"]}" stop-opacity="0.02"/>
  </linearGradient>
  <filter id="ringGlow" x="-60%" y="-60%" width="220%" height="220%">
    <feGaussianBlur stdDeviation="2.6" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
</defs>
<style>
  .fd {{ opacity:0; animation: fdIn .5s ease-out forwards; }}
  @keyframes fdIn {{ from {{ opacity:0; transform:translateY(6px); }}
                     to   {{ opacity:1; transform:translateY(0); }} }}
  .star {{ animation: twinkle 4s ease-in-out infinite; }}
  @keyframes twinkle {{ 0%,100% {{ opacity:.15; }} 50% {{ opacity:.7; }} }}
  /* Draw the sparkline on with a dash sweep. 4000 comfortably exceeds the
     path length, so the whole line is hidden before it wipes in. */
  .spark {{ stroke-dasharray:4000; stroke-dashoffset:4000;
            animation: draw 2.2s ease-out .5s forwards; }}
  @keyframes draw {{ to {{ stroke-dashoffset:0; }} }}
  .area {{ opacity:0; animation: fdIn .8s ease-out 1.6s forwards; }}
  .bar  {{ transform-origin:{lx}px 97px; animation: growBar 1s ease-out .4s backwards; }}
  @keyframes growBar {{ from {{ transform:scaleX(0); }} to {{ transform:scaleX(1); }} }}
  /* transform-box:fill-box keeps each ring spinning about its own centre, so
     one rule serves both the rank gauge and the streak ring. */
  .ring {{ transform-box:fill-box; transform-origin:center;
           animation: spin 1.1s ease-out .3s backwards; }}
  @keyframes spin {{ from {{ transform:rotate(-140deg); opacity:0; }}
                     to   {{ transform:rotate(0deg); opacity:1; }} }}
  .dial {{ transform-box:fill-box; transform-origin:center;
           animation: dialSpin 40s linear infinite; }}
  @keyframes dialSpin {{ to {{ transform:rotate(360deg); }} }}
  .uline {{ transform-box:fill-box; transform-origin:center;
            animation: wipe .7s ease-out .5s backwards; }}
  @keyframes wipe {{ from {{ transform:scaleX(0); }} to {{ transform:scaleX(1); }} }}
</style>
<rect width="{W}" height="{H}" rx="14" fill="url(#statbg)"/>
<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14" fill="none" stroke="{t["border"]}"/>
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
