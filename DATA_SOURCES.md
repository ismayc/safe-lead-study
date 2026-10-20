# Data sources

One row per dataset. A dataset is not used until its **License** cell is filled
from the source's own page (quote it), or marked "unverified" with the reason.
Raw play-by-play stays local (`../.pbp-archive/` is outside every repo); this
repo publishes only aggregate tables.

| Dataset | URL | License (quoted) | Commercial use | Redistribution | Retrieved | Local file |
|---|---|---|---|---|---|---|
| `PlayByPlayV3` archives, NBA 1996-97 to 2025-26 and WNBA 1997 to 2026 regular season (`nbastatsv3_*`, `wnba_nbastatsv3_*`) | https://github.com/shufinskiy/nba_data | Repository: "Apache License 2.0" (GitHub license metadata). The rows come from stats.nba.com, so NBA.com terms still govern the data: unverified | no (personal research) | no: kept in `../.pbp-archive/raw/`, outside git | October 19, 2026 | `../.pbp-archive/raw/*.tar.xz` (sha256 in `raw/checksums.txt`) |
| WNBA 2026 regular season, the 148 games missing from the archive copy (captured July 17, 2026) | https://stats.wnba.com/stats/playbyplayv3 (harvested by playbyplay-study) | unverified: NBA.com terms of use; no license on the endpoint | no | no | July to October 2026 | `../playbyplay-study/data/raw_pbp/10226*.parquet` |
| LeagueGameLog team-game finals, every season above | https://stats.nba.com/stats/leaguegamelog (harvested by playoff-series-study) | unverified: NBA.com terms of use | no | no | October 2026 | `../playoff-series-study/data/raw/gamelogs/*_rs.csv` |

## Notes

- stats.nba.com and stats.wnba.com did not answer from either machine in
  October 2026; the GitHub archive is the only full-history source reached.
- The shared layer checks every archive game against LeagueGameLog; the
  per-game result is in `../.pbp-archive/events/<league>_<year>_rs_finals.csv`.
