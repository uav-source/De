#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="${1:---dry-run}"

STEPS=(
  "python3 scripts/00_generate_minibench.py --all"
  "python3 scripts/01_simulate_observations.py --all --config configs/detector/odi_default.yaml"
  "python3 scripts/02_compute_odi.py --all --config configs/detector/odi_default.yaml"
  "python3 scripts/02_run_toy_lio.py --all --config configs/detector/odi_default.yaml"
  "python3 scripts/03_eval_metrics.py --all --config configs/detector/odi_default.yaml"
  "python3 scripts/04_plot_day14.py --results results/day14 --out results/day14/figures"
)

echo "Degen-LIO Day 14 reproduction skeleton"
echo "repo: $ROOT_DIR"
echo "mode: $MODE"

if [[ "$MODE" == "--dry-run" ]]; then
  echo "Planned steps:"
  for step in "${STEPS[@]}"; do
    echo "  $step"
  done
  echo "Day 2 skeleton only: future scripts are intentionally not required yet."
  exit 0
fi

if [[ "$MODE" != "--run" ]]; then
  echo "Usage: bash scripts/reproduce_day14.sh [--dry-run|--run]" >&2
  exit 2
fi

for step in "${STEPS[@]}"; do
  script_path="$(awk '{print $2}' <<< "$step")"
  if [[ ! -f "$script_path" ]]; then
    echo "Missing required future script: $script_path" >&2
    echo "Run with --dry-run during Day 2-12, or complete the pipeline before --run." >&2
    exit 3
  fi
  echo "+ $step"
  eval "$step"
done
