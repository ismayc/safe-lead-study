#!/bin/bash
# Every check in this repo: unit tests in both languages, then each step's
# rebuild-and-compare gate, the R reconcile, and the README results.
# Non-zero exit on any failure. PY overrides the interpreter (the family
# orchestrator sets it to the shared venv).
set -euo pipefail
cd "$(dirname "$0")"
PY=${PY:-../.venv/bin/python}

echo "=== unit tests: Python (pytest) ==="
$PY -m pytest tests/python -q

echo
echo "=== unit tests: R (testthat) ==="
(cd tests/R && Rscript -e 'r <- as.data.frame(testthat::test_dir(".", reporter = "silent", stop_on_failure = TRUE)); cat(sum(r$nb), "R expectations passed\n")')

echo
echo "=== checkpoints: coverage and per-season summary reproduce ==="
$PY -I python/01_checkpoints.py --check | tail -1

echo
echo "=== tier 1: comeback counts, safe leads, situations reproduce ==="
$PY -I python/02_empirical.py --check | tail -1

echo
echo "=== tier 2: Brownian fits, safe leads, calibration reproduce ==="
$PY -I python/03_brownian.py --check | tail -1

echo
echo "=== reconciliation: R vs Python, every table ==="
Rscript R/safe_lead.R >/dev/null
$PY -I python/04_reconcile.py | tail -1

echo
echo "=== report: README results match the outputs ==="
$PY -I python/06_report.py --check
