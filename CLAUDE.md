# CLAUDE.md

Guidance for Claude Code (claude.ai/code) working in this repo.

## What this is

`cGradying/cGradying` — the GitHub profile README repo. The README embeds
three **locally generated SVGs**, not third-party widget services. It used to
embed `github-readme-stats`, `top-langs`, `streak-stats`, `activity-graph`,
`github-profile-trophy` and `github-contributor-stats`; two of those started
returning HTTP 402 and one 503. **Do not add a widget URL back** — anything
new gets drawn by a script here.

## Commands

No build, no tests, no linter. Python 3.12, one third-party dep (`requests`).

```
python make_card.py    # renders assets/_demo_card.svg  + self-check
python make_stack.py   # renders assets/tech-stack.svg
python make_stats.py   # renders assets/_demo_stats.svg + self-check
python update_stats.py # live: needs GH_USERNAME + GITHUB_TOKEN
```

Each module's `demo()` is the whole test suite: it asserts XML validity,
byte-identical re-render (determinism), geometry bounds and streak/uptime edge
cases. Run the module directly after touching it.

## Architecture

```
update_stats.py  --GraphQL/REST-->  assets/stats.json
                                          |
                        make_card.render() -> assets/card.svg
                        make_stats.render() -> assets/github-stats.svg
```

`assets/stats.json` is the single source of truth, and it is **committed**.
That is what lets you re-render either SVG locally after a design change with
no token and no scraping. Always render from it; never hand-edit an SVG.

`make_stack.py` is *not* in the workflow — `tech-stack.svg` only changes when
you run it. It fetches Simple Icons logo paths from jsDelivr and caches them in
`assets/icons.json`; the cache-miss check is `not cache.get(s)`, deliberately,
so a failed fetch that cached `""` retries instead of sticking forever.

## The one rule that shapes every animation

**GitHub strips JavaScript from embedded SVGs but keeps CSS.** So every
effect — matrix decode, meteor impact, shockwave, shake, diffraction, rotating
content — is pre-rendered states stacked at the same coordinates and switched
by CSS `opacity` keyframes, usually with `steps(1, end)` to snap rather than
tween. If you find yourself wanting a `<script>`, pre-render the frames.

Renders must be **deterministic** — seeded RNG everywhere (`random.Random(seed)`,
an LCG for the starfield). The Action commits on a cron; nondeterminism means a
noise diff twice a day.

## Gotchas that have already cost time

- **Escape section titles.** `_esc()` was applied to chip labels but not
  section headings; a raw `&` in `"Web - Frontend & Backend"` made the SVG
  invalid XML and it silently rendered as nothing.
- **GitHub's Camo proxy caches by URL.** A broken SVG stays broken on the
  profile even after you push the fix and hard-refresh. Rename the file to bust
  it (that is why it is `tech-stack.svg`, not `stack.svg`).
- **A CSS `transform` overrides the SVG `transform` attribute.** The stats ring
  spin animation ends at `rotate(0deg)`, which clobbered `transform="rotate(-90)"`
  and swung the arc's start to 3 o'clock. Fix is a wrapper `<g>`.
- **`file_pattern` in the workflow must list every generated file.** It was
  pinned to `assets/card.svg`, so the stats panel and `stats.json` were
  regenerated then thrown away on every run.
- **`git pull` before editing.** The Action commits to `main` on a 12h cron
  *and* on push, so it races local edits constantly. Standard conflict
  resolution: take the Action's `stats.json`, re-render both SVGs from it,
  then conclude the merge.
- Column alignment in the card's stats block is monospace advance-width math —
  `STAT_KEY_W` is the shared key width, threaded through `row_text`/`glitch_stack`
  as `klen`. Glyph substitutions must stay ASCII so line width survives.
- The rank letter in `make_stats.py` is a **local heuristic**, not an official
  GitHub rank. Say so if it ever gets surfaced as one.

## Conventions

- `.gitattributes` forces `text eol=lf` for `*.svg`/`*.json`/`*.py`, and every
  file write passes `newline="\n"`. Keep both — this is a Windows machine.
- Theme is "astra moon and emerald green"; colours live in `THEME` in
  `make_card.py` and are reused by the other two renderers.
- `INFO` in `make_card.py` accepts a str, a callable, or a list — a list means
  rotating content and must have exactly `MULTI_N` entries.
- Times/positions in the animations are seconds against `CYCLE_S`; the meteor
  is keyed off `M_START`/`M_HIT`/`M_END` and `IMPACT`.

## Git commits

Never add a `Co-Authored-By: Claude ...` trailer.
