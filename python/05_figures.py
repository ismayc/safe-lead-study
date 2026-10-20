"""Figures, from committed and R-reconciled outputs only (situations.csv,
brownian_fits.csv, safe_leads.csv, brownian_safe_leads.csv). Plotly
originals go to figures/; report_builder.py swaps in the family's famplot
engine at publish time, so only traces famplot draws are used (scatter lines
and markers, error bars).

Figures:
  fig1_q4_comebacks_py    comeback rate from 10-14 up at the start of the
                          fourth quarter, by era, with Wilson intervals
  fig2_sigma_by_season_py margin volatility (sigma) by season, with 95%
                          intervals
  fig3_safe_lead_curve_py 1% safe lead by time left, NBA first and last era:
                          empirical (PAVA) and Brownian

Run:  python python/05_figures.py
"""
from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go
import polars as pl

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
FIG = ROOT / "figures"
LEAGUES = {"nba": "NBA", "wnba": "WNBA"}
# famplot's first two family colors, the same as the other studies.
COLORS = {"nba": "#2a78d6", "wnba": "#eb6834"}
LIGHT = {"nba": "#8db8ea", "wnba": "#f3a77f"}


def base_layout(title: str, xtitle: str, ytitle: str, height: int = 420) -> dict:
    return dict(title=title, xaxis_title=xtitle, yaxis_title=ytitle, template="plotly_white",
                height=height, margin=dict(l=70, r=30, t=60, b=60),
                legend=dict(orientation="h", y=-0.2))


def era_short(era: str) -> str:
    """"1996-97 to 2000-01" -> "1996-97 to 00-01"; WNBA labels unchanged."""
    a, b = era.split(" to ")
    return f"{a} to {b[2:]}" if "-" in b else era


def fig_q4(sit: pl.DataFrame) -> go.Figure:
    f = go.Figure()
    s = sit.filter(pl.col("situation") == "start of Q4, up 10-14")
    for lg, name in LEAGUES.items():
        r = s.filter(pl.col("league") == lg).sort("era")
        y = (r["rate"] * 100).to_list()
        f.add_trace(go.Scatter(
            # Nudged apart so the two leagues' intervals do not overlap.
            x=[j + (-0.07 if lg == "nba" else 0.07) for j in range(1, r.height + 1)], y=y, mode="lines+markers", name=name,
            line=dict(color=COLORS[lg]), marker=dict(size=9, color=COLORS[lg]),
            error_y=dict(type="data", symmetric=False,
                         array=[(h - v) * 100 for h, v in zip(r["hi"], r["rate"])],
                         arrayminus=[(v - lo) * 100 for v, lo in zip(r["rate"], r["lo"])],
                         color=LIGHT[lg]),
            customdata=list(zip(r["era"].to_list(), r["k"].to_list(), r["n"].to_list())),
            hovertemplate=f"{name} %{{customdata[0]}}: %{{y:.1f}}% "
                          "(%{customdata[1]} of %{customdata[2]} games)<extra></extra>"))
    f.update_layout(**base_layout(
        "Up 10 to 14 entering the fourth quarter: how often the trailing team wins",
        "Five-season era (NBA seasons named by starting year; WNBA one year later)",
        "Comeback rate (%), 95% Wilson interval"))
    ticks = [f"NBA {1996 + 5 * i}-{2000 + 5 * i}<br>WNBA {1997 + 5 * i}-{2001 + 5 * i}" for i in range(6)]
    f.update_xaxes(tickmode="array", tickvals=list(range(1, 7)), ticktext=ticks)
    return f


def fig_sigma(fits: pl.DataFrame) -> go.Figure:
    f = go.Figure()
    s = fits.filter(pl.col("unit") == "season")
    for lg, name in LEAGUES.items():
        r = s.filter(pl.col("league") == lg).sort("label")
        start = [int(x[:4]) for x in r["label"].to_list()]
        f.add_trace(go.Scatter(
            x=start, y=r["sigma"].to_list(), mode="lines+markers", name=name,
            line=dict(color=COLORS[lg]), marker=dict(size=8, color=COLORS[lg]),
            error_y=dict(type="data", symmetric=False,
                         array=[h - v for h, v in zip(r["sigma_hi"], r["sigma"])],
                         arrayminus=[v - lo for v, lo in zip(r["sigma"], r["sigma_lo"])],
                         color=LIGHT[lg]),
            customdata=r["label"].to_list(),
            hovertemplate=f"{name} %{{customdata}}: sigma %{{y:.2f}}<extra></extra>"))
    f.update_layout(**base_layout(
        "Score-margin volatility by season",
        "Season (starting year)",
        "sigma: points per square-root minute, 95% interval"))
    return f


def fig_curve(safe: pl.DataFrame, bsafe: pl.DataFrame) -> go.Figure:
    f = go.Figure()
    nba = safe.filter((pl.col("league") == "nba") & (pl.col("q") == 0.01) & (pl.col("T") <= 720))
    eras = sorted(nba["era"].unique().to_list())
    pick = {eras[0]: "#8db8ea", eras[-1]: "#2a78d6"}
    for era, color in pick.items():
        r = nba.filter(pl.col("era") == era).sort("T").drop_nulls("safe_lead")
        f.add_trace(go.Scatter(
            x=(r["T"] / 60).to_list(), y=r["safe_lead"].to_list(), mode="markers",
            name=f"{era_short(era)}, observed", marker=dict(size=8, color=color),
            hovertemplate="%{x:.2f} min left: %{y} points<extra></extra>"))
        b = bsafe.filter((pl.col("league") == "nba") & (pl.col("q") == 0.01)
                         & (pl.col("era") == era) & (pl.col("T") <= 720)).sort("T")
        f.add_trace(go.Scatter(
            x=(b["T"] / 60).to_list(), y=b["safe_lead"].to_list(), mode="lines",
            name=f"{era_short(era)}, Brownian model", line=dict(color=color, dash="dot"),
            hovertemplate="%{x:.1f} min left: %{y:.1f} points<extra></extra>"))
    f.update_layout(**base_layout(
        "NBA: the lead the trailing team overcomes under 1% of the time",
        "Minutes of regulation left", "Safe lead (points)", height=460))
    return f


def main() -> None:
    FIG.mkdir(exist_ok=True)
    sit = pl.read_csv(OUT / "situations.csv")
    fits = pl.read_csv(OUT / "brownian_fits.csv")
    safe = pl.read_csv(OUT / "safe_leads.csv", null_values=[""])
    bsafe = pl.read_csv(OUT / "brownian_safe_leads.csv")
    for name, fig in [("fig1_q4_comebacks_py", fig_q4(sit)),
                      ("fig2_sigma_by_season_py", fig_sigma(fits)),
                      ("fig3_safe_lead_curve_py", fig_curve(safe, bsafe))]:
        fig.write_html(FIG / f"{name}.html", include_plotlyjs="cdn", full_html=True)
        fig.write_image(FIG / f"{name}.png", width=900, height=fig.layout.height or 420, scale=2)
        print("wrote", name)


if __name__ == "__main__":
    main()
