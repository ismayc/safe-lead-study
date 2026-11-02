"""Figures, from committed and R-reconciled outputs only (situations.csv,
brownian_fits.csv, safe_leads.csv, brownian_safe_leads.csv,
brownian_calibration.csv). Plotly originals go to figures/; report_builder.py
swaps in the family's famplot engine at publish time, so only what famplot
draws is used (scatter lines and markers, error bars, line shapes, text
annotations). Every number in a title or annotation is read from those
tables. The explainer diagrams are python/08_diagrams.py.

Figures:
  fig1_q4_comebacks_py    comeback rate from 10-14 up at the start of the
                          fourth quarter, by era, with Wilson intervals and
                          the NBA's 2016-17 step marked
  fig2_sigma_by_season_py margin volatility (sigma) by season, with 95%
                          intervals and the NBA's first- and last-era fits
  fig3_safe_lead_curve_py 1% safe lead by time left, NBA first and last era:
                          empirical (PAVA) and Brownian
  fig4_calibration_py     observed against model-predicted comeback rates
                          (NBA, all eras pooled) by time left, one line per
                          lead band

Run:  python python/05_figures.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import plotly.graph_objects as go
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
FIG = ROOT / "figures"
LEAGUES = {"nba": "NBA", "wnba": "WNBA"}
# famplot's first two family colors, the same as the other studies.
COLORS = {"nba": "#2a78d6", "wnba": "#eb6834"}
LIGHT = {"nba": "#8db8ea", "wnba": "#f3a77f"}
INK = "#77766f"
RED = "#e34948"
Q4 = "start of Q4, up 10-14"


def base_layout(title: str, xtitle: str, ytitle: str, height: int = 420) -> dict:
    return dict(title=title, xaxis_title=xtitle, yaxis_title=ytitle, template="plotly_white",
                height=height, margin=dict(l=70, r=30, t=60, b=60),
                legend=dict(orientation="h", y=-0.2))


def era_short(era: str) -> str:
    """"1996-97 to 2000-01" -> "1996-97 to 00-01"; WNBA labels unchanged."""
    a, b = era.split(" to ")
    return f"{a} to {b[2:]}" if "-" in b else era


def pct(p: float) -> str:
    return f"{p * 100:.1f}%"


def band() -> tuple[int, int]:
    _, _, _, a, b = next(s for s in lib.SITUATIONS if s[0] == Q4)
    return a, b


def fig_q4(sit: pl.DataFrame) -> go.Figure:
    f = go.Figure()
    s = sit.filter(pl.col("situation") == Q4)
    a, b = band()
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
    # The NBA's step: the era with the largest rise over the one before it.
    nba = s.filter(pl.col("league") == "nba").sort("era")
    rates = nba["rate"].to_list()
    j = max(range(1, len(rates)), key=lambda i: rates[i] - rates[i - 1])
    step_season = nba["era"][j].split(" to ")[0]
    xs = j + 0.5
    hi_y = float(s["hi"].max()) * 100
    top = hi_y * 1.35
    f.add_shape(type="line", x0=xs, x1=xs, y0=0, y1=top, line=dict(color=INK, dash="dot", width=1.2))
    f.add_annotation(x=xs, y=top, text=f"NBA step in {step_season}:<br>{pct(rates[j - 1])} to {pct(rates[j])}",
                     showarrow=False, xanchor="left", yanchor="top", font=dict(color=COLORS["nba"], size=12))
    f.update_layout(**base_layout(
        f"NBA leads of {a} to {b} entering the fourth are lost more often since {step_season}",
        "Five-season era (NBA seasons named by starting year; WNBA one year later)",
        "Trailing team's win rate (%), 95% interval"))
    ticks = [f"NBA {1996 + 5 * i}-{2000 + 5 * i}<br>WNBA {1997 + 5 * i}-{2001 + 5 * i}" for i in range(6)]
    f.update_xaxes(tickmode="array", tickvals=list(range(1, 7)), ticktext=ticks)
    f.update_yaxes(range=[0, top])
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
    # The NBA's first- and last-era fits as level lines over their seasons.
    e = fits.filter((pl.col("unit") == "era") & (pl.col("league") == "nba")).sort("label")
    y_lo, y_hi = float(s["sigma_lo"].min()) * 0.88, float(s["sigma_hi"].max()) * 1.1
    for row, anchor in ((e.row(0, named=True), "left"), (e.row(-1, named=True), "right")):
        y0 = int(row["label"][:4])
        f.add_shape(type="line", x0=y0 - 0.4, x1=y0 + lib.ERA_LEN - 0.6, y0=row["sigma"], y1=row["sigma"],
                    line=dict(color=COLORS["nba"], width=3))
        # First era's label at the bottom edge, last era's at the top, so the
        # two never meet on a phone.
        f.add_annotation(x=y0 - 0.4 if anchor == "left" else y0 + lib.ERA_LEN - 0.6,
                         y=y_lo if anchor == "left" else y_hi,
                         text=f"NBA {era_short(row['label'])}: {row['sigma']:.2f}",
                         showarrow=False, xanchor=anchor,
                         yanchor="bottom" if anchor == "left" else "top",
                         font=dict(color=COLORS["nba"], size=12))
    step = int(e["label"][-2][:4])
    f.add_shape(type="line", x0=step - 0.5, x1=step - 0.5, y0=float(s["sigma_lo"].min()),
                y1=float(s["sigma_hi"].max()), line=dict(color=INK, dash="dot", width=1.2))
    f.update_layout(**base_layout(
        f"NBA score margins swing more since {lib.pbp_history.season_label('nba', step)}; "
        "WNBA seasons are too noisy to call",
        "Season (starting year)",
        "sigma: points per square-root minute, 95% interval"))
    f.update_yaxes(range=[y_lo, y_hi])
    return f


def fig_curve(safe: pl.DataFrame, bsafe: pl.DataFrame) -> go.Figure:
    f = go.Figure()
    nba = safe.filter((pl.col("league") == "nba") & (pl.col("q") == lib.THRESHOLDS[0]) & (pl.col("T") <= 720))
    eras = sorted(nba["era"].unique().to_list())
    pick = {eras[0]: ("First era", "#8db8ea"), eras[-1]: ("Last era", "#2a78d6")}
    for era, (tag, color) in pick.items():
        r = nba.filter(pl.col("era") == era).sort("T").drop_nulls("safe_lead")
        f.add_trace(go.Scatter(
            x=(r["T"] / 60).to_list(), y=r["safe_lead"].to_list(), mode="markers",
            name=f"{tag}, {era}: observed", marker=dict(size=8, color=color),
            hovertemplate="%{x:.2f} min left: %{y} points<extra></extra>"))
        b = bsafe.filter((pl.col("league") == "nba") & (pl.col("q") == lib.THRESHOLDS[0])
                         & (pl.col("era") == era) & (pl.col("T") <= 720)).sort("T")
        f.add_trace(go.Scatter(
            x=(b["T"] / 60).to_list(), y=b["safe_lead"].to_list(), mode="lines",
            name=f"{tag}: Brownian model", line=dict(color=color, dash="dot"),
            hovertemplate="%{x:.1f} min left: %{y:.1f} points<extra></extra>"))
        end = b.row(-1, named=True)
        if tag == "Last era":
            f.add_annotation(x=end["T"] / 60, y=end["safe_lead"],
                             text=f"{tag} model: {end['safe_lead']:.1f}",
                             showarrow=False, xanchor="right", yanchor="bottom", yshift=4,
                             font=dict(color=color, size=12))
        else:
            # Below the line, one report point in from the end, clear of the dots.
            mid = b.row(-3, named=True)
            f.add_annotation(x=mid["T"] / 60, y=mid["safe_lead"],
                             text=f"{tag} model: {end['safe_lead']:.1f}",
                             showarrow=False, xanchor="left", yanchor="top", yshift=-30,
                             font=dict(color=color, size=12))
    last_obs = nba.filter((pl.col("era") == eras[-1]) & (pl.col("T") == 720))["safe_lead"][0]
    f.update_layout(**base_layout(
        f"About {last_obs} points is safe entering an NBA fourth quarter; "
        "the model's safe lead has grown",
        "Minutes of regulation left", "Lead lost 1% of the time or less (points)", height=460))
    return f


def fig_calibration(cal: pl.DataFrame) -> go.Figure:
    """Observed over predicted comeback rate, NBA, all eras pooled (each
    band's rates weighted by its checkpoints). A point is shown only where
    the model expects at least MIN_EXPECTED comebacks, so a ratio never rests
    on a near-zero prediction."""
    MIN_EXPECTED = 5
    c = (cal.filter(pl.col("league") == "nba")
            .group_by("t_band", "lead_band")
            .agg(n=pl.col("n").sum(), k=(pl.col("observed") * pl.col("n")).sum(),
                 e=(pl.col("predicted") * pl.col("n")).sum())
            .with_columns(obs=pl.col("k") / pl.col("n"), pred=pl.col("e") / pl.col("n"),
                          ratio=pl.col("k") / pl.col("e"),
                          t0=pl.col("t_band").str.extract(r"^(\d+)").cast(pl.Int32),
                          l0=pl.col("lead_band").str.extract(r"^(\d+)").cast(pl.Int32)))
    tb = c.select("t_band", "t0").unique().sort("t0")
    xpos = {t: i + 1 for i, t in enumerate(tb["t_band"].to_list())}
    ticks = []
    for t in tb["t_band"].to_list():
        a, b = (int(v) // 60 for v in t.rstrip("s").split("-"))
        ticks.append("last minute" if a == 0 else f"{a} to {b}")
    f = go.Figure()
    leads = c.select("lead_band", "l0").unique().sort("l0")["lead_band"].to_list()
    shown = c.filter((pl.col("e") >= MIN_EXPECTED) & (pl.col("k") > 0))
    # The two points the story names: the largest underprediction and the
    # largest overprediction.
    late = shown.sort("ratio").row(-1, named=True)
    big = shown.sort("ratio").row(0, named=True)
    palette = {late["lead_band"]: RED, big["lead_band"]: COLORS["nba"]}
    greys = ["#b9b7ae", "#9a988f", "#7d7b73"]
    gi = 0
    xs = [1, len(xpos)]
    f.add_trace(go.Scatter(x=xs, y=[1, 1], mode="lines", name="Model exactly right",
                           line=dict(color=INK, width=1.2, dash="dot"), hoverinfo="skip",
                           showlegend=False))
    for lb in leads:
        r = shown.filter(pl.col("lead_band") == lb).sort("t0")
        color = palette.get(lb)
        if color is None:
            color, gi = greys[gi % len(greys)], gi + 1
        f.add_trace(go.Scatter(
            x=[xpos[t] for t in r["t_band"].to_list()], y=r["ratio"].to_list(),
            mode="lines+markers",
            name=f"lead {lb[:-1]} or more" if lb.endswith("+") else f"lead {lb.replace('-', ' to ')}",
            line=dict(color=color, width=2.6 if lb in palette else 1.4),
            marker=dict(size=8 if lb in palette else 6, color=color),
            customdata=list(zip((r["obs"] * 100).to_list(), (r["pred"] * 100).to_list())),
            hovertemplate=f"lead {lb}: observed %{{customdata[0]:.2f}}%, "
                          "model %{customdata[1]:.2f}%<extra></extra>"))
    def where(row):
        t = ticks[xpos[row["t_band"]] - 1]
        t = t if t == "last minute" else f"{t} minutes left"
        lb = row["lead_band"]
        lead = f"up {lb[:-1]} or more" if lb.endswith("+") else f"up {lb.replace('-', ' to ')}"
        return f"{t[0].upper()}{t[1:]}, {lead}"
    f.add_annotation(x=xpos[late["t_band"]], y=late["ratio"],
                     text=f"{where(late)}: lost {late['ratio']:.1f} times as often "
                          f"as the model says<br>({late['obs'] * 100:.2f}% against "
                          f"{late['pred'] * 100:.2f}%)",
                     showarrow=False, xanchor="left", yanchor="middle", xshift=10,
                     font=dict(color=RED, size=12))
    f.add_annotation(x=xpos[big["t_band"]], y=big["ratio"],
                     text=f"{where(big)}:<br>lost less often than predicted "
                          f"({big['obs'] * 100:.2f}% against {big['pred'] * 100:.2f}%)",
                     showarrow=False, xanchor="center", yanchor="top", yshift=-12,
                     font=dict(color=COLORS["nba"], size=12))
    f.add_annotation(x=len(xpos), y=1, text="model exactly right", showarrow=False,
                     xanchor="right", yanchor="bottom", yshift=3, font=dict(color=INK, size=11.5))
    f.update_layout(**base_layout(
        "The random walk underrates last-minute comebacks and overrates big-lead ones",
        "Minutes of regulation left", "Observed comebacks / model's prediction (log scale)",
        height=460))
    f.update_xaxes(tickmode="array", tickvals=list(xpos.values()), ticktext=ticks)
    # Log axes take their range in log10 units, in plotly and in famplot.
    lo, hi = float(shown["ratio"].min()), float(shown["ratio"].max())
    f.update_yaxes(type="log", range=[math.log10(lo * 0.55), math.log10(hi * 1.5)])
    return f


def main() -> None:
    FIG.mkdir(exist_ok=True)
    sit = pl.read_csv(OUT / "situations.csv")
    fits = pl.read_csv(OUT / "brownian_fits.csv")
    safe = pl.read_csv(OUT / "safe_leads.csv", null_values=[""])
    bsafe = pl.read_csv(OUT / "brownian_safe_leads.csv")
    cal = pl.read_csv(OUT / "brownian_calibration.csv")
    for name, fig in [("fig1_q4_comebacks_py", fig_q4(sit)),
                      ("fig2_sigma_by_season_py", fig_sigma(fits)),
                      ("fig3_safe_lead_curve_py", fig_curve(safe, bsafe)),
                      ("fig4_calibration_py", fig_calibration(cal))]:
        fig.write_html(FIG / f"{name}.html", include_plotlyjs="cdn", full_html=True)
        fig.write_image(FIG / f"{name}.png", width=900, height=fig.layout.height or 420, scale=2)
        print("wrote", name)


if __name__ == "__main__":
    main()
