"""One illustrative game for the page's "how a game is read" diagram: a raw
extract of a single game's score margin, not a statistic, so it has no R
twin.

Selection rule (fixed in code, no game id typed): among NBA games in the
last era, the ones where a team led by the middle lead of the "start of Q4,
up 10-14" situation (lib.SITUATIONS) at that situation's checkpoint and the
trailing team won in regulation (the other team leads at the last
checkpoint); the most recent of them by game date, then by gameId.

Writes output/example_game.csv (committed, one game only): gameId,
game_date, leader and trailer (team abbreviations, by who led entering the
fourth quarter), their final scores, kind ("event": every row where the
regulation margin changes, plus the tip and the end of regulation;
"checkpoint": the study's checkpoints with a leader, from lib.checkpoints),
T (seconds of regulation left), and margin (the fourth-quarter leader's
points minus the trailer's). --check rebuilds it and fails on any
difference.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

OUT = lib.ROOT / "output" / "example_game.csv"
SITUATION = "start of Q4, up 10-14"
LEAGUE = "nba"


def build() -> pl.DataFrame:
    _, T, _, a, b = next(s for s in lib.SITUATIONS if s[0] == SITUATION)
    lead = (a + b) // 2
    year = lib.YEARS[LEAGUE][-1]
    era = lib.era_of(LEAGUE, year)
    cps = pl.read_parquet(lib.ROOT / "data" / "checkpoints.parquet").filter(
        (pl.col("league") == LEAGUE) & (pl.col("era") == era))
    at_q4 = cps.filter((pl.col("T") == T) & (pl.col("lead") == lead) & (pl.col("comeback") == 1))
    last_t = min(lib.grid(4 * 720))
    at_end = cps.filter(pl.col("T") == last_t).select("gameId", end_home=pl.col("leader_home"))
    cand = at_q4.join(at_end, on="gameId").filter(pl.col("end_home") != pl.col("leader_home"))
    years = sorted(cand["year"].unique().to_list())
    fin = lib.pbp_history.load_finals(LEAGUE, years)
    pick = (cand.join(fin.select("gameId", "game_date", "abbr_h", "abbr_a", "gl_h", "gl_a"),
                      on="gameId")
                .sort("game_date", "gameId").row(-1, named=True))
    gid, yr, home = pick["gameId"], pick["year"], pick["leader_home"]
    sign = 1 if home else -1
    nper, plen = lib.regulation(LEAGUE, yr)
    total = nper * plen
    ev = pl.read_parquet(lib.pbp_history.events_path(LEAGUE, yr),
                         columns=["gameId", "period", "secs_left", "seq", "score_h", "score_a"]
                         ).filter(pl.col("gameId") == gid)
    e = (ev.filter(pl.col("period") <= nper)
           .with_columns(el=lib.elapsed_expr(nper, plen),
                         margin=sign * (pl.col("score_h") - pl.col("score_a")))
           .sort("el", "seq")
           .group_by("el", maintain_order=True).agg(pl.col("margin").last()))
    e = pl.concat([pl.DataFrame({"el": [0.0], "margin": [0]}, schema=e.schema), e])
    keep = e.filter((pl.col("margin") != pl.col("margin").shift(1)) | (pl.col("el") == 0))
    end = e.tail(1).with_columns(el=pl.lit(float(total)))
    events = pl.concat([keep, end]).unique("el", keep="last", maintain_order=True).sort("el")
    events = events.select(kind=pl.lit("event"), T=(total - pl.col("el")).cast(pl.Int32),
                           margin=pl.col("margin").cast(pl.Int32))
    fins = fin.filter(pl.col("gameId") == gid)
    c = lib.checkpoints(ev, fins, LEAGUE, yr).select(
        kind=pl.lit("checkpoint"), T=pl.col("T").cast(pl.Int32),
        margin=(pl.when(pl.col("leader_home") == home).then(1).otherwise(-1)
                * pl.col("lead")).cast(pl.Int32))
    lead_abbr, trail_abbr = (pick["abbr_h"], pick["abbr_a"]) if home else (pick["abbr_a"], pick["abbr_h"])
    lead_pts, trail_pts = (pick["gl_h"], pick["gl_a"]) if home else (pick["gl_a"], pick["gl_h"])
    return pl.concat([events, c.sort("T", descending=True)]).select(
        gameId=pl.lit(gid), game_date=pl.lit(str(pick["game_date"])),
        leader=pl.lit(lead_abbr), trailer=pl.lit(trail_abbr),
        leader_final=pl.lit(lead_pts), trailer_final=pl.lit(trail_pts),
        kind="kind", T="T", margin="margin")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    df = build()
    if args.check:
        ok = lib.frames_match(df, pl.read_csv(OUT, schema_overrides=df.schema))
        print("EXAMPLE GAME", "PASSED" if ok else "FAILED: example_game.csv differs from a fresh build")
        return 0 if ok else 1
    df.write_csv(OUT)
    r = df.row(0, named=True)
    print(f"{r['gameId']} {r['game_date']}: {r['leader']} led entering Q4, "
          f"{r['trailer']} won {r['trailer_final']}-{r['leader_final']}; {df.height} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
