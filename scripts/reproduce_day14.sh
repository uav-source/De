#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="${1:---dry-run}"
RUN_ID="day14_$(date -u +%Y%m%dT%H%M%SZ)"
TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

SEQUENCES=(
  "OC-L0-S01-M1"
  "ST-L3-S01-M1"
  "CT-L2-S01-M2"
  "RT-L4-S01-M1"
)

echo "Degen-LIO Day 14 reproduction"
echo "repo: $ROOT_DIR"
echo "mode: $MODE"

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
EOF
  exit 0
fi

if [[ "$MODE" != "--run" ]]; then
  echo "Usage: bash scripts/reproduce_day14.sh [--dry-run|--run]" >&2
  exit 2
fi

for script in \
  scripts/check_env.py \
  scripts/00_generate_minibench.py \
  scripts/01_simulate_observations.py \
  scripts/02_compute_odi.py \
  scripts/02_run_toy_lio.py \
  scripts/03_eval_metrics.py \
  scripts/04_plot_day14.py \
  scripts/05_metric_validity.py \
  scripts/06_sensitivity.py \
  scripts/07_reproduction_manifest.py; do
  if [[ ! -f "$script" ]]; then
    echo "Missing required script: $script" >&2
    exit 3
  fi
done

START_EPOCH="$(date +%s)"

clean_generated() {
  for dir in raw metrics tables figures manifests; do
    mkdir -p "results/day14/$dir"
    find "results/day14/$dir" -type f ! -name ".gitkeep" ! -name "manifest_template.json" -delete
  done
  for seq in "${SEQUENCES[@]}"; do
    rm -rf "data/minibench/$seq"
  done
}

clean_generated

COMMAND_LOG="results/day14/manifests/day14_commands_${RUN_ID}.txt"
: > "$COMMAND_LOG"

run_step() {
  echo "$*" >> "$COMMAND_LOG"
  echo "+ $*"
  "$@"
}

run_step python3 scripts/check_env.py
run_step python3 scripts/00_generate_minibench.py --all
run_step python3 scripts/01_simulate_observations.py --all --config configs/detector/odi_default.yaml
run_step python3 scripts/02_compute_odi.py --all --config configs/detector/odi_default.yaml
run_step python3 scripts/02_run_toy_lio.py --all --config configs/detector/odi_default.yaml
run_step python3 scripts/03_eval_metrics.py --all --config configs/detector/odi_default.yaml
run_step python3 scripts/05_metric_validity.py --config configs/detector/odi_default.yaml
run_step python3 scripts/04_plot_day14.py --results results/day14 --out results/day14/figures
run_step python3 scripts/06_sensitivity.py --config configs/detector/odi_default.yaml --results results/day14 --out results/day14/tables --figures-out results/day14/figures

END_EPOCH="$(date +%s)"
RUNTIME_SECONDS="$((END_EPOCH - START_EPOCH))"
run_step python3 scripts/07_reproduction_manifest.py \
  --results results/day14 \
  --commands-file "$COMMAND_LOG" \
  --run-id "$RUN_ID" \
  --timestamp "$TIMESTAMP" \
  --runtime-seconds "$RUNTIME_SECONDS" \
  --status OK

echo "Day 14 reproduction complete: run_id=$RUN_ID runtime_seconds=$RUNTIME_SECONDS"
