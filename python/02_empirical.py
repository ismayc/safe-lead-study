"""Tier 1: empirical comeback rates and safe leads, by league, era, and
checkpoint.

For each (league, era, T) the comeback rate at each lead is k / n (k of n
checkpoints won by the trailing team). Rates are smoothed with PAVA so they
never rise as the lead grows (python/lib.py), and each PAVA block gets a
Wilson 95% interval from its pooled counts.

Safe lead at threshold q: the smallest lead from which every larger observed
lead has a smoothed comeback rate at or below q. Two bounds go with it, read
off the same blocks: safe_lead_hi uses the Wilson upper bound (a lead safe
even at the pessimistic end of the interval) and safe_lead_lo the lower bound.
They are an approximate range, not a confidence interval for the safe lead.

Writes (committed, aggregate only):
  output/comeback_counts.csv   league, era, T, lead, n, k, rate, fit, block_n,
                               block_k, lo, hi
  output/safe_leads.csv        league, era, T, q, safe_lead, safe_lead_lo,
                               safe_lead_hi, n_games
  output/situations.csv        league, situation, era, n, k, rate, lo, hi: the
                               comeback rate in each standard situation
                               (lib.SITUATIONS) with its Wilson interval
  output/situation_change.csv  league, situation, first and last era, the
                               change in comeback rate (last minus first) and
                               its Newcombe interval, plain and
                               Bonferroni-adjusted for the 12 comparisons
--check recomputes all four from data/checkpoints.parquet and fails on any
difference, or if a smoothed rate rises with lead.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

COUNTS = lib.ROOT / "output" / "comeback_counts.csv"
SAFE = lib.ROOT / "output" / "safe_leads.csv"
SIT = lib.ROOT / "output" / "situations.csv"
CHANGE = lib.ROOT / "output" / "situation_change.csv"


def situations(cps: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    rows, change = [], []
    for name, t_nba, t_wnba, a, b in lib.SITUATIONS:
        for league, T in (("nba", t_nba), ("wnba", t_wnba)):
            x = (cps.filter((pl.col("league") == league) & (pl.col("T") == T)
                            & pl.col("lead").is_between(a, b))
                    .group_by("era").agg(n=pl.len(), k=pl.col("comeback").sum()).sort("era"))
            for r in x.iter_rows(named=True):
                lo, hi = lib.wilson(r["k"], r["n"])
                rows.append({"league": league, "situation": name, "era": r["era"], "n": r["n"],
                             "k": r["k"], "rate": r["k"] / r["n"], "lo": lo, "hi": hi})
            f, l = x.row(0, named=True), x.row(-1, named=True)
            d, dlo, dhi = lib.newcombe(l["k"], l["n"], f["k"], f["n"])
            _, alo, ahi = lib.newcombe(l["k"], l["n"], f["k"], f["n"], lib.Z_BONF12)
            change.append({"league": league, "situation": name, "first_era": f["era"],
                           "last_era": l["era"], "first_rate": f["k"] / f["n"],
                           "last_rate": l["k"] / l["n"], "change": d, "change_lo": dlo,
                           "change_hi": dhi,
                           "change_lo_adj": alo, "change_hi_adj": ahi})
    r12 = lambda df: df.with_columns(pl.col(pl.Float64).round(12))  # noqa: E731
    return r12(pl.DataFrame(rows)), r12(pl.DataFrame(change))


def compute(cps: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    counts = (cps.group_by("league", "era", "T", "lead")
                 .agg(n=pl.len(), k=pl.col("comeback").sum())
                 .sort("league", "era", "T", "lead"))
    games = cps.group_by("league", "era").agg(n_games=pl.col("gameId").n_unique())
    smoothed, safe = [], []
    for (league, era, T), cell in counts.group_by("league", "era", "T", maintain_order=True):
        s = lib.smooth_cell(cell)
        smoothed.append(s)
        leads = s["lead"].to_list()
        for q in lib.THRESHOLDS:
            safe.append({"league": league, "era": era, "T": T, "q": q,
                         "safe_lead": lib.safe_lead(leads, s["fit"].to_list(), q),
                         "safe_lead_lo": lib.safe_lead(leads, s["lo"].to_list(), q),
                         "safe_lead_hi": lib.safe_lead(leads, s["hi"].to_list(), q)})
    sm = pl.concat(smoothed).with_columns(pl.col("rate", "fit", "lo", "hi").round(12))
    sf = (pl.DataFrame(safe, schema={"league": pl.Utf8, "era": pl.Utf8, "T": pl.Int32,
                                     "q": pl.Float64, "safe_lead": pl.Int64,
                                     "safe_lead_lo": pl.Int64, "safe_lead_hi": pl.Int64})
            .join(games, on=["league", "era"]).sort("league", "era", "T", "q"))
    return sm, sf


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    cps = pl.read_parquet(lib.ROOT / "data" / "checkpoints.parquet")
    sm, sf = compute(cps)
    st, ch = situations(cps)
    rises = (sm.with_columns(prev=pl.col("fit").shift(1).over("league", "era", "T"))
               .filter(pl.col("fit") > pl.col("prev") + 1e-12))
    if args.check:
        fails = []
        old = pl.read_csv(COUNTS, schema_overrides=sm.schema)
        if not sm.equals(old):
            fails.append("comeback_counts.csv differs from a fresh build")
        if not sf.equals(pl.read_csv(SAFE, schema_overrides=sf.schema)):
            fails.append("safe_leads.csv differs from a fresh build")
        for name, df, path in (("situations.csv", st, SIT), ("situation_change.csv", ch, CHANGE)):
            if not df.equals(pl.read_csv(path, schema_overrides=df.schema)):
                fails.append(f"{name} differs from a fresh build")
        if rises.height:
            fails.append(f"{rises.height} smoothed rates rise with lead")
        for f in fails:
            print("FAIL", f)
        print("EMPIRICAL", "FAILED" if fails else
              f"PASSED: {sm.height:,} cells, {sf.height:,} safe leads")
        return 1 if fails else 0
    sm.write_csv(COUNTS)
    sf.write_csv(SAFE)
    st.write_csv(SIT)
    ch.write_csv(CHANGE)
    with pl.Config(tbl_rows=200, tbl_width_chars=200):
        print(ch)
    return 0


if __name__ == "__main__":
    sys.exit(main())
