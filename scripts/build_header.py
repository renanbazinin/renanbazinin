#!/usr/bin/env python3
"""Build the animated profile header: desktop and phone layouts, dark and light.

    python scripts/build_header.py

Standard library only (Python 3.8+). It writes four files next to README.md:

    assets/header-dark.svg          assets/header-light.svg
    assets/header-mobile-dark.svg   assets/header-mobile-light.svg

The scene: a terminal types `./life --seed "RENAN BAZININ"`, the name is born
cell by cell and holds for about ten seconds, then it is handed to Conway's
rules (B3/S23) for 14 real generations before it forms again. Real gliders
drift across the sky, and a small Forktown-style street hangs a string of
lanterns above its rooftops.

Pure SVG + CSS keyframes: no scripts, no external fonts or images, so it works
inside GitHub's <img> sandbox. With prefers-reduced-motion the header is a
still frame with the name fully formed. Edit the text constants or THEMES and
re-run; the output is deterministic (fixed random seed).
"""
import os
import random
from xml.sax.saxutils import escape

SUBTITLE = "Full-stack developer · B.Sc. Computer Science (MTA)"

# ---- timeline, in seconds -------------------------------------------------
LOOP = 14.8           # one full cycle
BIRTH = 0.3           # the first name cells appear
RAMP = 0.2            # each batch of cells fades in this fast
T_LIFE = 11.2         # the name is handed to the rules here (held ~10 s before)
GENS, STEP = 14, 0.18  # generations shown, seconds per generation
HOLD_LAST, FADE_LAST = 0.45, 0.4
LAST_START = T_LIFE + (GENS - 1) * STEP
T_FADE = LAST_START + HOLD_LAST       # the last generation starts fading here
assert T_FADE + FADE_LAST < LOOP - 0.2, "timeline does not fit in the loop"
EPS = 0.02

SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"

FONT = {
    "R": ["XXXX.", "X...X", "X...X", "XXXX.", "X.X..", "X..X.", "X...X"],
    "E": ["XXXXX", "X....", "X....", "XXXX.", "X....", "X....", "XXXXX"],
    "N": ["X...X", "XX..X", "XX..X", "X.X.X", "X..XX", "X..XX", "X...X"],
    "A": [".XXX.", "X...X", "X...X", "XXXXX", "X...X", "X...X", "X...X"],
    "B": ["XXXX.", "X...X", "X...X", "XXXX.", "X...X", "X...X", "XXXX."],
    "Z": ["XXXXX", "....X", "...X.", "..X..", ".X...", "X....", "XXXXX"],
    "I": ["XXX", ".X.", ".X.", ".X.", ".X.", ".X.", "XXX"],
}

LAYOUTS = {
    # 1200 wide: shown at about 846 px on github.com, so 28 px text reads as about 20 px.
    "desktop": dict(
        W=1200, H=340, radius=18,
        name_lines=["RENAN BAZININ"], line_gap=2, pitch=12, pix=10, y0=84, band_y=(-3, 9),
        prompt='$ ./life --seed "RENAN BAZININ" --rule B3/S23', prompt_xy=(40, 38), prompt_fs=15, char_w=9,
        counter_xy=(1160, 38), counter_fs=15,
        subtitle=[(600, 222, 28, 600, "subtitle", SUBTITLE)],
        stars=(46, 236), gliders=((40, -30, -6.4, False), (560, 350, -30.4, True), (930, -30, -45.6, False)),
        poles=(70, 212), hook=252, sag=266, ground=320, house_h=(18, 33),
    ),
    # 600 wide: picked for screens up to 700 px, shown at about 358 px on a phone.
    "mobile": dict(
        W=600, H=490, radius=16,
        name_lines=["RENAN", "BAZININ"], line_gap=2, pitch=13, pix=11, y0=66, band_y=(-1, 17),
        prompt='$ ./life --seed "RENAN BAZININ"', prompt_xy=(28, 40), prompt_fs=18, char_w=10.8,
        counter_xy=(572, 40), counter_fs=16,
        subtitle=[(300, 322, 30, 600, "accent", "Full-stack developer"),
                  (300, 356, 21, 500, "subtitle", "B.Sc. Computer Science (MTA)")],
        stars=(30, 300), gliders=((24, -30, -6.4, False), (330, 520, -30.4, True), (450, -30, -45.6, False)),
        poles=(40, 260), hook=398, sag=414, ground=468, house_h=(18, 33),
    ),
}

THEMES = {
    "dark": dict(
        sky=("#0b1021", "#141831", "#1b1d36"), star="#c0caf5", glider="#7aa2f7", glider_op=".3",
        prompt="#9aa5ce", dim="#565f89", name=("#7dcfff", "#7aa2f7", "#bb9af7", "#f7768e"),
        glow=True, subtitle="#c0caf5", accent="#7aa2f7", walls=("#1f2335", "#24283b", "#292e42", "#2f334d"),
        wall_stroke=None, roofs=("#bb9af7", "#7aa2f7", "#9ece6a", "#e0af68", "#f7768e", "#7dcfff"),
        lit="#ffd27a", unlit="#3b4261", pole="#3b4261", wire="#565f89",
        lantern="#ffb454", lantern_edge=None, halo=".55", pulse=".5",
        ground="#11142a", ground_line="#2a2e4a", walker="#c0caf5"),
    "light": dict(
        sky=("#eaf0ff", "#f6f8ff", "#fff4e6"), star="#9aa8d6", glider="#0969da", glider_op=".16",
        prompt="#57606a", dim="#8c959f", name=("#0598bc", "#0969da", "#8250df", "#cf222e"),
        glow=False, subtitle="#24292f", accent="#0969da", walls=("#ffffff", "#f6f8fa", "#fff8ec", "#eef4ff"),
        wall_stroke="#d0d7de", roofs=("#8250df", "#0969da", "#1a7f37", "#bf8700", "#cf222e", "#0598bc"),
        lit="#f2c14e", unlit="#c9dcff", pole="#afb8c1", wire="#8c959f",
        # No halo in light mode: on pale walls it read as an orange smudge.
        lantern="#f59e1b", lantern_edge="#9a5b13", halo=None, pulse=".8",
        ground="#e4eaf6", ground_line="#c8d1e0", walker="#24292f"),
}


def fmt(v):
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def pct(t):
    return f"{t / LOOP * 100:.3f}".rstrip("0").rstrip(".") + "%"


def name_cells(lines, gap):
    """Cells of the pixel name, every line centred on the widest one."""
    widths = []
    for line in lines:
        widths.append(sum(3 if ch == " " else len(FONT[ch][0]) + 1 for ch in line) - 1)
    cols = max(widths)
    cells, letters = set(), []
    for li, line in enumerate(lines):
        x, y0 = (cols - widths[li]) // 2, li * (7 + gap)
        for ch in line:
            if ch == " ":
                x += 3
                continue
            rows = FONT[ch]
            own = {(x + c, y0 + r) for r, row in enumerate(rows) for c, v in enumerate(row) if v == "X"}
            cells |= own
            letters.append(sorted(own))
            x += len(rows[0]) + 1
    return cells, letters, cols, len(lines) * 7 + (len(lines) - 1) * gap


def life(cells, x_range, y_range):
    """GENS generations of B3/S23 on a bounded band (cells outside it stay dead)."""
    (x_min, x_max), (y_min, y_max) = x_range, y_range
    gens = [cells]
    for _ in range(GENS):
        counts = {}
        for a, b in gens[-1]:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    p = (a + dx, b + dy)
                    if (dx or dy) and x_min <= p[0] < x_max and y_min <= p[1] < y_max:
                        counts[p] = counts.get(p, 0) + 1
        gens.append({p for p, n in counts.items() if n == 3 or (n == 2 and p in gens[-1])})
    return gens


def strokes(cells):
    """Horizontal runs as 1-unit-wide strokes ("M x y h n") in cell units."""
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
            out.append(f"M{start} {y}h{prev - start + 1}")
            if x is not None:
                start = prev = x
    return "".join(out)


def rects(items):
    """[(x, y, w, h)] -> one path."""
    return "".join(f"M{fmt(x)} {fmt(y)}h{fmt(w)}v{fmt(h)}h-{fmt(w)}z" for x, y, w, h in items)


def glider_phases(mirror):
    cells = {(1, 0), (2, 1), (0, 2), (1, 2), (2, 2)}
    phases = []
    for _ in range(4):
        phases.append(sorted(cells))
        counts = {}
        for a, b in cells:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx or dy:
                        counts[(a + dx, b + dy)] = counts.get((a + dx, b + dy), 0) + 1
        cells = {p for p, n in counts.items() if n == 3 or (n == 2 and p in cells)}
    # A glider moves one cell diagonally every four generations.
    assert cells == {(x + 1, y + 1) for x, y in phases[0]}
    if mirror:
        phases = [[(x, 2 - y) for x, y in ph] for ph in phases]
    return phases


def build(theme_name, layout_name):
    t, L = THEMES[theme_name], LAYOUTS[layout_name]
    W, H, P = L["W"], L["H"], L["pitch"]
    rnd = random.Random(20200411)   # fixed seed: both themes share one layout
    cells, letters, cols, rows = name_cells(L["name_lines"], L["line_gap"])
    x0 = (W - cols * P) // 2
    y0 = L["y0"]
    gens = life(cells, (-(x0 // P), -(x0 // P) + W // P), L["band_y"])
    assert all(gens[1:]), "the name died out too early"

    prompt = L["prompt"]
    chars = [(i, c) for i, c in enumerate(prompt) if c != " "]
    type_step = 0.015
    d_max = 0.15 + len(prompt) * type_step
    ty_off = LOOP - d_max - 0.05

    css = [
        f".s{{font-family:{SANS}}}.m{{font-family:{MONO}}}.h{{opacity:0}}",
        # The name: an outer window hides it while the rules run; batches of cells pop in with their own delays.
        f".nw{{animation:nw {LOOP}s linear infinite}}@keyframes nw{{0%,{pct(T_LIFE)}{{opacity:1}}"
        f"{pct(T_LIFE + EPS)},{pct(LOOP - 0.1)}{{opacity:0}}100%{{opacity:1}}}}",
        f".np{{animation:np {LOOP}s linear infinite backwards}}@keyframes np{{0%{{opacity:0}}"
        f"{pct(RAMP)},{pct(T_LIFE - BIRTH)}{{opacity:1}}{pct(T_LIFE - BIRTH + EPS)},100%{{opacity:0}}}}",
        # One generation frame: visible for STEP seconds, placed in time with a negative delay.
        f".gf{{animation:gf {LOOP}s linear infinite}}@keyframes gf{{0%,{pct(STEP)}{{opacity:1}}"
        f"{pct(STEP + EPS)},100%{{opacity:0}}}}",
        f".gl{{animation:gz {LOOP}s linear infinite}}@keyframes gz{{0%,{pct(HOLD_LAST)}{{opacity:1}}"
        f"{pct(HOLD_LAST + FADE_LAST)},100%{{opacity:0}}}}",
        f".c0{{animation:c0 {LOOP}s linear infinite}}@keyframes c0{{0%,{pct(T_LIFE)}{{opacity:1}}"
        f"{pct(T_LIFE + EPS)},{pct(LOOP - 0.4)}{{opacity:0}}100%{{opacity:1}}}}",
        # The prompt types itself character by character and fades out with the last generation.
        f".ty{{animation:ty {LOOP}s linear infinite backwards}}@keyframes ty{{0%{{fill-opacity:0}}"
        f"{pct(0.03)},{pct(ty_off)}{{fill-opacity:1}}{pct(ty_off + EPS)},100%{{fill-opacity:0}}}}",
        f".pw{{animation:pw {LOOP}s linear infinite}}@keyframes pw{{0%,{pct(T_FADE)}{{opacity:1}}"
        f"{pct(T_FADE + 0.3)},{pct(LOOP - 0.02)}{{opacity:0}}100%{{opacity:1}}}}",
        ".cur{animation:bl 1.1s steps(1) infinite}@keyframes bl{50%{opacity:0}}",
        ".st{animation:tw 4s ease-in-out infinite}@keyframes tw{0%,100%{opacity:.15}50%{opacity:1}}",
        f".lg{{animation:lg 2.8s ease-in-out infinite}}@keyframes lg{{0%,100%{{opacity:{t['pulse']}}}50%{{opacity:1}}}}",
        ".fl{animation:fl 6s linear infinite}@keyframes fl{0%,44%,56%,100%{opacity:1}50%{opacity:.2}}",
        ".gp{animation:gp .8s step-end infinite}@keyframes gp{0%{opacity:1}25%,100%{opacity:0}}",
        f".wk{{animation:wk {46 * W / 1200:.0f}s linear infinite}}@keyframes wk{{from{{transform:translateX(-40px)}}"
        f"to{{transform:translateX({W + 40}px)}}}}",
        ".l1,.l2{animation:lw .5s step-end infinite}.l2{animation-delay:-.25s}"
        "@keyframes lw{0%{opacity:1}50%,100%{opacity:0}}",
    ]
    for i, (dur, delay) in enumerate(((3.2, -0.4), (4.4, -1.9), (5.6, -3.1), (3.8, -2.6), (5.0, -0.9))):
        css.append(f".d{i}{{animation-duration:{dur}s;animation-delay:{delay}s}}")

    defs = [
        f'<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{t["sky"][0]}"/>'
        f'<stop offset=".6" stop-color="{t["sky"][1]}"/><stop offset="1" stop-color="{t["sky"][2]}"/></linearGradient>',
        # The name is drawn in cell units, so its gradient is too.
        f'<linearGradient id="ink" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="{cols}" y2="0">'
        + "".join(f'<stop offset="{i / 3:.2f}" stop-color="{c}"/>' for i, c in enumerate(t["name"]))
        + "</linearGradient>",
        f'<pattern id="px" x="{x0}" y="{y0}" width="{P}" height="{P}" patternUnits="userSpaceOnUse">'
        f'<rect width="{L["pix"]}" height="{L["pix"]}" rx="2" fill="#fff"/></pattern>',
        f'<mask id="grid" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}">'
        f'<rect width="{W}" height="{H}" fill="url(#px)"/></mask>',
        f'<clipPath id="card"><rect width="{W}" height="{H}" rx="{L["radius"]}"/></clipPath>',
    ]
    if t["halo"]:
        defs.append(f'<radialGradient id="halo"><stop offset="0" stop-color="{t["lantern"]}" stop-opacity="{t["halo"]}"/>'
                    f'<stop offset="1" stop-color="{t["lantern"]}" stop-opacity="0"/></radialGradient>')
    if t["glow"]:
        defs.append('<filter id="glow" x="-5%" y="-30%" width="110%" height="160%"><feGaussianBlur stdDeviation="4" '
                    'result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>')

    out = [f'<rect width="{W}" height="{H}" fill="url(#sky)"/>']

    # Stars, twinkling in five groups.
    n_stars, star_ymax = L["stars"]
    groups = [[] for _ in range(5)]
    for _ in range(n_stars):
        s = rnd.choice((2, 2, 3))
        groups[rnd.randrange(5)].append((rnd.randrange(12, W - 12), rnd.randrange(8, star_ymax), s, s))
    out.append(f'<g fill="{t["star"]}" opacity=".7">'
               + "".join(f'<path class="st d{i}" d="{rects(g)}"/>' for i, g in enumerate(groups) if g) + "</g>")

    # Real gliders: one generation per 0.2 s, so a 0.8 s phase cycle moves a glider one cell.
    gp, cycles = 6, 64
    for gx, gy, delay, mirror in L["gliders"]:
        move = f"gm{gx}"
        css.append(f"@keyframes {move}{{to{{transform:translate({gp * cycles}px,"
                   f"{-gp * cycles if mirror else gp * cycles}px)}}}}")
        paths = "".join(f'<path class="gp{" h" if k else ""}" style="animation-delay:{delay + 0.2 * k:.1f}s" '
                        f'd="{rects([(x * gp, y * gp, 5, 5) for x, y in ph])}"/>'
                        for k, ph in enumerate(glider_phases(mirror)))
        out.append(f'<g transform="translate({gx} {gy})"><g style="animation:{move} {0.8 * cycles:.1f}s '
                   f'steps({cycles},end) {delay}s infinite" fill="{t["glider"]}" opacity="{t["glider_op"]}">'
                   f'{paths}</g></g>')

    # The terminal prompt: one monospace cell per character, so it types itself.
    px0, py = L["prompt_xy"]
    cw = L["char_w"]
    xs = " ".join(fmt(px0 + i * cw) for i, _ in chars)
    spans = "".join(f'<tspan class="ty" style="animation-delay:{0.15 + i * type_step:.3f}s">'
                    f'{escape(c, {chr(34): "&quot;"})}</tspan>' for i, c in chars)
    out.append(f'<text class="m pw" x="{xs}" y="{py}" font-size="{L["prompt_fs"]}" fill="{t["prompt"]}">{spans}</text>')
    fs = L["prompt_fs"]
    out.append(f'<rect class="cur" x="{fmt(px0 + len(prompt) * cw + 3)}" y="{fmt(py - fs * 0.85)}" '
               f'width="{fmt(cw)}" height="{fmt(fs * 1.1)}" fill="{t["dim"]}"/>')

    # The name, born in small random batches from left to right; then each generation.
    parts = []
    for li, letter in enumerate(letters):
        shuffled = letter[:]
        rnd.shuffle(shuffled)
        half = len(shuffled) // 2
        for k, group in enumerate((shuffled[:half], shuffled[half:])):
            parts.append(f'<path class="np" style="animation-delay:{BIRTH + li * 0.06 + k * 0.14:.2f}s" '
                         f'd="{strokes(group)}"/>')
    frames = []
    for g in range(1, GENS + 1):
        start = T_LIFE + (g - 1) * STEP
        cls = "gl" if g == GENS else "gf"
        frames.append(f'<path class="{cls} h" style="animation-delay:{start - LOOP:.2f}s" d="{strokes(gens[g])}"/>')
    inner = (f'<g mask="url(#grid)"><g transform="translate({x0} {fmt(y0 + P / 2)}) scale({P})" fill="none" '
             f'stroke="url(#ink)" stroke-width="1"><g class="nw">{"".join(parts)}</g>{"".join(frames)}</g></g>')
    out.append(f'<g filter="url(#glow)">{inner}</g>' if t["glow"] else inner)

    # Generation counter, top right.
    cx, cy = L["counter_xy"]
    labels = [f'<text class="c0" x="{cx}" y="{cy}">B3/S23 · gen 00</text>']
    for g in range(1, GENS + 1):
        start = T_LIFE + (g - 1) * STEP
        cls = "gl" if g == GENS else "gf"
        labels.append(f'<text class="{cls} h" style="animation-delay:{start - LOOP:.2f}s" x="{cx}" y="{cy}">'
                      f'B3/S23 · gen {g:02d}</text>')
    out.append(f'<g class="m" font-size="{L["counter_fs"]}" fill="{t["dim"]}" text-anchor="end">{"".join(labels)}</g>')

    for sx, sy, size, weight, color, text in L["subtitle"]:
        out.append(f'<text class="s" x="{sx}" y="{sy}" font-size="{size}" font-weight="{weight}" '
                   f'text-anchor="middle" fill="{t[color]}">{escape(text)}</text>')

    # The street. Poles and the lantern string sit above the rooftops; houses stand in front of the poles.
    ground, hook, sag = L["ground"], L["hook"], L["sag"]
    first_pole, spacing = L["poles"]
    poles = list(range(first_pole, W, spacing))
    out.append(f'<path fill="{t["pole"]}" d="{rects([(p - 1, hook - 1, 3, ground - hook + 1) for p in poles])}"/>')
    wire, lamp_groups = [], [[] for _ in range(3)]
    for a, b in zip(poles, poles[1:]):
        mid = (a + b) / 2
        wire.append(f"M{a} {hook}Q{fmt(mid)} {sag} {b} {hook}")
        for f in (0.25, 0.5, 0.75):
            lx = round((1 - f) ** 2 * a + 2 * (1 - f) * f * mid + f * f * b)
            ly = round((1 - f) ** 2 * hook + 2 * (1 - f) * f * sag + f * f * hook)
            lamp_groups[rnd.randrange(3)].append((lx, ly))
    lamp_bottom = max(ly + 14 for g in lamp_groups for _, ly in g)

    walls, roofs, lit, unlit, flick = {}, {}, [], [], [[], [], []]
    lo, hi = L["house_h"]
    x = 6
    while x < W - 30:
        w = rnd.choice((44, 52, 60, 68))
        h = rnd.randrange(lo, hi)
        top = ground - h
        assert top - 13 > lamp_bottom, "a roof would overlap the lantern string"
        walls.setdefault(rnd.choice(t["walls"]), []).append((x, top, w, h))
        roof = rnd.choice(t["roofs"])
        if rnd.random() < 0.65:
            roofs.setdefault(roof, []).append(f"M{x - 3} {top}L{fmt(x + w / 2)} {top - 13}L{x + w + 3} {top}z")
        else:
            roofs.setdefault(roof, []).append(rects([(x - 2, top - 5, w + 4, 5), (x + w - 14, top - 13, 6, 8)]))
        for wx in range(x + 7, x + w - 9, 13):
            for wy in range(top + 6, ground - 10, 12):
                if rnd.random() < 0.55:
                    (flick[rnd.randrange(3)] if rnd.random() < 0.25 else lit).append((wx, wy, 6, 6))
                else:
                    unlit.append((wx, wy, 6, 6))
        x += w + rnd.randrange(8, 20)
    stroke = f' stroke="{t["wall_stroke"]}"' if t["wall_stroke"] else ""
    out.append("".join(f'<path fill="{c}"{stroke} d="{rects(r)}"/>' for c, r in walls.items()))
    out.append("".join(f'<path fill="{c}" d="{"".join(r)}"/>' for c, r in roofs.items()))
    out.append(f'<path fill="{t["unlit"]}" d="{rects(unlit)}"/><path fill="{t["lit"]}" d="{rects(lit)}"/>')
    out.append("".join(f'<path class="fl d{i}" fill="{t["lit"]}" d="{rects(r)}"/>' for i, r in enumerate(flick) if r))

    out.append(f'<path d="{"".join(wire)}" fill="none" stroke="{t["wire"]}" stroke-width="1.5"/>')
    edge = f' stroke="{t["lantern_edge"]}" stroke-width="1"' if t["lantern_edge"] else ""
    for i, lamps in enumerate(lamp_groups):
        if not lamps:
            continue
        halos = ""
        if t["halo"]:
            halos = '<g fill="url(#halo)">' + "".join(f'<circle cx="{lx}" cy="{ly + 9}" r="15"/>' for lx, ly in lamps) + "</g>"
        cords = rects([(lx, ly, 1, 4) for lx, ly in lamps])
        body = rects([(lx - 3.5, ly + 4.5, 8, 10) for lx, ly in lamps])
        out.append(f'<g class="lg d{i}">{halos}<path fill="{t["wire"]}" d="{cords}"/>'
                   f'<path fill="{t["lantern"]}"{edge} d="{body}"/></g>')

    out.append(f'<path fill="{t["ground"]}" d="M0 {ground}h{W}v{H - ground}h-{W}z"/>'
               f'<path fill="{t["ground_line"]}" d="M0 {ground}h{W}v1h-{W}z"/>')

    # A resident walking down the street.
    out.append(f'<g class="wk"><g transform="translate(0 {ground - 16})" fill="{t["walker"]}">'
               f'<path d="M1 0h4v4h-4zM0 5h6v6h-6z"/><path class="l1" d="M0 11h2v5h-2zM4 11h2v5h-2z"/>'
               f'<path class="l2 h" d="M1 11h2v5h-2zM3 11h2v4h-2z"/></g></g>')

    css.append("@media (prefers-reduced-motion:reduce){*{animation:none!important}}")
    title = f"Renan Bazinin: {SUBTITLE}"
    desc = ("Animated header. A terminal runs Conway's Game of Life seeded with the name Renan Bazinin: "
            "the name forms in pixels, holds, then evolves under the B3/S23 rules before forming again. "
            "Gliders cross the sky above a small pixel street with a string of lanterns.")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
            f'role="img" aria-labelledby="t d">\n<title id="t">{escape(title)}</title>\n'
            f'<desc id="d">{escape(desc)}</desc>\n'
            f'<style>{"".join(css)}</style>\n<defs>{"".join(defs)}</defs>\n'
            f'<g clip-path="url(#card)">\n' + "\n".join(out) + "\n</g>\n</svg>\n")


def main():
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
    os.makedirs(root, exist_ok=True)
    for layout in LAYOUTS:
        for theme in THEMES:
            svg = build(theme, layout)
            name = f"header-{theme}.svg" if layout == "desktop" else f"header-mobile-{theme}.svg"
            target = os.path.join(root, name)
            with open(target, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(svg)
            print(f"{os.path.normpath(target)}: {len(svg.encode()):,} bytes")


if __name__ == "__main__":
    main()
