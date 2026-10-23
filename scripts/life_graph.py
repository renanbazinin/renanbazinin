#!/usr/bin/env python3
"""Play Conway's Game of Life (B3/S23) on my GitHub contribution calendar.

Every day with at least one contribution becomes a living cell. The board
(weeks x weekdays, wrapped into a torus) then evolves until a state repeats
or MAX_GENS is reached. Output: <out>/life-dark.svg and <out>/life-light.svg,
plain SVG + CSS keyframes with no scripts and no external resources, so
GitHub can show them through a normal <img>.

Standard library only. In GitHub Actions the calendar comes from the GraphQL
API with GITHUB_TOKEN; if that call fails, the script falls back to the public
https://github-contributions-api.jogruber.de API. For a local test, pass
--input with a JSON file saved from
https://github-contributions-api.jogruber.de/v4/<user>?y=last
"""
import argparse
import datetime as dt
import json
import os
import sys
import urllib.request
from xml.sax.saxutils import escape

QUERY = """query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}"""

PITCH, CELL, RADIUS = 14, 11, 2      # grid pitch, cell size and corner radius in px
LEFT, TOP = 46, 64                   # grid origin inside the card
MAX_GENS = 72
HOLD_GRAPH, HOLD_SEED, STEP, HOLD_END, FADE = 3.4, 1.6, 0.17, 2.2, 0.6   # seconds

THEMES = {
    "dark": dict(bg="#0d1117", border="#30363d", empty="#161b22", text="#e6edf3",
                 muted="#7d8590", levels=["#0e4429", "#006d32", "#26a641", "#39d353"],
                 alive="#7aa2f7", born="#ffb454"),
    "light": dict(bg="#ffffff", border="#d0d7de", empty="#ebedf0", text="#1f2328",
                  muted="#656d76", levels=["#9be9a8", "#40c463", "#30a14e", "#216e39"],
                  alive="#0969da", born="#bc4c00"),
}
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"


def http_json(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "life-graph", **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def fetch_graphql(login, token):
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    data = http_json("https://api.github.com/graphql", body,
                     {"Authorization": f"bearer {token}", "Content-Type": "application/json"})
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [(d["date"], d["contributionCount"]) for w in cal["weeks"] for d in w["contributionDays"]]
    return cal["totalContributions"], days


def parse_jogruber(data):
    days = [(d["date"], d["count"]) for d in data["contributions"]]
    total = data.get("total", {}).get("lastYear", sum(c for _, c in days))
    return total, days


def fetch_jogruber(login):
    return parse_jogruber(http_json(f"https://github-contributions-api.jogruber.de/v4/{login}?y=last"))


def build_board(days):
    """Columns are weeks (Sunday first), rows are weekdays, like GitHub's calendar."""
    days = sorted(days)
    first_day = dt.date.fromisoformat(days[0][0])
    first = first_day - dt.timedelta(days=(first_day.weekday() + 1) % 7)
    last = dt.date.fromisoformat(days[-1][0])
    width = (last - first).days // 7 + 1
    grid = [[0] * 7 for _ in range(width)]
    nonzero = sorted(c for _, c in days if c > 0) or [1]
    quart = [nonzero[int(len(nonzero) * f)] for f in (0.25, 0.5, 0.75)]
    levels = [[], [], [], []]
    for date, count in days:
        k = (dt.date.fromisoformat(date) - first).days
        if count > 0:
            grid[k // 7][k % 7] = 1
            levels[sum(count > q for q in quart)].append((k // 7, k % 7))
    sundays = [first + dt.timedelta(weeks=i) for i in range(width)]
    return grid, levels, sundays


def step(grid):
    w, h = len(grid), 7
    out = [[0] * h for _ in range(w)]
    for x in range(w):
        for y in range(h):
            n = sum(grid[(x + dx) % w][(y + dy) % h]
                    for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy)
            out[x][y] = 1 if n == 3 or (n == 2 and grid[x][y]) else 0
    return out


def evolve(seed):
    gens, seen = [seed], {repr(seed)}
    while len(gens) <= MAX_GENS:
        nxt = step(gens[-1])
        gens.append(nxt)
        if repr(nxt) in seen:        # a still life or an oscillator: stop here
            break
        seen.add(repr(nxt))
    return gens


def path(cells):
    """One compact path for a set of cells, merging horizontal runs (cell units)."""
    rows = {}
    for x, y in cells:
        rows.setdefault(y, []).append(x)
    out = []
    for y in sorted(rows):
        xs = sorted(rows[y])
        start = prev = xs[0]
        for x in xs[1:] + [None]:
            if x is not None and x == prev + 1:
                prev = x
                continue
            n = prev - start + 1
            out.append(f"M{start} {y}h{n}v1h-{n}z")
            if x is not None:
                start = prev = x
    return "".join(out)


def keyframes(name, start, end, total, fade_in=0.0, fade_out=0.0, wrap=0.0):
    """Opacity 1 between start and end of the loop. wrap>0: also visible at loop start,
    fading back in during the last `wrap` seconds."""
    eps = 0.02
    if wrap:
        stops = [(0, 1), (end, 1), (end + (fade_out or eps), 0), (total - wrap, 0), (total, 1)]
    else:
        stops = [(0, 0), (start - (0 if fade_in else eps), 0), (start + fade_in, 1),
                 (end, 1), (end + (fade_out or eps), 0), (total, 0)]
    body = "".join(f"{min(100.0, t / total * 100):.2f}%{{opacity:{o}}}" for t, o in stops)
    return f"@keyframes {name}{{{body}}}"


def month_labels(sundays, width):
    """Like GitHub: a label at the first week of each month, skipping one that would crowd the next."""
    starts = [i for i in range(width) if i == 0 or sundays[i].month != sundays[i - 1].month]
    keep = []
    for n, i in enumerate(starts):
        nxt = starts[n + 1] if n + 1 < len(starts) else width
        if nxt - i < 3 and n == 0:
            continue                  # a partial first month: its label would collide with the next
        if keep and i - keep[-1] < 3:
            continue
        if i > width - 2:
            continue                  # no room at the right edge
        keep.append(i)
    return [(i, sundays[i].strftime("%b")) for i in keep]


def build_svg(theme, user, total, grid, levels, sundays, gens):
    t = THEMES[theme]
    w = len(grid)
    gw, gh = w * PITCH, 7 * PITCH
    width, height = LEFT + gw + 22, TOP + gh + 56
    n = len(gens) - 1
    t_seed = HOLD_GRAPH
    t_life = t_seed + HOLD_SEED
    t_last = t_life + (n - 1) * STEP           # when the final generation appears
    loop = round(t_last + STEP + HOLD_END + FADE, 2)
    last_end = loop - FADE

    css = [f".s{{font-family:{SANS}}}.m{{font-family:{MONO}}}.f{{opacity:0}}",
           f".a{{animation-duration:{loop}s;animation-iteration-count:infinite;"
           "animation-timing-function:linear}"]
    layers, texts = [], []

    # Phase A: the real calendar, coloured by level. Visible at start, fades back in at the end.
    css.append(keyframes("ka", 0, t_seed, loop, fade_out=0.4, wrap=FADE))
    lv = "".join(f'<path fill="{t["levels"][i]}" d="{path(c)}"/>' for i, c in enumerate(levels) if c)
    layers.append(f'<g class="a" style="animation-name:ka">{lv}</g>')

    # Phase B: generation 0 (the seed). Phase C: every following generation.
    prev = None
    for i, g in enumerate(gens):
        alive = [(x, y) for x in range(w) for y in range(7) if g[x][y]]
        if i == 0:
            start, end, fade_in, kept, born = t_seed, t_life, 0.4, alive, []
        else:
            start = t_life + (i - 1) * STEP
            end = start + STEP if i < n else last_end
            fade_in = 0.0
            kept = [c for c in alive if prev[c[0]][c[1]]]
            born = [c for c in alive if not prev[c[0]][c[1]]]
        css.append(keyframes(f"k{i}", start, end, loop, fade_in=fade_in,
                             fade_out=FADE if i == n else 0.0))
        parts = ""
        if kept:
            parts += f'<path fill="{t["alive"]}" d="{path(kept)}"/>'
        if born:
            parts += f'<path fill="{t["born"]}" d="{path(born)}"/>'
        layers.append(f'<g class="a f" style="animation-name:k{i}">{parts}</g>')
        prev = g

    # One status line per phase / generation.
    status = [(0, t_seed, "s", f"My real calendar: {total:,} contributions in the last year."),
              (t_seed, t_life, "s", "Every day with a contribution becomes a living cell. Rules: B3/S23.")]
    for i in range(1, n + 1):
        start = t_life + (i - 1) * STEP
        end = start + STEP if i < n else last_end
        tail = " · settled" if i == n and n < MAX_GENS else ""
        status.append((start, end, "m", f"generation {i:02d} · population {sum(map(sum, gens[i]))}{tail}"))
    y_status = TOP + gh + 34
    for j, (start, end, font, label) in enumerate(status):
        if j == 0:
            css.append(keyframes("t0", 0, end, loop, fade_out=0.3, wrap=FADE))
            cls = "a"
        else:
            css.append(keyframes(f"t{j}", start, end, loop,
                                 fade_out=FADE if j == len(status) - 1 else 0.0))
            cls = "a f"
        texts.append(f'<text class="{cls} {font}" style="animation-name:t{j}" '
                     f'x="{LEFT}" y="{y_status}">{escape(label)}</text>')

    # Legends: contribution levels while the real calendar shows, cell states while Life runs.
    css.append(keyframes("la", 0, t_seed, loop, fade_out=0.4, wrap=FADE))
    css.append(keyframes("lb", t_seed, last_end, loop, fade_in=0.4, fade_out=FADE))
    css.append("@media (prefers-reduced-motion:reduce){.a{animation:none!important}}")

    lx, ly = LEFT + gw, TOP + gh + 23
    sq = lambda x, fill: f'<rect x="{x}" y="{ly}" width="11" height="11" rx="2" fill="{fill}"/>'
    legend_a =(f'<g class="a" style="animation-name:la"><text x="{lx - 104}" y="{ly + 10}" text-anchor="end">Less</text>'
                + "".join(sq(lx - 98 + k * 14, c) for k, c in enumerate([t["empty"]] + t["levels"]))
                + f'<text x="{lx - 26}" y="{ly + 10}">More</text></g>')
    legend_b = (f'<g class="a f" style="animation-name:lb">'
                f'{sq(lx - 216, t["empty"])}<text x="{lx - 200}" y="{ly + 10}">empty</text>'
                f'{sq(lx - 152, t["alive"])}<text x="{lx - 136}" y="{ly + 10}">survived</text>'
                f'{sq(lx - 78, t["born"])}<text x="{lx - 62}" y="{ly + 10}">just born</text></g>')

    months = "".join(f'<text x="{LEFT + i * PITCH}" y="{TOP - 9}">{label}</text>'
                     for i, label in month_labels(sundays, w))
    weekdays = "".join(f'<text x="{LEFT - 8}" y="{TOP + r * PITCH + 10}" text-anchor="end">{d}</text>'
                       for r, d in ((1, "Mon"), (3, "Wed"), (5, "Fri")))

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
<title id="title">{escape(user)}'s GitHub contribution calendar playing Conway's Game of Life</title>
<desc id="desc">The last year of contributions ({total:,}) is shown first; then every day with a contribution becomes a living cell and the board evolves under the B3/S23 rules for {n} generations.</desc>
<style>{"".join(css)}</style>
<defs>
<pattern id="pe" x="{LEFT}" y="{TOP}" width="{PITCH}" height="{PITCH}" patternUnits="userSpaceOnUse"><rect width="{CELL}" height="{CELL}" rx="{RADIUS}" fill="{t["empty"]}"/></pattern>
<pattern id="pm" x="{LEFT}" y="{TOP}" width="{PITCH}" height="{PITCH}" patternUnits="userSpaceOnUse"><rect width="{CELL}" height="{CELL}" rx="{RADIUS}" fill="#fff"/></pattern>
<mask id="cells" maskUnits="userSpaceOnUse" x="0" y="0" width="{width}" height="{height}"><rect x="{LEFT}" y="{TOP}" width="{gw}" height="{gh}" fill="url(#pm)"/></mask>
</defs>
<rect x=".5" y=".5" width="{width - 1}" height="{height - 1}" rx="10" fill="{t["bg"]}" stroke="{t["border"]}"/>
<text class="s" x="{LEFT - 26}" y="31" font-size="16" font-weight="600" fill="{t["text"]}">Conway's Game of Life, seeded with my last year on GitHub</text>
<g class="s" font-size="11" fill="{t["muted"]}">{months}{weekdays}</g>
<rect x="{LEFT}" y="{TOP}" width="{gw}" height="{gh}" fill="url(#pe)"/>
<g mask="url(#cells)"><g transform="translate({LEFT} {TOP}) scale({PITCH})">{"".join(layers)}</g></g>
<g font-size="13" fill="{t["muted"]}">{"".join(texts)}</g>
<g class="s" font-size="12" fill="{t["muted"]}">{legend_a}{legend_b}</g>
</svg>
"""


def main():
    ap = argparse.ArgumentParser(description="Render the contribution calendar as Game of Life SVGs.")
    ap.add_argument("--user", default=os.environ.get("GITHUB_REPOSITORY_OWNER", "renanbazinin"))
    ap.add_argument("--input", help="contributions JSON (jogruber v4 format) instead of the API")
    ap.add_argument("--out", default="dist")
    args = ap.parse_args()

    if args.input:
        with open(args.input, encoding="utf-8") as fh:
            total, days = parse_jogruber(json.load(fh))
    else:
        token = os.environ.get("GITHUB_TOKEN")
        try:
            if not token:
                raise RuntimeError("GITHUB_TOKEN is not set")
            total, days = fetch_graphql(args.user, token)
        except Exception as err:  # noqa: BLE001 - any failure falls back to the public API
            print(f"GraphQL calendar unavailable ({err}); using github-contributions-api.jogruber.de",
                  file=sys.stderr)
            total, days = fetch_jogruber(args.user)

    if not days:
        sys.exit("no contribution days returned")
    grid, levels, sundays = build_board(days)
    gens = evolve(grid)
    os.makedirs(args.out, exist_ok=True)
    for theme in THEMES:
        svg = build_svg(theme, args.user, total, grid, levels, sundays, gens)
        target = os.path.join(args.out, f"life-{theme}.svg")
        with open(target, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(svg)
        print(f"{target}: {len(svg.encode()):,} bytes, {len(gens) - 1} generations")


if __name__ == "__main__":
    main()
