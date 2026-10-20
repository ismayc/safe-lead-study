"""Tier 2: Stern's Brownian-motion model of the score margin, by era and by
season.

Model (Stern 1994, "A Brownian motion model for the progress of sports
scores", JASA 89:1128-1134), with no drift because the calculator is for an
unknown pair of teams: the leader wins with probability
Phi(lead / (sigma * sqrt(T / 60))), T in seconds of regulation left. sigma is
the margin's standard deviation per square-root minute. It is fitted as a
probit with one slope (beta = 1 / sigma) on x = lead / sqrt(T / 60), over
every checkpoint with a leader, with a game-clustered standard error
(python/lib.py).

Safe lead at threshold q: z_(1-q) * sigma * sqrt(T / 60). Its range uses
sigma at beta -/+ 1.96 standard errors.

Calibration: observed against predicted comeback rates by band of time left
and lead, so the README can say where the model's square-root-of-time
scaling holds and where it does not.

Fourth-quarter fan: for each era, the model's comeback chance for the
middle lead of the "start of Q4, up 10-14" situation (lib.SITUATIONS) at the
start of the fourth quarter, Phi(-lead / (sigma * sqrt(T / 60))), with its
range from sigma_lo and sigma_hi. The page's fan diagram draws it.

Writes (committed): output/brownian_fits.csv (league, unit, label, beta, se,
sigma, sigma_lo, sigma_hi, n_checkpoints, n_games, iterations; unit is era or
season), output/brownian_safe_leads.csv, output/brownian_calibration.csv,
output/brownian_q4_fan.csv (league, era, T, lead, sigma, p_comeback,
p_comeback_lo, p_comeback_hi). --check recomputes all four and fails on any difference.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

FITS = lib.ROOT / "output" / "brownian_fits.csv"
SAFE = lib.ROOT / "output" / "brownian_safe_leads.csv"
CALIB = lib.ROOT / "output" / "brownian_calibration.csv"
FAN = lib.ROOT / "output" / "brownian_q4_fan.csv"
POOLED = lib.ROOT / "output" / "brownian_calibration_pooled.csv"
FAN_SITUATION = "start of Q4, up 10-14"

T_BANDS = [(0, 60), (60, 180), (180, 360), (360, 720), (720, 1440), (1440, 2880)]
LEAD_BANDS = [(1, 3), (4, 6), (7, 10), (11, 15), (16, 99)]
REPORT_T = [30, 60, 120, 180, 360, 600, 720, 1200, 1440]


def fit(sub: pl.DataFrame) -> dict:
    cells = (sub.group_by("T", "lead").agg(n=pl.len(), k=(1 - pl.col("comeback")).sum())
                .sort("T", "lead"))
    x = (cells["lead"] / (cells["T"] / 60).sqrt()).to_numpy()
    beta, it = lib.probit_slope(x, cells["n"].to_numpy().astype(float),
                                cells["k"].to_numpy().astype(float))
    xo = (sub["lead"] / (sub["T"] / 60).sqrt()).to_numpy()
    yo = (1 - sub["comeback"]).to_numpy().astype(float)
    codes = sub["gameId"].cast(pl.Categorical).to_physical().to_numpy().astype(np.int64)
    se = lib.cluster_se(beta, xo, yo, codes)
    return {"beta": beta, "se": se, "sigma": 1 / beta,
            "sigma_lo": 1 / (beta + lib.Z95 * se), "sigma_hi": 1 / (beta - lib.Z95 * se),
            "n_checkpoints": sub.height, "n_games": sub["gameId"].n_unique(),
            "iterations": it}


def compute(cps: pl.DataFrame):
    rows = []
    for (league, era), sub in cps.group_by("league", "era", maintain_order=True):
        rows.append({"league": league, "unit": "era", "label": era, **fit(sub)})
    for (league, year), sub in cps.group_by("league", "year", maintain_order=True):
        rows.append({"league": league, "unit": "season",
                     "label": lib.pbp_history.season_label(league, year), **fit(sub)})
    fits = pl.DataFrame(rows).sort("league", "unit", "label")
    safe = []
    for r in fits.filter(pl.col("unit") == "era").iter_rows(named=True):
        for T in REPORT_T:
            for q in lib.THRESHOLDS:
                safe.append({"league": r["league"], "era": r["label"], "T": T, "q": q,
                             "safe_lead": lib.brownian_safe_lead(r["sigma"], T, q),
                             "safe_lead_lo": lib.brownian_safe_lead(r["sigma_lo"], T, q),
                             "safe_lead_hi": lib.brownian_safe_lead(r["sigma_hi"], T, q)})
    safe = pl.DataFrame(safe)
    sig = fits.filter(pl.col("unit") == "era").select(
        "league", pl.col("label").alias("era"), "sigma")
    c = cps.join(sig, on=["league", "era"])
    z = (c["lead"] / (c["sigma"] * (c["T"] / 60).sqrt())).to_numpy()
    c = c.with_columns(pred=pl.Series(lib.ndtr(-z)))
    tb = pl.lit(None, pl.Utf8)
    for a, b in T_BANDS:
        tb = pl.when((pl.col("T") > a) & (pl.col("T") <= b)).then(pl.lit(f"{a}-{b}s")).otherwise(tb)
    lb = pl.lit(None, pl.Utf8)
    for a, b in LEAD_BANDS:
        lb = pl.when((pl.col("lead") >= a) & (pl.col("lead") <= b)).then(
            pl.lit(f"{a}-{b}" if b < 99 else f"{a}+")).otherwise(lb)
    calib = (c.with_columns(t_band=tb, lead_band=lb)
              .group_by("league", "era", "t_band", "lead_band")
              .agg(n=pl.len(), observed=pl.col("comeback").mean(), predicted=pl.col("pred").mean())
              .sort("league", "era", "t_band", "lead_band"))
    _, t_nba, t_wnba, a, b = next(s for s in lib.SITUATIONS if s[0] == FAN_SITUATION)
    lead = (a + b) / 2
    fan = []
    for r in fits.filter(pl.col("unit") == "era").iter_rows(named=True):
        T = t_nba if r["league"] == "nba" else t_wnba
        p = lambda sg: float(lib.ndtr(-lead / (sg * (T / 60) ** 0.5)))  # noqa: E731
        fan.append({"league": r["league"], "era": r["label"], "T": T, "lead": lead,
                    "sigma": r["sigma"], "p_comeback": p(r["sigma"]),
                    "p_comeback_lo": p(r["sigma_lo"]), "p_comeback_hi": p(r["sigma_hi"])})
    fan = pl.DataFrame(fan)
    rnd = lambda df, cols: df.with_columns(pl.col(cols).round(10))  # noqa: E731
    return (rnd(fits, ["beta", "se", "sigma", "sigma_lo", "sigma_hi"]),
            rnd(safe, ["safe_lead", "safe_lead_lo", "safe_lead_hi"]),
            rnd(calib, ["observed", "predicted"]),
            rnd(fan, ["sigma", "p_comeback", "p_comeback_lo", "p_comeback_hi"]))


def pool_calibration(calib: pl.DataFrame) -> pl.DataFrame:
    """Calibration with all eras pooled: each era's observed and predicted
    rate weighted by its checkpoints (the story's late-game and big-lead
    comparisons quote these)."""
    return (calib.group_by("league", "t_band", "lead_band")
                 .agg(n=pl.col("n").sum(), obs=(pl.col("observed") * pl.col("n")).sum(),
                      pred=(pl.col("predicted") * pl.col("n")).sum())
                 .with_columns(observed=(pl.col("obs") / pl.col("n")).round(10),
                               predicted=(pl.col("pred") / pl.col("n")).round(10))
                 .select("league", "t_band", "lead_band", "n", "observed", "predicted")
                 .sort("league", "t_band", "lead_band"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    cps = pl.read_parquet(lib.ROOT / "data" / "checkpoints.parquet")
    fits, safe, calib, fan = compute(cps)
    pooled = pool_calibration(calib)
    if args.check:
        fails = [name for name, df, path in [("brownian_fits.csv", fits, FITS),
                                             ("brownian_safe_leads.csv", safe, SAFE),
                                             ("brownian_calibration.csv", calib, CALIB),
                                             ("brownian_q4_fan.csv", fan, FAN),
                                             ("brownian_calibration_pooled.csv", pooled, POOLED)]
                 if not lib.frames_match(df, pl.read_csv(path, schema_overrides=df.schema))]
        for f in fails:
            print("FAIL", f, "differs from a fresh build")
        print("BROWNIAN", "FAILED" if fails else f"PASSED: {fits.height} fits")
        return 1 if fails else 0
    fits.write_csv(FITS)
    safe.write_csv(SAFE)
    calib.write_csv(CALIB)
    fan.write_csv(FAN)
    pooled.write_csv(POOLED)
    with pl.Config(tbl_rows=100, tbl_width_chars=200):
        print(fits.filter(pl.col("unit") == "era").drop("unit"))
        print(safe.filter((pl.col("q") == 0.01) & pl.col("T").is_in([60, 360, 720])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
