#!/usr/bin/env bash
set -u

if [[ "$#" -ne 8 ]]; then
  echo "Usage: $0 <results_dir> <data_root> <tables_out> <figures_out> <stdout_log> <stderr_log> <step_timeout_seconds> <n_boot>" >&2
  exit 2
fi

RESULTS_DIR="$1"
DATA_ROOT="$2"
TABLES_OUT="$3"
FIGURES_OUT="$4"
STDOUT_LOG="$5"
STDERR_LOG="$6"
STEP_TIMEOUT_SECONDS="$7"
N_BOOT="$8"
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
  python3 scripts/06_sensitivity.py \
    --config configs/detector/odi_default.yaml \
    --results "$RESULTS_DIR" \
    --data-root "$DATA_ROOT" \
    --out "$TABLES_OUT" \
    --figures-out "$FIGURES_OUT" \
    --n-boot "$N_BOOT" \
    "${EXTRA_ARGS[@]}" \
  > "$STDOUT_LOG" \
  2> "$STDERR_LOG"
exit "$?"
