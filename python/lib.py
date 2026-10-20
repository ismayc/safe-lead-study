"""Shared definitions for the safe-lead study. Every function here has a twin
in R/functions.R, and tests/python and tests/R pin both to the same
hand-computed fixtures.

Checkpoints
-----------
A checkpoint is a moment in regulation, measured as seconds of regulation
left (T). The grid is every 5 seconds from 5 to 120, then every 30 seconds up
to the start of the game (exclusive). The lead at T is the score after every
event at or before that moment: an event at exactly T counts.

Regulation: NBA four 12-minute quarters (2,880 s). WNBA two 20-minute halves
through 2005 and four 10-minute quarters from 2006 (2,400 s either way).
Clock readings above a period's length (the 2006 WNBA period-start rows read
12:00) are clamped to it.

Comeback: the team trailing at T wins the game (overtime included). Ties at T
have no leader and are left out.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import polars as pl
from scipy.special import ndtr

ROOT = Path(__file__).resolve().parents[1]
FAMILY = ROOT.parent
sys.path.insert(0, str(FAMILY / "basketball-analysis-tools"))
import pbp_history  # noqa: E402

YEARS = {"nba": range(1996, 2026), "wnba": range(1997, 2027)}
ERA_LEN = 5
Z95 = 1.959963984540054
THRESHOLDS = [0.01, 0.05, 0.10]


def regulation(league: str, year: int) -> tuple[int, int]:
    """(regulation periods, seconds per period)."""
    if league == "nba":
        return 4, 720
    return (2, 1200) if year <= 2005 else (4, 600)


def grid(total: int) -> list[int]:
    return list(range(5, 121, 5)) + list(range(150, total, 30))


def era_of(league: str, year: int) -> str:
    first = YEARS[league].start
    a = first + (year - first) // ERA_LEN * ERA_LEN
    b = a + ERA_LEN - 1
    if league == "nba":
        return f"{a}-{(a + 1) % 100:02d} to {b}-{(b + 1) % 100:02d}"
    return f"{a} to {b}"


def elapsed_expr(nper: int, plen: int) -> pl.Expr:
    """Seconds of regulation played at an event (regulation periods only)."""
    left = pl.min_horizontal(pl.col("secs_left"), pl.lit(float(plen)))
    return (pl.col("period") - 1) * plen + (plen - left)


def checkpoints(ev: pl.DataFrame, finals: pl.DataFrame, league: str, year: int) -> pl.DataFrame:
    """One row per game and checkpoint with a leader: gameId, T, lead (> 0),
    leader_home, comeback (0/1). ev: prepared events; finals: the season's
    finals check (only status "ok" games are used)."""
    nper, plen = regulation(league, year)
    total = nper * plen
    ok = finals.filter(pl.col("status") == "ok").select(
        "gameId", home_won=(pl.col("gl_h") > pl.col("gl_a")))
    e = (ev.filter(pl.col("period") <= nper)
           .join(ok.select("gameId"), on="gameId", how="semi")
           .with_columns(el=elapsed_expr(nper, plen),
                         margin=pl.col("score_h") - pl.col("score_a"))
           .select("gameId", "el", "seq", "margin")
           .sort("gameId", "el", "seq"))
    # The last event at or before each checkpoint's moment. Elapsed times are
    # non-decreasing within a game because prepare() sorts by period, then
    # clock descending.
    e = e.group_by("gameId", "el", maintain_order=True).agg(pl.col("margin").last())
    cps = pl.DataFrame({"T": grid(total)}, schema={"T": pl.Int32}).with_columns(
        el=(total - pl.col("T")).cast(pl.Float64))
    games = ok.select("gameId")
    q = games.join(cps, how="cross").sort("gameId", "el")
    out = q.join_asof(e.sort("gameId", "el"), on="el", by="gameId", strategy="backward",
                      check_sortedness=False)
    out = out.with_columns(pl.col("margin").fill_null(0)).filter(pl.col("margin") != 0)
    out = out.join(ok, on="gameId").with_columns(
        lead=pl.col("margin").abs().cast(pl.Int32),
        leader_home=pl.col("margin") > 0)
    out = out.with_columns(comeback=(pl.col("leader_home") != pl.col("home_won")).cast(pl.Int32))
    return out.select("gameId", "T", "lead", "leader_home", "comeback").sort("gameId", "T")


def pava_nonincreasing(y: list[float], w: list[float]) -> list[float]:
    """Weighted least-squares fit of y that never increases left to right
    (pool adjacent violators). Blocks are merged whenever a later block's
    mean is at least an earlier one's. Merging equal means leaves the fit
    unchanged but pools their counts, so the run of zero-comeback leads at
    the top of each cell becomes one block with all its games (the Wilson
    bounds in smooth_cell depend on that)."""
    blocks: list[list[float]] = []  # [weighted sum, weight, count]
    for yi, wi in zip(y, w):
        blocks.append([yi * wi, wi, 1])
        while len(blocks) > 1 and blocks[-1][0] * blocks[-2][1] >= blocks[-2][0] * blocks[-1][1]:
            s, ww, c = blocks.pop()
            blocks[-1][0] += s
            blocks[-1][1] += ww
            blocks[-1][2] += c
    out: list[float] = []
    for s, ww, c in blocks:
        out.extend([s / ww] * int(c))
    return out


def pava_blocks(y: list[float], w: list[float]) -> list[int]:
    """Block index of each element in pava_nonincreasing's fit."""
    blocks: list[list[float]] = []
    for yi, wi in zip(y, w):
        blocks.append([yi * wi, wi, 1])
        while len(blocks) > 1 and blocks[-1][0] * blocks[-2][1] >= blocks[-2][0] * blocks[-1][1]:
            s, ww, c = blocks.pop()
            blocks[-1][0] += s
            blocks[-1][1] += ww
            blocks[-1][2] += c
    idx: list[int] = []
    for b, (_, _, c) in enumerate(blocks):
        idx.extend([b] * int(c))
    return idx


def wilson(k: float, n: float, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval for k successes in n trials."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def smooth_cell(counts: pl.DataFrame) -> pl.DataFrame:
    """counts: one (T) slice with lead, n, k for every observed lead, sorted
    by lead. Adds rate, fit (PAVA, nonincreasing in lead), block_n, block_k,
    and the block's Wilson interval (lo, hi)."""
    c = counts.sort("lead")
    n = c["n"].cast(pl.Float64).to_list()
    k = c["k"].cast(pl.Float64).to_list()
    rate = [ki / ni for ki, ni in zip(k, n)]
    fit = pava_nonincreasing(rate, n)
    blk = pava_blocks(rate, n)
    bn: dict[int, float] = {}
    bk: dict[int, float] = {}
    for b, ni, ki in zip(blk, n, k):
        bn[b] = bn.get(b, 0.0) + ni
        bk[b] = bk.get(b, 0.0) + ki
    lo, hi = zip(*[wilson(bk[b], bn[b]) for b in blk]) if blk else ((), ())
    return c.with_columns(
        rate=pl.Series(rate), fit=pl.Series(fit),
        block_n=pl.Series([bn[b] for b in blk]), block_k=pl.Series([bk[b] for b in blk]),
        lo=pl.Series(list(lo)), hi=pl.Series(list(hi)))


def newcombe(k1: float, n1: float, k2: float, n2: float, z: float = Z95) -> tuple[float, float, float]:
    """Difference p1 - p2 with Newcombe's hybrid score interval (method 10 in
    Newcombe 1998, Statistics in Medicine 17:873-890), built from the two
    Wilson intervals."""
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1, z)
    l2, u2 = wilson(k2, n2, z)
    d = p1 - p2
    return (d, d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2),
            d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2))


# Bonferroni z for the 12 era comparisons (6 situations x 2 leagues),
# two-sided 95%: qnorm(1 - 0.05 / 24).
Z_BONF12 = 2.8652602385321346

# Standard situations for the era comparison: (name, T for the NBA, T for the
# WNBA, lowest lead, highest lead). The NBA's fourth quarter starts at 720 s
# left, the WNBA's at 600 s (from 2006; 600 s left in a 1997-2005 half).
SITUATIONS = [
    ("halftime, up 10-14", 1440, 1200, 10, 14),
    ("start of Q4, up 10-14", 720, 600, 10, 14),
    ("start of Q4, up 15-19", 720, 600, 15, 19),
    ("6:00 left, up 10-14", 360, 360, 10, 14),
    ("3:00 left, up 7-9", 180, 180, 7, 9),
    ("1:00 left, up 5-6", 60, 60, 5, 6),
]


def safe_lead(leads: list[int], values: list[float], q: float) -> int | None:
    """Smallest lead L such that every observed lead >= L has value <= q.
    None when even the largest observed lead is above q."""
    best = None
    for L, v in sorted(zip(leads, values), reverse=True):
        if v <= q:
            best = L
        else:
            break
    return best


# Tier 2: Stern's Brownian-motion model. With no drift, the margin's change
# over the T seconds left is normal with variance sigma^2 * (T / 60), so the
# leader wins with probability Phi(lead / (sigma * sqrt(T / 60))). Fitting
# it is a probit with one slope, beta = 1 / sigma, and no intercept, on
# x = lead / sqrt(T / 60).

def _parts(beta: float, x: np.ndarray):
    eta = beta * x
    p = ndtr(eta)
    q = ndtr(-eta)
    d = np.exp(-0.5 * eta * eta) / math.sqrt(2 * math.pi)
    return p, q, d


def probit_slope(x: np.ndarray, n: np.ndarray, k: np.ndarray,
                 tol: float = 1e-12, max_iter: int = 100) -> tuple[float, int]:
    """Fisher-scoring fit of P(leader wins) = Phi(beta * x) on cells: x per
    cell, n checkpoints, k of them won by the leader. Returns (beta,
    iterations)."""
    # Start wide (sigma = 10 points per root minute); Fisher scoring then
    # moves monotonically toward the fit.
    beta = 0.1
    for it in range(1, max_iter + 1):
        p, q, d = _parts(beta, x)
        # Cells so far out that Phi rounds to 1 carry no information.
        m = (p * q) > 0
        xm, nm, km, p, q, d = x[m], n[m], k[m], p[m], q[m], d[m]
        score = float(np.sum(xm * d * (km - nm * p) / (p * q)))
        info = float(np.sum(nm * xm * xm * d * d / (p * q)))
        step = score / info
        beta += step
        if abs(step) < tol:
            return beta, it
    raise RuntimeError("probit did not converge")


def cluster_se(beta: float, x: np.ndarray, y: np.ndarray, game: np.ndarray) -> float:
    """Cluster-robust (sandwich) standard error of beta, with game-level score
    sums, because one game contributes many correlated checkpoints. Inputs
    are per checkpoint; game holds integer game codes."""
    p, q, d = _parts(beta, x)
    m = (p * q) > 0
    x, y, game, p, q, d = x[m], y[m], game[m], p[m], q[m], d[m]
    info = float(np.sum(x * x * d * d / (p * q)))
    s = np.bincount(game, weights=x * d * (y - p) / (p * q))
    return math.sqrt(float(np.sum(s * s))) / info


Z_ONE_SIDED = {0.01: 2.3263478740408408, 0.05: 1.6448536269514722, 0.10: 1.2815515655446004}


def brownian_safe_lead(sigma: float, T: float, q: float) -> float:
    """Lead at which the trailing team's win probability is q with T
    seconds left: z_(1-q) * sigma * sqrt(T / 60)."""
    return Z_ONE_SIDED[q] * sigma * math.sqrt(T / 60)
