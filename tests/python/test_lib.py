"""python/lib.py against hand-computed fixtures. tests/R/test_functions.R
asserts the same numbers for R/functions.R."""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import polars as pl
import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def lib():
    spec = importlib.util.spec_from_file_location("safe_lead_lib", REPO / "python" / "lib.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["safe_lead_lib"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_pava_pools_violators_and_ties(lib):
    # 0.6 > 0.5 pools to 0.55; the two 0.2s are equal and pool into one block.
    y, w = [0.5, 0.6, 0.2, 0.2, 0.1], [1, 1, 2, 2, 1]
    assert lib.pava_nonincreasing(y, w) == pytest.approx([0.55, 0.55, 0.2, 0.2, 0.1])
    assert lib.pava_blocks(y, w) == [0, 0, 1, 1, 2]


def test_pava_preserves_the_weighted_mean(lib):
    y, w = [0.1, 0.3, 0.2, 0.4, 0.0], [3, 1, 2, 5, 4]
    fit = lib.pava_nonincreasing(y, w)
    assert sum(f * wi for f, wi in zip(fit, w)) == pytest.approx(sum(a * b for a, b in zip(y, w)))
    assert all(a >= b - 1e-15 for a, b in zip(fit, fit[1:]))


def test_wilson(lib):
    lo, hi = lib.wilson(5, 100)
    assert (lo, hi) == pytest.approx((0.021543, 0.111750), abs=1e-6)
    # Zero events: the upper bound is z^2 / (n + z^2); 380 games are just
    # short of certifying 1%.
    z2 = lib.Z95 ** 2
    assert lib.wilson(0, 380)[1] == pytest.approx(z2 / (380 + z2))
    assert lib.wilson(0, 380)[1] > 0.01 > lib.wilson(0, 381)[1]


def test_safe_lead(lib):
    assert lib.safe_lead([1, 2, 3, 4], [0.3, 0.02, 0.005, 0.0], 0.01) == 3
    # A larger lead above q blocks every smaller one.
    assert lib.safe_lead([1, 2, 3, 4], [0.3, 0.005, 0.02, 0.0], 0.01) == 4
    assert lib.safe_lead([1, 2], [0.3, 0.2], 0.01) is None


def test_regulation_and_eras(lib):
    assert lib.regulation("wnba", 2005) == (2, 1200)
    assert lib.regulation("wnba", 2006) == (4, 600)
    assert lib.era_of("nba", 1996) == "1996-97 to 2000-01"
    assert lib.era_of("nba", 2001) == "2001-02 to 2005-06"
    assert lib.era_of("nba", 2025) == "2021-22 to 2025-26"
    assert lib.era_of("wnba", 2026) == "2022 to 2026"
    g = lib.grid(2880)
    assert g[:3] == [5, 10, 15] and 120 in g and 150 in g and g[-1] == 2850


def test_probit_recovers_an_exact_slope(lib):
    # Cells whose win counts are exactly n * Phi(0.5 x): the fit is 0.5.
    x = np.array([0.5, 1.0, 2.0, 3.0, 4.0])
    n = np.full(5, 1000.0)
    k = n * lib.ndtr(0.5 * x)
    beta, _ = lib.probit_slope(x, n, k)
    assert beta == pytest.approx(0.5, abs=1e-10)


def test_cluster_se_is_zero_for_one_cluster(lib):
    # At the fit the score sums to zero, so one cluster has no spread.
    x = np.array([0.5, 1.0, 1.0, 2.0, 3.0, 0.2])
    y = np.array([1.0, 0.0, 1.0, 1.0, 1.0, 0.0])
    beta, _ = lib.probit_slope(x, np.ones(6), y)
    assert lib.cluster_se(beta, x, y, np.zeros(6, dtype=np.int64)) == pytest.approx(0, abs=1e-10)
    assert lib.cluster_se(beta, x, y, np.arange(6)) > 0


def test_brownian_safe_lead(lib):
    # sigma 2 with 4 minutes left: 2.326 * 2 * 2.
    assert lib.brownian_safe_lead(2.0, 240, 0.01) == pytest.approx(4 * 2.3263478740408408)


def test_checkpoints_on_a_tiny_game(lib):
    # NBA game: home scores at 0:30 of Q4 (T = 30), away answers at 0:10.
    ev = pl.DataFrame({
        "gameId": ["g"] * 4, "period": [1, 4, 4, 4], "secs_left": [720.0, 30.0, 10.0, 0.0],
        "seq": [0, 1, 2, 3], "score_h": [0, 2, 2, 2], "score_a": [0, 0, 3, 3]})
    fin = pl.DataFrame({"gameId": ["g"], "status": ["ok"], "gl_h": [2], "gl_a": [3]})
    c = lib.checkpoints(ev, fin, "nba", 2020)
    # Tied before T = 30 (left out); home leads by 2 at T = 30 (the event at
    # exactly T counts), 25, 20, 15; away leads by 1 at T = 10 and 5.
    assert c.select("T", "lead", "leader_home", "comeback").rows() == [
        (5, 1, False, 0), (10, 1, False, 0), (15, 2, True, 1), (20, 2, True, 1),
        (25, 2, True, 1), (30, 2, True, 1)]


def test_checkpoints_skip_games_that_fail_the_finals_check(lib):
    ev = pl.DataFrame({"gameId": ["g"], "period": [1], "secs_left": [600.0], "seq": [0],
                       "score_h": [2], "score_a": [0]})
    fin = pl.DataFrame({"gameId": ["g"], "status": ["jump"], "gl_h": [2], "gl_a": [0]})
    assert lib.checkpoints(ev, fin, "nba", 2020).height == 0


def test_wnba_halves_elapsed(lib):
    # 2005: two 20-minute halves. A basket 5:00 into the second half is
    # 25 minutes played, so 15:00 (900 s) of regulation is left.
    ev = pl.DataFrame({"gameId": ["g", "g"], "period": [1, 2], "secs_left": [1200.0, 900.0],
                       "seq": [0, 1], "score_h": [0, 2], "score_a": [0, 0]})
    fin = pl.DataFrame({"gameId": ["g"], "status": ["ok"], "gl_h": [2], "gl_a": [0]})
    c = lib.checkpoints(ev, fin, "wnba", 2005)
    assert c["T"].max() == 900 and c["T"].min() == 5
    assert math.isclose(c.height, len([t for t in lib.grid(2400) if t <= 900]))


def test_newcombe_matches_the_published_example(lib):
    # Newcombe (1998), example (a): 56/70 vs 48/80, method 10: 0.0524 to 0.3339.
    d, lo, hi = lib.newcombe(56, 70, 48, 80)
    assert (d, lo, hi) == pytest.approx((0.2, 0.0524, 0.3339), abs=1e-4)
    # A wider z widens both ends.
    _, alo, ahi = lib.newcombe(56, 70, 48, 80, lib.Z_BONF12)
    assert alo < lo and ahi > hi
