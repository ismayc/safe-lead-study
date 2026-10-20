# The R twins of python/lib.py, written from its docstrings. tests/R pins
# them to the same hand-computed fixtures as tests/python.

YEARS <- list(nba = 1996:2025, wnba = 1997:2026)
ERA_LEN <- 5L
Z95 <- 1.959963984540054
THRESHOLDS <- c(0.01, 0.05, 0.10)
Z_ONE_SIDED <- c("0.01" = 2.3263478740408408, "0.05" = 1.6448536269514722,
                 "0.1" = 1.2815515655446004)

regulation <- function(league, year) {
  if (league == "nba") return(c(4L, 720L))
  if (year <= 2005) c(2L, 1200L) else c(4L, 600L)
}

checkpoint_grid <- function(total) c(seq(5L, 120L, 5L), seq(150L, total - 1L, 30L))

season_label <- function(league, year) {
  if (league == "nba") sprintf("%d-%02d", year, (year + 1) %% 100) else as.character(year)
}

era_of <- function(league, year) {
  first <- min(YEARS[[league]])
  a <- first + (year - first) %/% ERA_LEN * ERA_LEN
  b <- a + ERA_LEN - 1L
  if (league == "nba") sprintf("%s to %s", season_label("nba", a), season_label("nba", b))
  else sprintf("%d to %d", a, b)
}

# Pool adjacent violators for a nonincreasing fit; equal means are merged too.
# Returns list(fit, block).
pava_nonincreasing <- function(y, w) {
  s <- numeric(0); ww <- numeric(0); cnt <- integer(0)
  for (i in seq_along(y)) {
    s <- c(s, y[i] * w[i]); ww <- c(ww, w[i]); cnt <- c(cnt, 1L)
    m <- length(s)
    while (m > 1 && s[m] * ww[m - 1] >= s[m - 1] * ww[m]) {
      s[m - 1] <- s[m - 1] + s[m]; ww[m - 1] <- ww[m - 1] + ww[m]
      cnt[m - 1] <- cnt[m - 1] + cnt[m]
      s <- s[-m]; ww <- ww[-m]; cnt <- cnt[-m]
      m <- m - 1
    }
  }
  list(fit = rep(s / ww, cnt), block = rep(seq_along(cnt), cnt))
}

wilson <- function(k, n, z = Z95) {
  if (n == 0) return(c(0, 1))
  p <- k / n
  den <- 1 + z * z / n
  centre <- (p + z * z / (2 * n)) / den
  half <- z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
  c(max(0, centre - half), min(1, centre + half))
}

# Smallest lead from which every larger observed lead has value <= q; NA if none.
safe_lead <- function(leads, values, q) {
  o <- order(leads, decreasing = TRUE)
  best <- NA_integer_
  for (i in o) {
    if (values[i] <= q) best <- leads[i] else break
  }
  best
}

probit_parts <- function(beta, x) {
  eta <- beta * x
  list(p = pnorm(eta), q = pnorm(-eta), d = dnorm(eta))
}

probit_slope <- function(x, n, k, tol = 1e-12, max_iter = 100L) {
  beta <- 0.1
  for (it in seq_len(max_iter)) {
    pr <- probit_parts(beta, x)
    m <- (pr$p * pr$q) > 0
    xm <- x[m]; nm <- n[m]; km <- k[m]; p <- pr$p[m]; q <- pr$q[m]; d <- pr$d[m]
    score <- sum(xm * d * (km - nm * p) / (p * q))
    info <- sum(nm * xm * xm * d * d / (p * q))
    step <- score / info
    beta <- beta + step
    if (abs(step) < tol) return(c(beta = beta, iterations = it))
  }
  stop("probit did not converge")
}

cluster_se <- function(beta, x, y, game) {
  pr <- probit_parts(beta, x)
  m <- (pr$p * pr$q) > 0
  x <- x[m]; y <- y[m]; game <- game[m]; p <- pr$p[m]; q <- pr$q[m]; d <- pr$d[m]
  info <- sum(x * x * d * d / (p * q))
  s <- rowsum(x * d * (y - p) / (p * q), game, reorder = FALSE)
  sqrt(sum(s * s)) / info
}

brownian_safe_lead <- function(sigma, Tsec, q) {
  Z_ONE_SIDED[[as.character(q)]] * sigma * sqrt(Tsec / 60)
}

Z_BONF12 <- 2.8652602385321346

newcombe <- function(k1, n1, k2, n2, z = Z95) {
  p1 <- k1 / n1; p2 <- k2 / n2
  w1 <- wilson(k1, n1, z); w2 <- wilson(k2, n2, z)
  d <- p1 - p2
  c(d, d - sqrt((p1 - w1[1])^2 + (w2[2] - p2)^2), d + sqrt((w1[2] - p1)^2 + (p2 - w2[1])^2))
}

SITUATIONS <- data.frame(
  situation = c("halftime, up 10-14", "start of Q4, up 10-14", "start of Q4, up 15-19",
                "6:00 left, up 10-14", "3:00 left, up 7-9", "1:00 left, up 5-6"),
  t_nba = c(1440L, 720L, 720L, 360L, 180L, 60L),
  t_wnba = c(1200L, 600L, 600L, 360L, 180L, 60L),
  lo = c(10L, 10L, 15L, 10L, 7L, 5L),
  hi = c(14L, 14L, 19L, 14L, 9L, 6L))
