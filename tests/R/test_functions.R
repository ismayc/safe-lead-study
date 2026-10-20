# R/functions.R against the same hand-computed fixtures as
# tests/python/test_lib.py. Run from the repo root:
#   Rscript -e 'testthat::test_dir("tests/R")'

source(file.path("..", "..", "R", "functions.R"), chdir = FALSE)

test_that("PAVA pools violators and ties", {
  r <- pava_nonincreasing(c(0.5, 0.6, 0.2, 0.2, 0.1), c(1, 1, 2, 2, 1))
  expect_equal(r$fit, c(0.55, 0.55, 0.2, 0.2, 0.1))
  expect_equal(r$block, c(1L, 1L, 2L, 2L, 3L))
})

test_that("PAVA preserves the weighted mean", {
  y <- c(0.1, 0.3, 0.2, 0.4, 0.0); w <- c(3, 1, 2, 5, 4)
  fit <- pava_nonincreasing(y, w)$fit
  expect_equal(sum(fit * w), sum(y * w))
  expect_true(all(diff(fit) <= 1e-15))
})

test_that("Wilson interval", {
  expect_equal(wilson(5, 100), c(0.021543, 0.111750), tolerance = 1e-5)
  z2 <- Z95^2
  expect_equal(wilson(0, 380)[2], z2 / (380 + z2))
  expect_true(wilson(0, 380)[2] > 0.01 && wilson(0, 381)[2] < 0.01)
})

test_that("safe lead", {
  expect_equal(safe_lead(1:4, c(0.3, 0.02, 0.005, 0.0), 0.01), 3L)
  expect_equal(safe_lead(1:4, c(0.3, 0.005, 0.02, 0.0), 0.01), 4L)
  expect_true(is.na(safe_lead(1:2, c(0.3, 0.2), 0.01)))
})

test_that("regulation and eras", {
  expect_equal(regulation("wnba", 2005), c(2L, 1200L))
  expect_equal(regulation("wnba", 2006), c(4L, 600L))
  expect_equal(era_of("nba", 1996), "1996-97 to 2000-01")
  expect_equal(era_of("nba", 2001), "2001-02 to 2005-06")
  expect_equal(era_of("nba", 2025), "2021-22 to 2025-26")
  expect_equal(era_of("wnba", 2026), "2022 to 2026")
  g <- checkpoint_grid(2880)
  expect_equal(g[1:3], c(5L, 10L, 15L))
  expect_equal(tail(g, 1), 2850L)
})

test_that("probit recovers an exact slope", {
  x <- c(0.5, 1, 2, 3, 4); n <- rep(1000, 5)
  b <- probit_slope(x, n, n * pnorm(0.5 * x))
  expect_equal(unname(b["beta"]), 0.5, tolerance = 1e-10)
})

test_that("cluster SE is zero for one cluster", {
  x <- c(0.5, 1, 1, 2, 3, 0.2); y <- c(1, 0, 1, 1, 1, 0)
  beta <- unname(probit_slope(x, rep(1, 6), y)["beta"])
  expect_equal(cluster_se(beta, x, y, rep(1L, 6)), 0, tolerance = 1e-10)
  expect_gt(cluster_se(beta, x, y, 1:6), 0)
})

test_that("Brownian safe lead", {
  expect_equal(brownian_safe_lead(2, 240, 0.01), 4 * 2.3263478740408408)
})

test_that("Newcombe matches the published example", {
  expect_equal(newcombe(56, 70, 48, 80), c(0.2, 0.0524, 0.3339), tolerance = 1e-3)
  a <- newcombe(56, 70, 48, 80, Z_BONF12)
  expect_true(a[2] < 0.0524 && a[3] > 0.3339)
})
