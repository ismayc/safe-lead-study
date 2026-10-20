"""Write the README's results section from the output tables, so no number in
it is typed by hand. Replaces the text between <!-- gen:results --> and
<!-- /gen:results -->. --check fails if the README is out of date.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
README = ROOT / "README.md"
START, END = "<!-- gen:results -->", "<!-- /gen:results -->"
LEAGUE = {"nba": "NBA", "wnba": "WNBA"}
Q4 = {"nba": 720, "wnba": 600}


def pct(x: float, digits: int = 1) -> str:
    return f"{100 * x:.{digits}f}%"


def pts(x: float) -> str:
    return f"{100 * x:+.1f}"


def mmss(T: int) -> str:
    return f"{T // 60}:{T % 60:02d}"


def results() -> str:
    cov = pl.read_csv(OUT / "coverage.csv")
    sit = pl.read_csv(OUT / "situations.csv")
    chg = pl.read_csv(OUT / "situation_change.csv")
    fits = pl.read_csv(OUT / "brownian_fits.csv")
    safe = pl.read_csv(OUT / "safe_leads.csv", null_values=[""])
    bsafe = pl.read_csv(OUT / "brownian_safe_leads.csv")
    cal = pl.read_csv(OUT / "brownian_calibration.csv")

    used = cov.group_by("league").agg(pl.col("games_used").sum(),
                                      out=pl.sum_horizontal("final_mismatch", "stamp_jump",
                                                            "no_events", "no_gamelog").sum())
    u = {r["league"]: r for r in used.iter_rows(named=True)}
    seasons = {lg: cov.filter(pl.col("league") == lg)["season"].to_list() for lg in LEAGUE}
    lines = [
        f"Coverage: {u['nba']['games_used']:,} NBA games ({seasons['nba'][0]} to "
        f"{seasons['nba'][-1]}) and {u['wnba']['games_used']:,} WNBA games "
        f"({seasons['wnba'][0]} to {seasons['wnba'][-1]}), every regular-season game whose "
        "final score matches LeagueGameLog and whose running score never jumps by more than "
        f"one basket; {u['nba']['out']} NBA and {u['wnba']['out']} WNBA games fail those "
        "checks and are left out (per season in `output/coverage.csv`). Every table below "
        "is computed twice, in Python and in R from the same events, and the two agree on "
        "every cell (`python/04_reconcile.py`).",
        "",
        "### 1. How often a fixed lead is lost, then and now",
        "",
        "Share of games the trailing team won, first five-season era against the last, "
        "with the change in percentage points and its 95% Newcombe interval (in brackets: "
        "Bonferroni-adjusted for all 12 comparisons):",
        "",
        "| Situation | League | First era | Last era | Change (points) |",
        "|---|---|---|---|---|",
    ]
    for r in chg.iter_rows(named=True):
        lines.append(
            f"| {r['situation']} | {LEAGUE[r['league']]} | {pct(r['first_rate'])} | "
            f"{pct(r['last_rate'])} | {pts(r['change'])} ({pts(r['change_lo'])} to "
            f"{pts(r['change_hi'])}) [{pts(r['change_lo_adj'])} to {pts(r['change_hi_adj'])}] |")
    nba = chg.filter(pl.col("league") == "nba")
    plain = nba.filter(pl.col("change_lo") > 0)["situation"].to_list()
    adj = nba.filter(pl.col("change_lo_adj") > 0)["situation"].to_list()
    wn = chg.filter((pl.col("league") == "wnba") & (pl.col("change_lo") > 0)).height
    q4 = sit.filter((pl.col("situation") == "start of Q4, up 10-14") & (pl.col("league") == "nba")).sort("era")
    steps = q4["rate"].diff().to_list()[1:]
    big = max(range(len(steps)), key=lambda i: steps[i]) + 1
    size = (sit.filter(pl.col("league") == "wnba")["n"].sum()
            / sit.filter(pl.col("league") == "nba")["n"].sum())
    lines += [
        "",
        f"In the NBA, {len(plain)} of 6 situations show a rise whose interval excludes zero "
        f"({'; '.join(plain)}); after the adjustment, {len(adj)} remains"
        f"{'' if len(adj) == 1 else 's'} ({'; '.join(adj)}). A 10 to 14 point lead entering "
        f"the fourth quarter was lost {pct(q4['rate'][0])} of the time in {q4['era'][0]} and "
        f"{pct(q4['rate'][-1])} in {q4['era'][-1]}; the largest step between neighboring eras "
        f"is into {q4['era'][big]} ({pct(q4['rate'][big - 1])} to {pct(q4['rate'][big])}). "
        f"In the WNBA, {wn} of 6 situations show a change whose interval excludes zero; its "
        f"samples in these situations are {size:.0%} the size of the NBA's, so changes as "
        "large as the NBA's cannot be ruled out either.",
        "",
        "![Comebacks from 10-14 entering the fourth quarter](figures/fig1_q4_comebacks_py.png)",
        "",
        "### 2. Safe leads (comeback under 1%)",
        "",
        "Observed (PAVA-smoothed) 1% safe lead, with the range from the Wilson bounds of its "
        "PAVA block; \"n/c\" means the games at that lead are too few to certify 1% even at "
        "zero comebacks (the upper bound never falls below 1%):",
        "",
    ]
    for lg in LEAGUE:
        times = [Q4[lg], 360, 180, 60, 30]
        lines += [f"**{LEAGUE[lg]}**", "",
                  "| Era | " + " | ".join(f"{mmss(t)} left" for t in times) + " |",
                  "|---|" + "---|" * len(times)]
        s = safe.filter((pl.col("league") == lg) & (pl.col("q") == 0.01))
        for era in sorted(s["era"].unique().to_list()):
            cells = []
            for t in times:
                r = s.filter((pl.col("era") == era) & (pl.col("T") == t)).row(0, named=True)
                hi = "n/c" if r["safe_lead_hi"] is None else r["safe_lead_hi"]
                cells.append(f"{r['safe_lead']} ({r['safe_lead_lo']} to {hi})")
            lines.append(f"| {era} | " + " | ".join(cells) + " |")
        lines.append("")
    lines += [
        "Single cells are noisy (a lead safe at 6:00 can read lower than at 3:00), because "
        "the 1% tail rests on a few hundred games per cell; the era comparison in section 1 "
        "uses the far denser middle of the distribution for that reason.",
        "",
        "![1% safe lead by time left](figures/fig3_safe_lead_curve_py.png)",
        "",
        "### 3. The Brownian-motion model, and where it fails",
        "",
        "Fitted margin volatility, sigma, in points per square-root minute (95% interval, "
        "game-clustered), and the model's 1% safe lead at the start of the fourth quarter:",
        "",
        "| League | Era | sigma | 1% safe lead at the start of Q4 |",
        "|---|---|---|---|",
    ]
    for r in fits.filter(pl.col("unit") == "era").sort("league", "label").iter_rows(named=True):
        b = bsafe.filter((pl.col("league") == r["league"]) & (pl.col("era") == r["label"])
                         & (pl.col("q") == 0.01) & (pl.col("T") == Q4[r["league"]])).row(0, named=True)
        lines.append(f"| {LEAGUE[r['league']]} | {r['label']} | {r['sigma']:.2f} "
                     f"({r['sigma_lo']:.2f} to {r['sigma_hi']:.2f}) | {b['safe_lead']:.1f} "
                     f"({b['safe_lead_lo']:.1f} to {b['safe_lead_hi']:.1f}) |")
    pooled = (cal.group_by("league", "t_band", "lead_band")
                 .agg(n=pl.col("n").sum(), obs=(pl.col("observed") * pl.col("n")).sum(),
                      pred=(pl.col("predicted") * pl.col("n")).sum())
                 .with_columns(obs=pl.col("obs") / pl.col("n"), pred=pl.col("pred") / pl.col("n")))
    late = pooled.filter((pl.col("league") == "nba") & (pl.col("t_band") == "0-60s")
                         & (pl.col("lead_band") == "7-10")).row(0, named=True)
    mid = pooled.filter((pl.col("league") == "nba") & (pl.col("t_band") == "360-720s")
                        & (pl.col("lead_band") == "16+")).row(0, named=True)
    nf = fits.filter((pl.col("league") == "nba") & (pl.col("unit") == "era")).sort("label")
    wf = fits.filter((pl.col("league") == "wnba") & (pl.col("unit") == "era")).sort("label")

    def overlap(f: pl.DataFrame) -> str:
        apart = f["sigma_hi"][0] < f["sigma_lo"][-1] or f["sigma_hi"][-1] < f["sigma_lo"][0]
        return "do not overlap" if apart else "overlap"
    lines += [
        "",
        f"NBA sigma went from {nf['sigma'][0]:.2f} to {nf['sigma'][-1]:.2f}, and the "
        f"intervals of the first and last eras {overlap(nf)}; in the WNBA "
        f"({wf['sigma'][0]:.2f} to {wf['sigma'][-1]:.2f}) they {overlap(wf)}. The model is a smooth summary, not a calculator for the endgame. In "
        "the NBA's last minute, leads of 7 to 10 are overturned "
        f"{pct(late['obs'], 2)} of the time against the model's {pct(late['pred'], 2)} "
        f"({late['obs'] / late['pred']:.1f} times as often): fouling, threes, and timeouts "
        "add variance a constant-rate model has no room for. With 6 to 12 minutes left, "
        f"leads of 16 or more are overturned {pct(mid['obs'], 2)} against "
        f"{pct(mid['pred'], 2)} predicted: big leads belong disproportionately to better "
        "teams, which a model with no drift ignores (an interpretation, not tested here). "
        "Full calibration table: `output/brownian_calibration.csv`.",
        "",
        "![sigma by season](figures/fig2_sigma_by_season_py.png)",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    text = README.read_text()
    a, b = text.index(START) + len(START), text.index(END)
    new = text[:a] + "\n" + results() + "\n" + text[b:]
    if args.check:
        ok = new == text
        print("REPORT", "PASSED: README results match the outputs" if ok else
              "FAILED: README results are stale; run python/06_report.py")
        return 0 if ok else 1
    README.write_text(new)
    print("README results written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
