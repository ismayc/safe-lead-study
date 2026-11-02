# Design

## Question

How big a lead is safe with a given amount of time left, in the NBA and the
WNBA, and has that changed since the late 1990s? From the backlog idea
"The death of the safe lead" (`../hub/ideas/historical-analysis-ideas.md`,
Round 2 #6).

## Decisions

Made by Chester Ismay on October 19, 2026, before any result was computed:

1. **Its own repo**, one of three studies built on the shared
   PlayByPlayV3 layer.
2. **Full history**: NBA 1996-97 to 2025-26, WNBA 1997 to 2026, regular
   season.
3. **"Safe" means a comeback rate of 1% or less**, with 5% and 10% reported
   alongside. The decision was first written as "under 1%". The code has always
   used "1% or less", so the words were aligned to it on November 2, 2026, and no
   number changed. A strict "under 1%" would move 70 of 11,556 safe-lead values,
   because 17 smoothed rates equal exactly 1%.

Made while building (October 19, 2026), each for the reason given:

4. **Smoothing model: Stern's Brownian motion, not the Elam race model.** The
   option Chester picked named the Elam study's race model as the smoother,
   but that model races to a target score and has no clock, so it cannot
   say what lead is safe with T seconds left. Stern (1994) is the standard
   clock-based model for exactly this question, and it is deterministic, so
   it reconciles across languages.
5. **Eras are fixed five-season blocks** from each league's first season,
   chosen before results: six per league.
6. **The era comparison uses six fixed situations** (halftime, the start of
   the fourth quarter at two lead bands, 6:00, 3:00, and 1:00 left), not the
   1% safe lead itself, whose cells rest on too few games to compare. The
   six were chosen after a first look at comeback rates by era (shown in
   the build session), so they are not pre-registered; all six are reported
   with both plain and Bonferroni-adjusted intervals, whatever they show.
7. **PAVA merges equal means.** Without that, every zero-comeback lead at the
   top of a cell is its own block of a few games, and no Wilson upper bound
   could ever certify 1%.

## Definitions

In `python/lib.py` (Python) and `R/functions.R` (R), each pinned by the same
fixtures in `tests/python` and `tests/R`:

- **Checkpoint:** seconds of regulation left, T: every 5 seconds from 5 to
  120, then every 30 seconds to the start of the game.
- **Lead at T:** the score after every event at or before that moment.
- **Regulation:** NBA four 12:00 quarters; WNBA two 20:00 halves through
  2005, four 10:00 quarters from 2006. The 2006 WNBA period-start rows read
  12:00; clock readings are clamped to the period length.
- **Comeback:** the team trailing at T wins (overtime included); ties at T
  are left out.

## Data checks

From the shared layer (`../basketball-analysis-tools/pbp_history.py`), every
game is checked before use:

- the final score in the events equals LeagueGameLog's (playoff-series-study
  `data/raw/gamelogs/`);
- no running score rises by more than 3 on one row. This second check exists
  because the running-maximum rule hides a too-high stamp that is below the
  team's final: in 0021700025 a home stamp of 114 ninety seconds in froze the
  home score there, every margin until the real score passed 114 was wrong,
  and the final still matched. It removed 46 games that the finals check
  passed (35 NBA, 11 WNBA), and the largest lead in the data fell from 114 to
  78 (0022100330, Memphis 152, Oklahoma City 79: real, unverified against a
  box score).

Coverage per season, with the reason for every game left out:
`output/coverage.csv`.
