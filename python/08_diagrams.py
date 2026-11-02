"""Explainer diagrams for the story page, drawn with the family's famdiagram
(theme-aware SVG, colors as classes only). Every number in them is read
from a committed output or from lib.py's definitions:

  dg1_reading_a_game  one real game's margin over regulation, with the
                      checkpoint grid and the fourth-quarter situation
                      (output/example_game.csv, lib.grid, lib.SITUATIONS)
  dg2_sigma_fan       the Brownian model's spread of the margin over the
                      fourth quarter from the middle of the 10-14 band, first
                      NBA era against last, with the chance it ends below
                      zero (output/brownian_q4_fan.csv)
  dg3_comeback_grid   NBA comeback rate (PAVA-smoothed) by lead and minutes
                      left in the fourth quarter, first era against last,
                      with the 1% safe-lead line (output/comeback_counts.csv,
                      output/safe_leads.csv)

Run:  python python/08_diagrams.py          (writes figures/dg*.svg)
      python python/08_diagrams.py --check  (fails if a committed SVG
                                             differs from a fresh build)
"""
from __future__ import annotations

import argparse
import math
from datetime import date
import sys
from pathlib import Path

import polars as pl
from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402
import famdiagram as fd  # noqa: E402  (lib puts basketball-analysis-tools on the path)

OUT = lib.ROOT / "output"
FIG = lib.ROOT / "figures"
Q4 = "start of Q4, up 10-14"


def pct(p: float, nd: int = 1) -> str:
    return f"{p * 100:.{nd}f}%"


def clock(T: int) -> str:
    return f"{T // 60}:{T % 60:02d}"


# ---------------------------------------------------------------------------
# 1. How a game is read
# ---------------------------------------------------------------------------

def game_panel(d, g, x0, y0, w, h, t_hi, t_lo, ylo, yhi, every, label_every, size,
               show_band=True, mark_q4=True, end_label=True):
    """Margin step line and checkpoint dots for T in [t_lo, t_hi] seconds
    left, drawn in the box (x0, y0, w, h). Returns the scale functions."""
    X = lambda T: x0 + (t_hi - T) / (t_hi - t_lo) * w  # noqa: E731
    Y = lambda m: y0 + (yhi - m) / (yhi - ylo) * h  # noqa: E731
    _, t_q4, _, a, b = next(s for s in lib.SITUATIONS if s[0] == Q4)
    d.rect(x0, y0, w, h, fill="surface", stroke="rule", sw=1)
    if show_band:
        d.rect(x0, Y(b), w, Y(a) - Y(b), fill="nba", opacity=0.12)
    for m in range(math.ceil(ylo / label_every) * label_every, yhi + 1, label_every):
        d.line(x0, Y(m), x0 + w, Y(m), stroke="rule", sw=1 if m else 1.6)
        d.text(x0 - 6, Y(m) + size * 0.35, f"{m:+d}" if m else "0", size=size,
               fill="ink3", anchor="end")
    ev = g.filter((pl.col("kind") == "event")).sort("T", descending=True)
    pts = []
    prev = None
    for T, m in ev.select("T", "margin").iter_rows():
        if T > t_hi:
            prev = m
            continue
        if T < t_lo:
            break
        if prev is None:
            prev = m
        pts += [(X(T), Y(prev)), (X(T), Y(m))]
        prev = m
    pts.append((X(t_lo), Y(prev)))
    pts.insert(0, (X(t_hi), pts[0][1]))
    d.polyline(pts, stroke="ink2", sw=1.6)
    cp = g.filter((pl.col("kind") == "checkpoint") & pl.col("T").is_between(t_lo, t_hi))
    for T, m in cp.select("T", "margin").iter_rows():
        if T % every == 0:
            d.circle(X(T), Y(m), 2.2, fill="nba")
    if mark_q4 and t_lo <= t_q4 <= t_hi:
        m = cp.filter(pl.col("T") == t_q4)["margin"][0]
        d.line(X(t_q4), y0, X(t_q4), y0 + h, stroke="ink3", sw=1.2, dash="4 3")
        d.circle(X(t_q4), Y(m), 6.5, fill="none", stroke="c8", sw=2.4)
    return X, Y


def dg_game(layout: str) -> fd.Diagram:
    g = pl.read_csv(OUT / "example_game.csv", schema_overrides={"gameId": pl.Utf8})
    r = g.row(0, named=True)
    lead_t, trail_t = r["leader"], r["trailer"]
    nper, plen = lib.regulation("nba", int(r["game_date"][:4]))
    total = nper * plen
    grid = lib.grid(total)
    fine = grid[1] - grid[0]
    coarse = grid[-1] - grid[-2]
    # The last T read every `fine` seconds (the last two minutes).
    switch =max(t for i, t in enumerate(grid[:-1]) if grid[i + 1] - t == fine) + fine
    _, t_q4, _, a, b = next(s for s in lib.SITUATIONS if s[0] == Q4)
    q4m = g.filter((pl.col("kind") == "checkpoint") & (pl.col("T") == t_q4))["margin"][0]
    ev = g.filter(pl.col("kind") == "event")
    ylo = min(ev["margin"].min(), 0) - 3
    yhi = max(ev["margin"].max(), b) + 3
    end_m = ev.filter(pl.col("T") == 0)["margin"][0]
    zev = ev.filter(pl.col("T") <= switch)
    zlo, zhi = min(zev["margin"].min(), 0) - 2, max(zev["margin"].max(), 0) + 2
    when = date.fromisoformat(r["game_date"][:10])
    when = f"{when:%B} {when.day}, {when.year}"
    title = (f"{lead_t} against {trail_t}, {when}: the score margin read at "
             f"every checkpoint")
    if layout == "wide":
        W, H, s = 760, 420, 14
        d = fd.Diagram(W, H, title)
        mx, my, mw, mh = 50, 58, 470, 290
        zx, zy, zw, zh = 590, 58, 150, 290
    else:
        W, H, s = 360, 700, 12
        d = fd.Diagram(W, H, title)
        mx, my, mw, mh = 40, 66, 305, 280
        zx, zy, zw, zh = 40, 420, 305, 200
    d.text(mx, 22, f"{lead_t} lead over {trail_t}, {when}", size=s + 2,
           weight="600")
    d.text(mx, 42, f"Dots: the study's checkpoints, every {coarse} seconds",
           size=s, fill="ink3")
    X, Y = game_panel(d, g, mx, my, mw, mh, total, 0, ylo, yhi, coarse, 10, s)
    # quarter labels
    for p in range(nper):
        t_start = total - p * plen
        if p:
            d.line(X(t_start), my, X(t_start), my + mh, stroke="rule", sw=1)
        d.text((X(t_start) + X(t_start - plen)) / 2, my + mh + s + 6, f"Q{p + 1}",
               size=s, fill="ink3", anchor="middle")
    d.text(mx + 6, Y(b) + s + 2, f"up {a} to {b}", size=s, fill="nba")
    # the fourth-quarter situation
    xq = X(t_q4)
    if layout == "wide":
        d.text(xq - 10, Y(yhi) + s + 6, "Entering the fourth:", size=s, fill="ink",
               anchor="end", weight="600")
        d.text(xq - 10, Y(yhi) + 2 * s + 10, f"{lead_t} up {q4m}", size=s, fill="ink",
               anchor="end")
    else:
        d.text(xq - 8, Y(yhi) + s + 4, "Entering the fourth:", size=s, anchor="end",
               weight="600")
        d.text(xq - 8, Y(yhi) + 2 * s + 8, f"{lead_t} up {q4m}", size=s, anchor="end")
    # the result
    d.text(X(switch) - 6, Y(end_m) + s + 8, f"{trail_t} wins", size=s, fill="c8",
           anchor="end", weight="600")
    d.text(X(switch) - 6, Y(end_m) + 2 * s + 12, f"{r['trailer_final']}-{r['leader_final']}",
           size=s, fill="c8", anchor="end")
    # zoom box on the main panel
    d.rect(X(switch), my, X(0) - X(switch), mh, fill="none", stroke="ink3", sw=1.2,
           dash="3 3")
    # zoom panel: the last two minutes
    zm = switch // 60
    d.text(zx, zy - 22 if layout == "wide" else zy - 30,
           f"Last {zm} minutes:" if layout == "wide" else
           f"Last {zm} minutes: every {fine} seconds",
           size=s, weight="600")
    if layout == "wide":
        d.text(zx, zy - 6, f"every {fine} seconds", size=s, fill="ink3")
    ZX, ZY = game_panel(d, g, zx, zy, zw, zh, switch, 0, zlo, zhi, fine,
                        2 if zhi - zlo <= 12 else 5, s, show_band=False, mark_q4=False)
    for T in (switch, switch // 2, 0):
        d.text(ZX(T), zy + zh + s + 6, clock(T), size=s, fill="ink3",
               anchor="middle")
    if layout == "wide":
        d.line(X(0), my, zx - 30, zy, stroke="ink3", sw=1, dash="3 3")
        d.line(X(0), my + mh, zx - 30, zy + zh, stroke="ink3", sw=1, dash="3 3")
        d.text(mx, H - 14, f"Time runs left to right; a negative margin means "
               f"{trail_t} leads.", size=s, fill="ink3")
    else:
        d.text(mx, H - 34, "Time runs left to right; a negative", size=s, fill="ink3")
        d.text(mx, H - 16, f"margin means {trail_t} leads.", size=s, fill="ink3")
    return d


# ---------------------------------------------------------------------------
# 2. Why a bigger sigma means more comebacks
# ---------------------------------------------------------------------------

def fan_panel(d, x0, y0, w, h, sigma, lead, T, p, ylo, yhi, name, s, dens_w):
    mins = T / 60
    X = lambda t: x0 + t / mins * w  # noqa: E731  t = minutes played in the quarter
    Y = lambda m: y0 + (yhi - m) / (yhi - ylo) * h  # noqa: E731
    d.rect(x0, y0, w + dens_w, h, fill="surface", stroke="rule", sw=1)
    d.rect(x0, Y(0), w + dens_w, Y(ylo) - Y(0), fill="c8", opacity=0.07)
    steps = [mins * i / 48 for i in range(49)]
    for k, op in ((2, 0.16), (1, 0.3)):
        top = [(X(t), Y(lead + k * sigma * math.sqrt(t))) for t in steps]
        bot = [(X(t), Y(lead - k * sigma * math.sqrt(t))) for t in reversed(steps)]
        d.polyline(top + bot, stroke="none", fill="nba", opacity=op)
    d.line(X(0), Y(lead), X(mins), Y(lead), stroke="nba", sw=1.6, dash="5 4")
    d.line(x0, Y(0), x0 + w + dens_w, Y(0), stroke="ink2", sw=1.4)
    d.text(x0 + 4, Y(0) - 5, "tied", size=s, fill="ink3")
    d.text(x0 + 4, Y(0) + s + 4, "trailing team ahead", size=s, fill="c8")
    # the margin's distribution at the buzzer, drawn sideways
    sd = sigma * math.sqrt(mins)
    xb = X(mins)
    peak = norm.pdf(0, scale=sd)
    ms = [ylo + (yhi - ylo) * i / 120 for i in range(121)]
    curve = [(xb + norm.pdf(m - lead, scale=sd) / peak * (dens_w - 8), Y(m)) for m in ms]
    d.polyline([(xb, Y(ylo))] + curve + [(xb, Y(yhi))], stroke="ink3", sw=1.2, fill="none")
    below = [0.0] + sorted((m for m in ms if m < 0), reverse=True)
    tail = ([(xb, Y(0))]
            + [(xb + norm.pdf(m - lead, scale=sd) / peak * (dens_w - 8), Y(m)) for m in below]
            + [(xb, Y(ylo)), (xb, Y(0))])
    d.polyline(tail, stroke="c8", sw=1, fill="c8", opacity=0.8)
    d.line(xb, y0, xb, y0 + h, stroke="rule", sw=1)
    d.text(x0, y0 - 10, name, size=s + 1, weight="600")
    d.text(x0 + w + dens_w, y0 - 10, f"sigma {sigma:.2f}", size=s, fill="nba",
           anchor="end", weight="600")
    d.text(X(0) + 4, Y(lead) - 6, f"up {lead:g}", size=s, fill="nba")
    d.text(xb - 6, Y(ylo) - 8, f"comeback {pct(p)}", size=s, fill="c8", anchor="end",
           weight="600")
    for t, lab in ((0, f"{clock(T)} left"), (mins, "buzzer")):
        d.text(X(t), y0 + h + s + 6, lab, size=s, fill="ink3",
               anchor="start" if t == 0 else "middle")
    return X, Y


def dg_fan(layout: str) -> fd.Diagram:
    fan = pl.read_csv(OUT / "brownian_q4_fan.csv").filter(pl.col("league") == "nba").sort("era")
    first, last = fan.row(0, named=True), fan.row(-1, named=True)
    lead, T = first["lead"], first["T"]
    smax = max(first["sigma"], last["sigma"])
    reach = 2.2 * smax * math.sqrt(T / 60)
    ylo, yhi = math.floor(lead - reach), math.ceil(lead + reach)
    title = (f"The Brownian model's spread of an NBA margin from up {lead:g} entering the "
             f"fourth: sigma {first['sigma']:.2f} against {last['sigma']:.2f}")
    if layout == "wide":
        W, H, s = 760, 400, 14
        d = fd.Diagram(W, H, title)
        boxes = [(30, 84, 250, 260), (400, 84, 250, 260)]
        dens = 80
    else:
        W, H, s = 360, 790, 12
        d = fd.Diagram(W, H, title)
        boxes = [(16, 92, 240, 250), (16, 440, 240, 250)]
        dens = 88
    d.text(boxes[0][0], 24, "Shaded: where the margin is likely to be", size=s + 1,
           weight="600")
    if layout == "wide":
        d.text(boxes[0][0], 44, "Darker band: within 1 sigma x the square root of minutes "
               "played. Lighter band: within 2.", size=s, fill="ink3")
    else:
        d.text(boxes[0][0], 44, "Darker: within 1 sigma x root(minutes", size=s, fill="ink3")
        d.text(boxes[0][0], 60, "played). Lighter: within 2.", size=s, fill="ink3")
    for (x0, y0, w, h), r in zip(boxes, (first, last)):
        X, Y = fan_panel(d, x0, y0, w, h, r["sigma"], lead, T, r["p_comeback"], ylo, yhi,
                         f"NBA {r['era']}", s, dens)
    # The first era's 2-sigma edge, dashed over the last era's fan.
    mins = T / 60
    steps = [mins * i / 48 for i in range(49)]
    for k in (1, -1):
        d.polyline([(X(t), Y(lead + k * 2 * first["sigma"] * math.sqrt(t))) for t in steps],
                   stroke="ink2", sw=1.3, dash="4 3")
    d.text(X(mins * 0.97), Y(lead + 2 * first["sigma"] * math.sqrt(mins)) + s + 14,
           "first era's edge", size=s, fill="ink2", anchor="end")
    if layout == "wide":
        d.text(30, H - 14, "Red: the share of games that end with the trailing team "
               "ahead, the model's comeback chance.", size=s, fill="ink3")
    else:
        d.text(16, H - 34, "Red: games that end with the trailing", size=s, fill="ink3")
        d.text(16, H - 16, "team ahead, the model's comeback chance.", size=s, fill="ink3")
    return d


# ---------------------------------------------------------------------------
# 3. Comeback-rate grid
# ---------------------------------------------------------------------------

def dg_grid(layout: str) -> fd.Diagram:
    cc = pl.read_csv(OUT / "comeback_counts.csv").filter(pl.col("league") == "nba")
    sl = pl.read_csv(OUT / "safe_leads.csv", null_values=[""]).filter(
        (pl.col("league") == "nba") & (pl.col("q") == lib.THRESHOLDS[0]))
    eras = sorted(cc["era"].unique().to_list())
    pick = [eras[0], eras[-1]]
    _, t_q4, _, a, b = next(s for s in lib.SITUATIONS if s[0] == Q4)
    cols = list(range(60, t_q4 + 1, 60))
    safe = sl.filter(pl.col("era").is_in(pick) & pl.col("T").is_in(cols))
    top = int(safe["safe_lead"].max()) + 2
    rows = list(range(1, top + 1))
    th = lib.THRESHOLDS
    bins = [(0.0, th[0], 0.0), (th[0], th[1], 0.32), (th[1], th[2], 0.58), (th[2], 1.01, 0.9)]
    labels = [f"under {pct(th[0], 0)}", f"{pct(th[0], 0)} to {pct(th[1], 0)}",
              f"{pct(th[1], 0)} to {pct(th[2], 0)}", f"over {pct(th[2], 0)}"]
    title = (f"NBA comeback rate by lead and minutes left, {pick[0]} against {pick[1]}, "
             f"with the {pct(th[0], 0)} safe-lead line")
    if layout == "wide":
        W, s, cw, ch = 760, 14, 25, 11
        origins = [(56, 96), (56 + 12 * cw + 70, 96)]
    else:
        W, s, cw, ch = 360, 12, 24, 10
        origins = [(44, 96), (44, 96 + top * ch + 100)]
    gh = top * ch
    H = origins[-1][1] + gh + (92 if layout == "narrow" else 104)
    d = fd.Diagram(W, H, title)
    # legend
    lx = origins[0][0]
    d.text(lx - (30 if layout == "wide" else 28), 22,
           "Share of games the trailing team wins", size=s + 1, weight="600")
    step = (W - lx - 10) / 4 if layout == "wide" else (W - lx) / 2
    for i, ((lo, hi, op), lab) in enumerate(zip(bins, labels)):
        if layout == "wide":
            bx, by = lx - 30 + i * 165, 36
        else:
            bx, by = lx - 28 + (i % 2) * 165, 34 + (i // 2) * 20
        if op:
            d.rect(bx, by, 14, 14, fill="nba", opacity=op)
        else:
            d.rect(bx, by, 14, 14, fill="surface2", stroke="rule", sw=1)
        d.text(bx + 20, by + 12, lab, size=s, fill="ink2")
    for (gx, gy), era in zip(origins, pick):
        e = cc.filter((pl.col("era") == era) & pl.col("T").is_in(cols))
        fit = {(t, l): v for t, l, v in e.select("T", "lead", "fit").iter_rows()}
        X = lambda T, gx=gx: gx + cols.index(T) * cw  # noqa: E731
        Y = lambda L, gy=gy: gy + (top - L) * ch  # noqa: E731
        d.text(gx, gy - 10, f"NBA {era}", size=s + 1, weight="600")
        for T in cols:
            for L in rows:
                v = fit.get((T, L))
                if v is None:
                    continue
                op = next(o for lo, hi, o in bins if lo <= v < hi) if v > 0 else 0.0
                if op:
                    d.rect(X(T) + 0.5, Y(L) + 0.5, cw - 1, ch - 1, fill="nba", opacity=op)
                else:
                    d.rect(X(T) + 0.5, Y(L) + 0.5, cw - 1, ch - 1, fill="surface2")
        # the 1% safe-lead line: the lower edge of the safe lead's row
        sr = dict(safe.filter(pl.col("era") == era).select("T", "safe_lead").iter_rows())
        pts = []
        for T in cols:
            L = sr.get(T)
            if L is None:
                continue
            yv = Y(L) + ch
            pts += [(X(T), yv), (X(T) + cw, yv)]
        d.polyline(pts, stroke="c8", sw=2.6)
        # the fourth-quarter situation
        d.rect(X(t_q4), Y(b), cw, (b - a + 1) * ch, fill="none", stroke="ink", sw=1.8)
        q4s = sr.get(t_q4)
        d.text(X(t_q4) + cw - 2, Y(q4s) + ch - 4 - 6, f"safe: {q4s}", size=s, fill="c8",
               anchor="end", weight="600")
        for L in rows:
            if L % 5 == 0 or L == 1:
                d.text(gx - 5, Y(L) + ch - 1, str(L), size=s, fill="ink3", anchor="end")
        for T in cols:
            if (T // 60) % 3 == 0 or T == cols[0]:
                d.text(X(T) + cw / 2, gy + gh + s + 4, str(T // 60), size=s, fill="ink3",
                       anchor="middle")
        d.text(gx + 6 * cw, gy + gh + 2 * s + 12, "minutes left", size=s, fill="ink3",
               anchor="middle")
    d.text(origins[0][0] - (30 if layout == "wide" else 28), H - 14 if layout == "wide" else H - 40,
           f"Rows: lead in points. Boxed: up {a} to {b} entering the fourth.",
           size=s, fill="ink3")
    if layout == "narrow":
        d.text(origins[0][0] - 28, H - 20, "Red line: the 1% safe lead.", size=s, fill="ink3")
    else:
        d.text(origins[0][0] - 30, H - 34,
               f"Red line: the smallest lead lost {pct(th[0], 0)} of the time or less.",
               size=s, fill="ink3")
    return d


BUILDERS = {"dg1_reading_a_game": dg_game, "dg2_sigma_fan": dg_fan,
            "dg3_comeback_grid": dg_grid}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    fails = []
    for ref, build in BUILDERS.items():
        wide, narrow = build("wide"), build("narrow")
        if args.check:
            for dg, name in ((wide, f"{ref}.svg"), (narrow, f"{ref}_narrow.svg")):
                p = FIG / name
                if not p.exists() or p.read_text() != dg.svg():
                    fails.append(name)
        else:
            for p in fd.save(FIG, ref, wide, narrow):
                print("wrote", p.relative_to(lib.ROOT))
    if args.check:
        for f in fails:
            print("FAIL", f, "differs from a fresh build")
        print("DIAGRAMS", "FAILED" if fails else f"PASSED: {len(BUILDERS)} diagrams")
        return 1 if fails else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
