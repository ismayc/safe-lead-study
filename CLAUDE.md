# Safe-lead study

How big a lead is safe with a given time left, NBA 1996-97 to 2025-26 and
WNBA 1997 to 2026, and has it changed? Personal research in the
basketball-data-science family (backlog: `../hub/ideas/historical-analysis-ideas.md`,
Round 2 #6). Decisions and their dates: `docs/design.md`. Private repo.

## Data context

- **Source:** the family's shared PlayByPlayV3 layer,
  `../basketball-analysis-tools/pbp_history.py`; prepared events and per-game
  finals checks under `../.pbp-archive/events/`. Only games with finals
  status `ok` are used.
- **Grain:** checkpoints: one game at one moment (`gameId`, `T` = seconds of
  regulation left), only when someone leads. Aggregates: league x era x T x
  lead.
- **Keys:** `gameId` is 10-character text (`002` NBA, `102` WNBA regular
  season). Archive years are start years (NBA 1996 = 1996-97).
- **Regulation:** NBA 4 x 720 s; WNBA 2 x 1200 s through 2005, 4 x 600 s
  from 2006 (2006 period-start rows read 12:00; clamp).
- **Known issues:** see "Data checks" in `docs/design.md` (finals mismatch,
  score jumps). Scores are running maxima of stamps; never forward-fill.
- **Sources of truth:** LeagueGameLog finals (playoff-series-study).
- **Suspicious results:** a lead over 80, a comeback from 20+ with under two
  minutes left, or a season losing over 5% of games means stop and check.

Data sources and licenses: `DATA_SOURCES.md`. Raw rows stay local; publish
aggregate tables only.

## How work is done here

- Family layout: `python/NN_*.py`, `python/lib.py` and its R twin
  `R/functions.R`, `R/safe_lead.R` for the full R pipeline, `tests/python`
  and `tests/R` on shared fixtures, `output/` committed, `run_checks.sh` as
  the gate. Python uses polars and plotly; the shared venv is `../.venv`.
- Python and R must agree on every reconciled cell within 1e-9, so methods
  are deterministic (PAVA, Wilson and Newcombe intervals, Fisher scoring).
  No bootstrap.
- README results are generated (`python/06_report.py`); never type a number
  into them.
- **Plan mode first** for any step that drops or filters games, deletes or
  overwrites files, joins tables, or changes a definition in `lib.py`.
- Before reporting: rerun, recompute one headline number another way, and
  report row and game counts before and after every filter.
- Label anything not checked against the data as unverified.
