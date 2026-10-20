"""Game states at every checkpoint, for every regular-season game whose final
score matches LeagueGameLog.

Reads the family's shared PlayByPlayV3 layer (basketball-analysis-tools
pbp_history.py; events under ../.pbp-archive/, built there with
`python pbp_history.py build`). Checkpoint, lead, and comeback are defined in
python/lib.py.

Writes data/checkpoints.parquet (local: one row per game and checkpoint) and
output/coverage.csv (committed: games used and left out, per league-season,
with the reason). --check rebuilds in memory and fails if coverage.csv or the
checkpoint table's per-season summary differs, or if any season loses more
than 5% of its games.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

CHECKPOINTS = lib.ROOT / "data" / "checkpoints.parquet"
COVERAGE = lib.ROOT / "output" / "coverage.csv"
SUMMARY = lib.ROOT / "output" / "checkpoint_summary.csv"


def build() -> tuple[pl.DataFrame, pl.DataFrame]:
    cps, cov = [], []
    for league, years in lib.YEARS.items():
        for y in years:
            ev = pl.read_parquet(lib.pbp_history.events_path(league, y),
                                 columns=["gameId", "period", "secs_left", "seq",
                                          "score_h", "score_a"])
            fin = lib.pbp_history.load_finals(league, [y])
            c = lib.checkpoints(ev, fin, league, y)
            cps.append(c.with_columns(league=pl.lit(league), year=pl.lit(y, pl.Int32),
                                      era=pl.lit(lib.era_of(league, y))))
            counts = dict(fin.group_by("status").len().iter_rows())
            cov.append({"league": league, "year": y,
                        "season": lib.pbp_history.season_label(league, y),
                        "games_used": counts.get("ok", 0),
                        "final_mismatch": counts.get("score", 0),
                        "stamp_jump": counts.get("jump", 0),
                        "no_events": counts.get("no_events", 0),
                        "no_gamelog": counts.get("no_gamelog", 0)})
    return pl.concat(cps), pl.DataFrame(cov)


def summary(cps: pl.DataFrame) -> pl.DataFrame:
    return (cps.group_by("league", "year").agg(
                games=pl.col("gameId").n_unique(), checkpoints=pl.len(),
                comebacks=pl.col("comeback").sum(), mean_lead=pl.col("lead").mean().round(6))
            .sort("league", "year"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    cps, cov = build()
    summ = summary(cps)
    bad = cov.with_columns(lost=1 - pl.col("games_used") / (
        pl.col("games_used") + pl.col("final_mismatch") + pl.col("stamp_jump")
        + pl.col("no_events") + pl.col("no_gamelog"))
    ).filter(pl.col("lost") > 0.05)
    if args.check:
        fails = []
        if not lib.frames_match(cov, pl.read_csv(COVERAGE)):
            fails.append("coverage.csv differs from a fresh build")
        if not lib.frames_match(summ, pl.read_csv(SUMMARY, schema_overrides=summ.schema)):
            fails.append("checkpoint_summary.csv differs from a fresh build")
        if bad.height:
            fails.append(f"seasons losing over 5% of games: {bad.select('league', 'year').rows()}")
        for f in fails:
            print("FAIL", f)
        print("CHECKPOINTS", "FAILED" if fails else
              f"PASSED: {cov['games_used'].sum():,} games, {cps.height:,} checkpoints")
        return 1 if fails else 0
    CHECKPOINTS.parent.mkdir(exist_ok=True)
    cps.write_parquet(CHECKPOINTS)
    cov.write_csv(COVERAGE)
    summ.write_csv(SUMMARY)
    print(cov.group_by("league").agg(pl.col("games_used", "final_mismatch", "stamp_jump",
                                            "no_events", "no_gamelog").sum()))
    print(f"{cps.height:,} checkpoints; seasons losing over 5%: {bad.select('league', 'year').rows()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
