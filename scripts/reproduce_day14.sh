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

declare -A CONFIGS=(
  ["OC-L0-S01-M1"]="configs/minibench/OC-L0-S01-M1.yaml"
  ["ST-L3-S01-M1"]="configs/minibench/ST-L3-S01-M1.yaml"
  ["CT-L2-S01-M2"]="configs/minibench/CT-L2-S01-M2.yaml"
  ["RT-L4-S01-M1"]="configs/minibench/RT-L4-S01-M1.yaml"
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
  check_env
  gen_OC / gen_ST / gen_CT / gen_RT
  obs_OC / obs_ST / obs_CT / obs_RT
  02_compute_odi --all
  02_run_toy_lio --all
  03_eval_metrics --all
  05_metric_validity --n-boot "$REPRO_N_BOOT"
  04_plot_day14 real rendering
  06_sensitivity real computation --n-boot "$REPRO_N_BOOT"
  07_reproduction_manifest
Each step uses timeout --kill-after=10s "$STEP_TIMEOUT_SECONDS"s and writes stdout/stderr logs.
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
  scripts/07_reproduction_manifest.py \
  scripts/prewarm_matplotlib.py; do
  if [[ ! -f "$script" ]]; then
    echo "Missing required script: $script" >&2
    exit 3
  fi
done

START_EPOCH="$(date +%s)"

clean_generated() {
  for dir in raw metrics tables figures manifests; do
    mkdir -p "results/day14/$dir"
    find "results/day14/$dir" -mindepth 1 -maxdepth 1 ! -name ".gitkeep" ! -name "manifest_template.json" -exec rm -rf {} + || true
  done
  for seq in "${SEQUENCES[@]}"; do
    rm -rf "data/minibench/$seq" || true
  done
}

ensure_manifest_template() {
  local template_path="results/day14/manifests/manifest_template.json"
  if [[ -f "$template_path" ]]; then
    return
  fi
  cat > "$template_path" <<'EOF'
{
  "run_id": "",
  "date": "",
  "git_commit": "",
  "config_hash": "",
  "sequence_id": "",
  "random_seed": 42,
  "command": "",
  "input_files": [],
  "output_files": [],
  "status": ""
}

EOF
}

clean_generated
ensure_manifest_template

MANIFEST_DIR="results/day14/manifests"
LOG_DIR="$MANIFEST_DIR/logs/$RUN_ID"
mkdir -p "$LOG_DIR"
COMMAND_LOG="$MANIFEST_DIR/day14_commands_${RUN_ID}.txt"
STEP_STATUS="$MANIFEST_DIR/day14_step_status_${RUN_ID}.csv"
: > "$COMMAND_LOG"
printf 'step_name,command,start_time,end_time,runtime_seconds,return_code,timeout,stdout_log_path,stderr_log_path\n' > "$STEP_STATUS"
export MPLCONFIGDIR="$MANIFEST_DIR/mplconfig_${RUN_ID}"
mkdir -p "$MPLCONFIGDIR"

tail_logs() {
  local stdout_path="$1"
  local stderr_path="$2"
  echo "--- stdout last 100 lines: $stdout_path ---" >&2
  if [[ -f "$stdout_path" ]]; then
    timeout 5s tail -n 100 "$stdout_path" >&2 || true
  fi
  echo "--- stderr last 100 lines: $stderr_path ---" >&2
  if [[ -f "$stderr_path" ]]; then
    timeout 5s tail -n 100 "$stderr_path" >&2 || true
  fi
}

write_manifest() {
  local status="$1"
  local failed_step="${2:-}"
  local return_code="${3:-0}"
  local timeout_flag="${4:-false}"
  local stdout_path="${5:-}"
  local stderr_path="${6:-}"
  local now_epoch runtime
  now_epoch="$(date +%s)"
  runtime="$((now_epoch - START_EPOCH))"
  python3 scripts/07_reproduction_manifest.py \
    --results results/day14 \
    --commands-file "$COMMAND_LOG" \
    --run-id "$RUN_ID" \
    --timestamp "$TIMESTAMP" \
    --runtime-seconds "$runtime" \
    --status "$status" \
    --failed-step "$failed_step" \
    --return-code "$return_code" \
    --timeout "$timeout_flag" \
    --step-status-csv "$STEP_STATUS" \
    --stdout-log-path "$stdout_path" \
    --stderr-log-path "$stderr_path"
}

run_step() {
  local step_name="$1"
  shift
  local stdout_path="$LOG_DIR/${step_name}.stdout.log"
  local stderr_path="$LOG_DIR/${step_name}.stderr.log"
  local command_text="$*"
  local start_time end_time start_epoch end_epoch runtime status timeout_flag

  start_time="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  start_epoch="$(date +%s)"
  echo "RUN step=${step_name} timeout=${STEP_TIMEOUT_SECONDS}s command=${command_text}" >> "$COMMAND_LOG"
  echo "+ [${step_name}] timeout=${STEP_TIMEOUT_SECONDS}s ${command_text}"

  set +e
  timeout --kill-after=10s "${STEP_TIMEOUT_SECONDS}s" "$@" >"$stdout_path" 2>"$stderr_path"
  status=$?
  set -e

  end_epoch="$(date +%s)"
  end_time="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  runtime="$((end_epoch - start_epoch))"
  timeout_flag="false"
  if [[ "$status" -eq 124 || "$status" -eq 137 ]]; then
    timeout_flag="true"
  fi

  printf '%s,%s,%s,%s,%s,%s,%s,%s,%s\n' \
    "$step_name" "$command_text" "$start_time" "$end_time" "$runtime" "$status" "$timeout_flag" "$stdout_path" "$stderr_path" >> "$STEP_STATUS"

  if [[ "$status" -ne 0 ]]; then
    echo "FAILED step=${step_name} return_code=${status} timeout=${timeout_flag} runtime_seconds=${runtime}" >> "$COMMAND_LOG"
    echo "ERROR: step failed: ${step_name} return_code=${status} timeout=${timeout_flag}" >&2
    tail_logs "$stdout_path" "$stderr_path"
    write_manifest FAILED "$step_name" "$status" "$timeout_flag" "$stdout_path" "$stderr_path" || true
    exit "$status"
  fi
  echo "OK step=${step_name} return_code=0 runtime_seconds=${runtime}" >> "$COMMAND_LOG"
}

run_step check_env python3 scripts/check_env.py

for seq in "${SEQUENCES[@]}"; do
  short="${seq%%-*}"
  run_step "gen_${short}" python3 scripts/00_generate_minibench.py --config "${CONFIGS[$seq]}" --out "data/minibench/$seq"
done

for seq in "${SEQUENCES[@]}"; do
  short="${seq%%-*}"
  run_step "obs_${short}" python3 scripts/01_simulate_observations.py --seq "data/minibench/$seq" --config configs/detector/odi_default.yaml
done

run_step compute_odi python3 scripts/02_compute_odi.py --all --config configs/detector/odi_default.yaml
run_step run_toy_lio python3 scripts/02_run_toy_lio.py --all --config configs/detector/odi_default.yaml
run_step eval_metrics python3 scripts/03_eval_metrics.py --all --config configs/detector/odi_default.yaml
run_step metric_validity python3 scripts/05_metric_validity.py --config configs/detector/odi_default.yaml --n-boot "$REPRO_N_BOOT"
echo "BEFORE_PREWARM: skipped; prewarm_matplotlib is not a mandatory reproduction step" >> "$COMMAND_LOG"
echo "AFTER_PREWARM_TIMEOUT_RETURN: skipped; no timeout subprocess launched" >> "$COMMAND_LOG"

plot_stdout_path="$LOG_DIR/plot_day14.stdout.log"
plot_stderr_path="$LOG_DIR/plot_day14.stderr.log"
plot_start_time="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
plot_start_epoch="$(date +%s)"
echo "RUN step=plot_day14 timeout=${STEP_TIMEOUT_SECONDS}s command=plot_day14" >> "$COMMAND_LOG"
echo "+ [plot_day14] timeout=${STEP_TIMEOUT_SECONDS}s plot_day14"
set +e
bash scripts/run_plot_day14_step.sh \
  results/day14 \
  results/day14/figures \
  "$plot_stdout_path" \
  "$plot_stderr_path" \
  "$STEP_TIMEOUT_SECONDS"
plot_rc=$?
set -e
plot_end_epoch="$(date +%s)"
plot_end_time="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
plot_runtime="$((plot_end_epoch - plot_start_epoch))"
plot_timeout="false"
if [[ "$plot_rc" -eq 124 || "$plot_rc" -eq 137 ]]; then
  plot_timeout="true"
fi
printf '%s,%s,%s,%s,%s,%s,%s,%s,%s\n' \
  "plot_day14" "plot_day14" "$plot_start_time" "$plot_end_time" "$plot_runtime" "$plot_rc" "$plot_timeout" "$plot_stdout_path" "$plot_stderr_path" >> "$STEP_STATUS"
if [[ "$plot_rc" -ne 0 ]]; then
  echo "FAILED step=plot_day14 return_code=${plot_rc} timeout=${plot_timeout} runtime_seconds=${plot_runtime}" >> "$COMMAND_LOG"
  echo "ERROR: step failed: plot_day14 return_code=${plot_rc} timeout=${plot_timeout}" >&2
  tail_logs "$plot_stdout_path" "$plot_stderr_path"
  write_manifest FAILED "plot_day14" "$plot_rc" "$plot_timeout" "$plot_stdout_path" "$plot_stderr_path" || true
  exit "$plot_rc"
fi
echo "OK step=plot_day14 return_code=0 runtime_seconds=${plot_runtime}" >> "$COMMAND_LOG"

sensitivity_stdout_path="$LOG_DIR/sensitivity.stdout.log"
sensitivity_stderr_path="$LOG_DIR/sensitivity.stderr.log"
sensitivity_start_time="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
sensitivity_start_epoch="$(date +%s)"
echo "RUN step=sensitivity timeout=${STEP_TIMEOUT_SECONDS}s command=sensitivity" >> "$COMMAND_LOG"
echo "+ [sensitivity] timeout=${STEP_TIMEOUT_SECONDS}s sensitivity"
set +e
bash scripts/run_sensitivity_step.sh \
  results/day14 \
  data/minibench \
  results/day14/tables \
  results/day14/figures \
  "$sensitivity_stdout_path" \
  "$sensitivity_stderr_path" \
  "$STEP_TIMEOUT_SECONDS" \
  "$REPRO_N_BOOT"
sensitivity_rc=$?
set -e
sensitivity_end_epoch="$(date +%s)"
sensitivity_end_time="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
sensitivity_runtime="$((sensitivity_end_epoch - sensitivity_start_epoch))"
sensitivity_timeout="false"
if [[ "$sensitivity_rc" -eq 124 || "$sensitivity_rc" -eq 137 ]]; then
  sensitivity_timeout="true"
fi
printf '%s,%s,%s,%s,%s,%s,%s,%s,%s\n' \
  "sensitivity" "sensitivity" "$sensitivity_start_time" "$sensitivity_end_time" "$sensitivity_runtime" "$sensitivity_rc" "$sensitivity_timeout" "$sensitivity_stdout_path" "$sensitivity_stderr_path" >> "$STEP_STATUS"
if [[ "$sensitivity_rc" -ne 0 ]]; then
  echo "FAILED step=sensitivity return_code=${sensitivity_rc} timeout=${sensitivity_timeout} runtime_seconds=${sensitivity_runtime}" >> "$COMMAND_LOG"
  echo "ERROR: step failed: sensitivity return_code=${sensitivity_rc} timeout=${sensitivity_timeout}" >&2
  tail_logs "$sensitivity_stdout_path" "$sensitivity_stderr_path"
  write_manifest FAILED "sensitivity" "$sensitivity_rc" "$sensitivity_timeout" "$sensitivity_stdout_path" "$sensitivity_stderr_path" || true
  exit "$sensitivity_rc"
fi
echo "OK step=sensitivity return_code=0 runtime_seconds=${sensitivity_runtime}" >> "$COMMAND_LOG"

END_EPOCH="$(date +%s)"
RUNTIME_SECONDS="$((END_EPOCH - START_EPOCH))"
run_step reproduction_manifest python3 scripts/07_reproduction_manifest.py \
  --results results/day14 \
  --commands-file "$COMMAND_LOG" \
  --run-id "$RUN_ID" \
  --timestamp "$TIMESTAMP" \
  --runtime-seconds "$RUNTIME_SECONDS" \
  --status OK \
  --step-status-csv "$STEP_STATUS"

echo "Day 14 reproduction complete: run_id=$RUN_ID runtime_seconds=$RUNTIME_SECONDS"
echo "step status: $STEP_STATUS"
