#!/usr/bin/env bash
set -u

if [[ "$#" -ne 5 ]]; then
  echo "Usage: $0 <results_dir> <figures_out> <stdout_log> <stderr_log> <step_timeout_seconds>" >&2
  exit 2
fi

RESULTS_DIR="$1"
FIGURES_OUT="$2"
STDOUT_LOG="$3"
STDERR_LOG="$4"
STEP_TIMEOUT_SECONDS="$5"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

mkdir -p "$(dirname "$STDOUT_LOG")" "$(dirname "$STDERR_LOG")"

EXTRA_ARGS=()
if [[ "${DEGEN_STEP_SMOKE_TEST_NO_RENDER:-0}" == "1" ]]; then
  EXTRA_ARGS+=(--smoke-test-no-render)
fi

cd "$ROOT_DIR"
timeout --kill-after=10s "${STEP_TIMEOUT_SECONDS}s" \
  env DEGEN_FORCE_CLI_EXIT=1 \
      MPLBACKEND=Agg \
      PYTHONUNBUFFERED=1 \
      OMP_NUM_THREADS=1 \
      OPENBLAS_NUM_THREADS=1 \
      MKL_NUM_THREADS=1 \
      NUMEXPR_NUM_THREADS=1 \
  python3 scripts/04_plot_day14.py \
    --results "$RESULTS_DIR" \
    --out "$FIGURES_OUT" \
    "${EXTRA_ARGS[@]}" \
  > "$STDOUT_LOG" \
  2> "$STDERR_LOG"
exit "$?"
