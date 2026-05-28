#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="${1:---dry-run}"
RUN_ID="day14_$(date -u +%Y%m%dT%H%M%SZ)"
TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
STEP_TIMEOUT_SECONDS="${STEP_TIMEOUT_SECONDS:-180}"
REPRO_N_BOOT="${REPRO_N_BOOT:-300}"

export MPLBACKEND=Agg
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

SEQUENCES=(
  "OC-L0-S01-M1"
  "ST-L3-S01-M1"
  "CT-L2-S01-M2"
  "RT-L4-S01-M1"
)

echo "Degen-LIO Day 14 reproduction"
echo "repo: $ROOT_DIR"
echo "mode: $MODE"
echo "step_timeout_seconds: $STEP_TIMEOUT_SECONDS"
echo "repro_n_boot: $REPRO_N_BOOT"

if [[ "$MODE" == "--dry-run" ]]; then
  cat <<'EOF'
Planned --run steps:
  clean generated results and minibench sequence directories
  python3 scripts/check_env.py
  python3 scripts/00_generate_minibench.py --all
  python3 scripts/01_simulate_observations.py --all --config configs/detector/odi_default.yaml
  python3 scripts/02_compute_odi.py --all --config configs/detector/odi_default.yaml
  python3 scripts/02_run_toy_lio.py --all --config configs/detector/odi_default.yaml
  python3 scripts/03_eval_metrics.py --all --config configs/detector/odi_default.yaml
  python3 scripts/05_metric_validity.py --config configs/detector/odi_default.yaml
  python3 scripts/04_plot_day14.py --results results/day14 --out results/day14/figures
  python3 scripts/06_sensitivity.py --config configs/detector/odi_default.yaml --results results/day14 --out results/day14/tables --figures-out results/day14/figures
  python3 scripts/07_reproduction_manifest.py ...
Execution is delegated to scripts/run_reproduce_steps.py.
Each step is run with subprocess.run(timeout=STEP_TIMEOUT_SECONDS), stdout/stderr logs,
and a pinned non-interactive plotting/threading environment.
EOF
  exit 0
fi

if [[ "$MODE" != "--run" ]]; then
  echo "Usage: bash scripts/reproduce_day14.sh [--dry-run|--run]" >&2
  exit 2
fi

if [[ ! -f scripts/run_reproduce_steps.py ]]; then
  echo "Missing required script: scripts/run_reproduce_steps.py" >&2
  exit 3
fi

exec python3 scripts/run_reproduce_steps.py \
  --run-id "$RUN_ID" \
  --timestamp "$TIMESTAMP" \
  --timeout-seconds "$STEP_TIMEOUT_SECONDS" \
  --n-boot "$REPRO_N_BOOT" \
  --results results/day14
