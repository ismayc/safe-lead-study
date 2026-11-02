# How big a lead is safe, and is it still safe?

Almost every broadcast eventually asks whether a lead is safe. We can answer
that question by looking at the score at fixed moments of every
regular-season game since the late 1990s: 35,492 NBA games from 1996-97 to
2025-26 and 6,469 WNBA games from 1997 to 2026. We want to see how often the
trailing team still wins, by lead and time left, and whether that has
changed across six five-season eras. In the NBA, a lead of 10 to 14 entering
the fourth quarter is lost more often. It happened 10.1% of the time in the
last five seasons compared to 5.8% in the first five. Score margins also
swing more than before. In the WNBA, the samples are too small to say either
way.

<div class="tiles">
<div class="tile"><div class="label">Fourth-quarter comebacks</div>
<div class="value">5.8% to 10.1%</div>
<div class="sub">NBA teams trailing by 10 to 14 entering the fourth quarter who won: 1996-97 to 2000-01 against 2021-22 to 2025-26.</div></div>
<div class="tile"><div class="label">The change</div>
<div class="value">+4.3 points</div>
<div class="sub">95% interval +2.0 to +6.5; +1.0 to +7.6 after adjusting for all 12 comparisons.</div></div>
<div class="tile"><div class="label">Margin volatility</div>
<div class="value">2.43 to 2.78</div>
<div class="sub">NBA sigma, in points per square-root minute, first era against last. The two 95% intervals do not overlap.</div></div>
<div class="tile"><div class="label">Last-minute leads</div>
<div class="value">6.2 times</div>
<div class="sub">How much more often NBA leads of 7 to 10 are lost in the final minute than the random-walk model predicts (0.17% against 0.03%).</div></div>
</div>

<div class="eyebrow beat">The question</div>

## Two ways to measure a safe lead

The study defines a lead as safe when the trailing team comes back to win
less than 1% of the time. It reads the score every 5 seconds over the last
two minutes of regulation and every 30 seconds before that. The study
answers in two ways, each with its own claim.

{{svg:dg1_reading_a_game|One game read the way the study reads every game: New Orleans against Cleveland on March 21, 2026. Each dot is a checkpoint, where the study records who leads and by how much. New Orleans entered the fourth quarter up 12, inside the 10 to 14 band the era comparison uses, and Cleveland won, so this game counts as one comeback in that situation.}}

The first is a count. For each lead, time left, and era, it takes the share
of games the trailing team went on to win, overtime included. These rates
are smoothed so that a bigger lead is never less safe than a smaller one,
and each comes with a 95% Wilson interval. To compare eras, the study uses
six fixed game situations where the data are dense, such as a 10 to 14 point
lead at the start of the fourth quarter, and puts a Newcombe interval on
each change, with a Bonferroni adjustment for running 12 comparisons at
once.

The second is a model. Hal Stern's 1994 Brownian-motion model treats the
score margin as a random walk with one volatility, sigma, per era or season.
This model turns any lead and time left into a win chance, provides a smooth
safe-lead curve, and makes the change in volatility one number with an
interval.

Games enter only if their play-by-play final matches the league's game log
and the running score never jumps by more than one basket on a single row;
55 NBA and 27 WNBA games fail those checks and are left out. Every table was
computed twice, in Python and in R, and the two agree on every cell.

<div class="eyebrow beat">Then and now</div>

## A double-digit lead entering the fourth is less safe than it was

In the NBA, teams that trailed by 10 to 14 entering the fourth quarter won
5.8% of the time from 1996-97 to 2000-01 (62 of 1,064 games) and 10.1% from
2021-22 to 2025-26 (118 of 1,167). The change is 4.3 percentage points, with
a 95% interval of 2.0 to 6.5. After the adjustment for multiple comparisons,
the interval stays above zero, 1.0 to 7.6.

{{fig:fig1_q4_comebacks_py|How often the team down 10 to 14 entering the fourth quarter wins, by era, with 95% Wilson intervals. The NBA sits near 7.7% for three eras, then steps up to about 10% from 2016-17 on; the WNBA intervals are wide and show no trend.}}

This rise was not gradual. The rate held between 7.6% and 7.8% for the three
middle eras, and then it stepped from 7.8% to 10.2% into 2016-17 to 2020-21
and stayed there. Across the six NBA situations, three show a rise whose
interval excludes zero: the start of the fourth quarter up 10 to 14, 6:00
left up 10 to 14, and 1:00 left up 5 or 6. After the adjustment, only the
fourth-quarter one remains. This study does not test why the step happened.

The WNBA shows no clear change. None of its six situations has an interval
that excludes zero. For example, entering the fourth up 10 to 14, the
trailing team won 3.5% of the time in 1997 to 2001 and 3.7% in 2022 to 2026,
which is a change of +0.2 points with an interval of -4.1 to +3.9. However,
the WNBA samples in these situations are 18% the size of the NBA's, so a
change as large as the NBA's cannot be ruled out either.

<div class="eyebrow beat">Safe leads</div>

## About 20 points is safe entering an NBA fourth quarter

If we count comebacks directly, we see that the 1% safe lead at the start of
the fourth quarter was 21 points in 1996-97 to 2000-01, with a range of 17
to 21 from the Wilson bounds, and 20 points in 2021-22 to 2025-26, with a
range of 18 to 23. With 6:00 left, the lead was 15 (13 to 17) and then 17
(13 to 19).

{{svg:dg3_comeback_grid|How often the NBA team trailing in the fourth quarter goes on to win, by lead (rows) and minutes left (columns), smoothed so a bigger lead is never less safe. Above the red line, leads were lost less than 1% of the time. In the recent era the darker cells reach higher in most columns: the same lead is lost more often. The boxed cells are the 10 to 14 point leads entering the fourth.}}

{{fig:fig3_safe_lead_curve_py|The NBA's 1% safe lead by minutes left, first era against last. Dots are observed safe leads; dotted lines are the Brownian model's. The model's curve for the recent era sits above the early one at every time left.}}

These single cells are noisy. The 1% tail rests on a few hundred games per
cell, which is why a lead can read safer at 6:00 than at 3:00 in some eras,
and why the era comparison above uses the denser middle of the distribution
instead of the safe lead itself.

<div class="eyebrow beat">The random-walk model</div>

## The margin swings more than it used to

The model provides a cleaner view of the same change. NBA sigma rose
from 2.43 (95% interval 2.34 to 2.53) in 1996-97 to 2000-01 to 2.78
(2.68 to 2.88) in 2021-22 to 2025-26, and the two intervals do not
overlap. Most of that rise occurred at the same point as the comeback
step: sigma was 2.55 in 2011-12 to 2015-16 and 2.81 in 2016-17 to
2020-21. The model's 1% safe lead entering the fourth quarter moved from
19.6 points (18.8 to 20.4) to 22.4 (21.6 to 23.2). In the WNBA, sigma
went from 2.14 (1.96 to 2.34) to 2.44 (2.27 to 2.64), and those
intervals overlap.

{{fig:fig2_sigma_by_season_py|Score-margin volatility, sigma, fitted season by season with 95% intervals. NBA seasons from 2016-17 on sit at or above the top of the earlier range (the season intervals overlap), while the WNBA's seasons move up and down inside much wider intervals with no clear trend.}}

In this model, sigma links the two findings. With no drift, the model
spreads the margin over the remaining minutes in proportion to sigma, so a
wider spread leaves more of the outcomes below zero at the buzzer. From a
12-point lead entering the fourth quarter, the model gives the trailing team
a 7.7% chance with the first era's sigma and 10.6% with the last era's. The
observed rates for leads of 10 to 14 moved from 5.8% to 10.1%, in the same
direction.

{{svg:dg2_sigma_fan|The model's view of the fourth quarter from a 12-point NBA lead. The shaded fan is where the margin is likely to be as the quarter plays out; the curve at the buzzer is the margin's final spread, and its red tail is the share of games the trailing team wins. The recent era's sigma widens the fan (the dashed line is the first era's edge) and enlarges the red tail.}}

<div class="eyebrow beat">Where the model breaks</div>

## A random walk has no term for fouling or team strength

The model is a smooth summary, not a calculator for the endgame. In the
NBA's last minute, leads of 7 to 10 are lost 0.17% of the time, against
the model's 0.03%, or 6.2 times as often. The likely reasons are late-game
fouling, three-point attempts, and timeouts, which add variance that a
constant-rate random walk has no room for. The error runs the other way for big leads with time left: with
6 to 12 minutes to play, leads of 16 or more are lost 0.54% of the time
against 0.79% predicted. Big leads belong disproportionately to better
teams, and the model has no term for team strength (an interpretation, not
tested here). For the endgame, the observed counts are the better guide.

{{fig:fig4_calibration_py|How far the model is off, by time left and lead (NBA, all eras pooled): observed comebacks divided by the model's prediction, on a log scale. On the dotted line at 1 the model is right. Points where the model expects fewer than five comebacks are left out.}}

<div class="eyebrow beat">Limits</div>

## What this does not show

These are regular-season games only; the playoffs are a different
population. The term "safe" is unconditional: a strong team's 10-point lead
is safer than these tables say, and a weak team's lead is less safe. The
running score comes from the league's play-by-play score stamps, and a stamp
wrong by exactly two or three points would pass both data checks. The eras
are fixed five-season blocks chosen before any result was seen, not fitted
break points, and the six comparison situations were picked after a first
look at comeback rates by era, so they are reported with both plain and
adjusted intervals, whatever they show. Finally, the study measures that the
NBA's fourth-quarter leads got less safe; it does not test why.