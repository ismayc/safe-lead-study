# The whole safe-lead pipeline in R, written from the docstrings of
# python/lib.py, 01_checkpoints.py, 02_empirical.py, and 03_brownian.py. It
# reads the shared prepared events (../.pbp-archive/events/) and the finals
# checks, rebuilds the checkpoints itself, and writes an _r twin of every
# committed output. python/04_reconcile.py compares them cell by cell.
#
# Run from the repo root:  Rscript R/safe_lead.R

suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
})
source("R/functions.R")

ARCHIVE <- Sys.getenv("PBP_ARCHIVE", "../.pbp-archive")

season_checkpoints <- function(league, year) {
  reg <- regulation(league, year)
  nper <- reg[1]; plen <- reg[2]; total <- nper * plen
  fin <- read_csv(file.path(ARCHIVE, "events", sprintf("%s_%d_rs_finals.csv", league, year)),
                  col_select = c(gameId, gl_h, gl_a, status),
                  col_types = cols(gameId = col_character(), status = col_character(),
                                   gl_h = col_double(), gl_a = col_double(), .default = col_skip()),
                  progress = FALSE) |>
    filter(status == "ok") |>
    transmute(gameId, home_won = gl_h > gl_a)
  ev <- nanoparquet::read_parquet(file.path(ARCHIVE, "events", sprintf("%s_%d_rs.parquet", league, year)),
                                  col_select = c("gameId", "period", "secs_left", "seq",
                                                 "score_h", "score_a")) |>
    filter(period <= nper, gameId %in% fin$gameId) |>
    mutate(el = (period - 1) * plen + (plen - pmin(secs_left, plen)),
           margin = score_h - score_a)
  gi <- match(ev$gameId, fin$gameId)
  # One sort key per event, game first; findInterval then finds, for each
  # checkpoint, the last event at or before its moment (ties: last by seq).
  ord <- order(gi, ev$el, ev$seq)
  key <- gi[ord] * 1e5 + ev$el[ord]
  marg <- ev$margin[ord]
  game_of <- gi[ord]
  cps <- checkpoint_grid(total)
  ng <- nrow(fin)
  qg <- rep(seq_len(ng), each = length(cps))
  qT <- rep(cps, times = ng)
  qkey <- qg * 1e5 + (total - qT)
  idx <- findInterval(qkey, key)
  m <- ifelse(idx > 0 & game_of[pmax(idx, 1)] == qg, marg[pmax(idx, 1)], 0)
  lg <- league; yr <- as.integer(year); era <- era_of(league, year)
  out <- tibble(gameId = fin$gameId[qg], T = as.integer(qT), margin = m,
                home_won = fin$home_won[qg]) |>
    filter(margin != 0) |>
    mutate(lead = as.integer(abs(margin)), leader_home = margin > 0,
           comeback = as.integer(leader_home != home_won),
           league = lg, year = yr, era = era) |>
    select(gameId, T, lead, leader_home, comeback, league, year, era)
  out
}

cps <- bind_rows(lapply(names(YEARS), function(lg)
  bind_rows(lapply(YEARS[[lg]], function(y) season_checkpoints(lg, y)))))

summary_r <- cps |>
  group_by(league, year) |>
  summarise(games = n_distinct(gameId), checkpoints = n(), comebacks = sum(comeback),
            mean_lead = round(mean(lead), 6), .groups = "drop") |>
  arrange(league, year)
write_csv(summary_r, "output/checkpoint_summary_r.csv")

# Tier 1
counts <- cps |>
  group_by(league, era, T, lead) |>
  summarise(n = n(), k = sum(comeback), .groups = "drop") |>
  arrange(league, era, T, lead)
cells <- split(counts, list(counts$league, counts$era, counts$T), drop = TRUE)
sm <- list(); sf <- list()
for (cell in cells) {
  cell <- arrange(cell, lead)
  rate <- cell$k / cell$n
  pv <- pava_nonincreasing(rate, cell$n)
  bn <- tapply(cell$n, pv$block, sum)[pv$block]
  bk <- tapply(cell$k, pv$block, sum)[pv$block]
  wl <- t(mapply(wilson, bk, bn))
  cell <- cell |> mutate(rate = rate, fit = pv$fit, block_n = as.numeric(bn),
                         block_k = as.numeric(bk), lo = wl[, 1], hi = wl[, 2])
  sm[[length(sm) + 1]] <- cell
  for (q in THRESHOLDS) {
    sf[[length(sf) + 1]] <- tibble(
      league = cell$league[1], era = cell$era[1], T = cell$T[1], q = q,
      safe_lead = safe_lead(cell$lead, cell$fit, q),
      safe_lead_lo = safe_lead(cell$lead, cell$lo, q),
      safe_lead_hi = safe_lead(cell$lead, cell$hi, q))
  }
}
games <- cps |> group_by(league, era) |> summarise(n_games = n_distinct(gameId), .groups = "drop")
sm <- bind_rows(sm) |> arrange(league, era, T, lead)
sf <- bind_rows(sf) |> left_join(games, by = c("league", "era")) |> arrange(league, era, T, q)
write_csv(sm, "output/comeback_counts_r.csv")
write_csv(sf, "output/safe_leads_r.csv")

sit <- list(); chg <- list()
for (i in seq_len(nrow(SITUATIONS))) {
  s <- SITUATIONS[i, ]
  for (lg in c("nba", "wnba")) {
    Tsec <- if (lg == "nba") s$t_nba else s$t_wnba
    x <- cps |> filter(league == lg, T == Tsec, lead >= s$lo, lead <= s$hi) |>
      group_by(era) |> summarise(n = n(), k = sum(comeback), .groups = "drop") |> arrange(era)
    for (j in seq_len(nrow(x))) {
      w <- wilson(x$k[j], x$n[j])
      sit[[length(sit) + 1]] <- tibble(league = lg, situation = s$situation, era = x$era[j],
                                       n = x$n[j], k = x$k[j], rate = x$k[j] / x$n[j],
                                       lo = w[1], hi = w[2])
    }
    f <- x[1, ]; l <- x[nrow(x), ]
    d <- newcombe(l$k, l$n, f$k, f$n)
    a <- newcombe(l$k, l$n, f$k, f$n, Z_BONF12)
    chg[[length(chg) + 1]] <- tibble(league = lg, situation = s$situation, first_era = f$era,
                                     last_era = l$era, first_rate = f$k / f$n,
                                     last_rate = l$k / l$n, change = d[1], change_lo = d[2],
                                     change_hi = d[3], change_lo_adj = a[2], change_hi_adj = a[3])
  }
}
write_csv(bind_rows(sit), "output/situations_r.csv")
write_csv(bind_rows(chg), "output/situation_change_r.csv")

# Tier 2
fit_one <- function(sub) {
  cl <- sub |> group_by(T, lead) |> summarise(n = n(), k = sum(1 - comeback), .groups = "drop")
  x <- cl$lead / sqrt(cl$T / 60)
  b <- probit_slope(x, cl$n, cl$k)
  beta <- unname(b["beta"])
  se <- cluster_se(beta, sub$lead / sqrt(sub$T / 60), 1 - sub$comeback, sub$gameId)
  tibble(beta = beta, se = se, sigma = 1 / beta, sigma_lo = 1 / (beta + Z95 * se),
         sigma_hi = 1 / (beta - Z95 * se), n_checkpoints = nrow(sub),
         n_games = n_distinct(sub$gameId), iterations = as.integer(b["iterations"]))
}
fits <- bind_rows(
  cps |> group_by(league, label = era) |> group_modify(~ fit_one(.x)) |> ungroup() |>
    mutate(unit = "era"),
  cps |> group_by(league, year) |> group_modify(~ fit_one(.x)) |> ungroup() |>
    mutate(unit = "season", label = mapply(season_label, league, year)) |> select(-year)
) |> select(league, unit, label, beta, se, sigma, sigma_lo, sigma_hi, n_checkpoints,
            n_games, iterations) |> arrange(league, unit, label)
write_csv(fits, "output/brownian_fits_r.csv")

REPORT_T <- c(30, 60, 120, 180, 360, 600, 720, 1200, 1440)
ef <- fits |> filter(unit == "era")
bsafe <- bind_rows(lapply(seq_len(nrow(ef)), function(i) {
  r <- ef[i, ]
  bind_rows(lapply(REPORT_T, function(Tsec) bind_rows(lapply(THRESHOLDS, function(q) tibble(
    league = r$league, era = r$label, T = Tsec, q = q,
    safe_lead = brownian_safe_lead(r$sigma, Tsec, q),
    safe_lead_lo = brownian_safe_lead(r$sigma_lo, Tsec, q),
    safe_lead_hi = brownian_safe_lead(r$sigma_hi, Tsec, q))))))
}))
write_csv(bsafe, "output/brownian_safe_leads_r.csv")

T_BANDS <- list(c(0, 60), c(60, 180), c(180, 360), c(360, 720), c(720, 1440), c(1440, 2880))
LEAD_BANDS <- list(c(1, 3), c(4, 6), c(7, 10), c(11, 15), c(16, 99))
band <- function(v, bands, fmt, lower_open) {
  out <- rep(NA_character_, length(v))
  for (b in bands) {
    inb <- if (lower_open) v > b[1] & v <= b[2] else v >= b[1] & v <= b[2]
    out[inb] <- fmt(b)
  }
  out
}
calib <- cps |>
  left_join(ef |> select(league, era = label, sigma), by = c("league", "era")) |>
  mutate(pred = pnorm(-lead / (sigma * sqrt(T / 60))),
         t_band = band(T, T_BANDS, function(b) sprintf("%d-%ds", b[1], b[2]), TRUE),
         lead_band = band(lead, LEAD_BANDS, function(b)
           if (b[2] < 99) sprintf("%d-%d", b[1], b[2]) else sprintf("%d+", b[1]), FALSE)) |>
  group_by(league, era, t_band, lead_band) |>
  summarise(n = n(), observed = mean(comeback), predicted = mean(pred), .groups = "drop") |>
  arrange(league, era, t_band, lead_band)
write_csv(calib, "output/brownian_calibration_r.csv")
cat("R pipeline: ", nrow(cps), " checkpoints, ", nrow(sm), " cells, ", nrow(fits), " fits\n", sep = "")
