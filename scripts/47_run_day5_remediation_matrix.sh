#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_ROOT="$ROOT/results/harmful_bias_multihyp_dev/day5_remediation/multihyp_day5_remediation_v1"
LOCK="$RUN_ROOT/day5_remediation_run_lock.json"
RUNNER="$ROOT/scripts/43_run_fastlio2_quick_equivalence.sh"
COMPARATOR="$ROOT/scripts/44_compare_fastlio2_quick_equivalence.py"

test -f "$LOCK" || { echo "ERROR: frozen remediation run lock is missing" >&2; exit 2; }
test ! -e "$RUN_ROOT/matrix_started.marker" || {
  echo "ERROR: remediation run-id has already been used; refusing continuation" >&2
  exit 2
}
touch "$RUN_ROOT/matrix_started.marker"
mkdir -p "$RUN_ROOT/runs"

readarray -t LOCK_VALUES < <(python3 - "$LOCK" <<'PY'
import json, sys
lock = json.load(open(sys.argv[1], encoding="utf-8"))
print(lock["binary_sha256"])
print(lock["cpu_affinity"]["fastlio2_core"])
print(lock["cpu_affinity"]["rosbag_core"])
PY
)
BINARY_SHA256="${LOCK_VALUES[0]}"
FAST_CORE="${LOCK_VALUES[1]}"
BAG_CORE="${LOCK_VALUES[2]}"

verify_lock() {
  local output_path="$1"
  python3 - "$LOCK" "$output_path" "$ROOT" "$HOME/fastlio2_ws/src/FAST_LIO" "$HOME/fastlio2_ws/devel/lib/fast_lio/fastlio_mapping" <<'PY'
import hashlib, json, pathlib, subprocess, sys
lock_path, output_path, degen_root, fast_root, binary = sys.argv[1:]
lock = json.load(open(lock_path, encoding="utf-8"))
roots = {"degen": pathlib.Path(degen_root), "fastlio2": pathlib.Path(fast_root)}
mismatches = []
for group, root in roots.items():
    for relative, expected in lock[f"{group}_source_hashes"].items():
        path = root / relative
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if actual != expected:
            mismatches.append({"group": group, "path": relative, "expected": expected, "actual": actual})
actual_binary = hashlib.sha256(pathlib.Path(binary).read_bytes()).hexdigest()
if actual_binary != lock["binary_sha256"]:
    mismatches.append({"group": "binary", "path": "fastlio_mapping", "expected": lock["binary_sha256"], "actual": actual_binary})

def changed(root):
    raw = subprocess.check_output(["git", "-C", str(root), "status", "--porcelain"], text=True)
    values = []
    for line in raw.splitlines():
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        values.append(path.rstrip("/"))
    return values

degen_changed = changed(roots["degen"])
fast_changed = changed(roots["fastlio2"])
scope_failures = [
    {"group": "degen", "path": path}
    for path in degen_changed
    if not any(path == allowed or path.startswith(allowed.rstrip("/") + "/") for allowed in lock["allowed_degen_paths"])
] + [
    {"group": "fastlio2", "path": path}
    for path in fast_changed
    if not any(path == allowed or path.startswith(allowed.rstrip("/") + "/") for allowed in lock["allowed_fastlio2_paths"])
]
result = {
    "all_locked_hashes_match": not mismatches,
    "binary_sha256": actual_binary,
    "mismatches": mismatches,
    "day5_diff_scope_pass": not scope_failures,
    "scope_failures": scope_failures,
    "degen_changed_paths": degen_changed,
    "fastlio2_changed_paths": fast_changed,
}
pathlib.Path(output_path).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
if mismatches or scope_failures:
    raise SystemExit(1)
PY
}

run_one() {
  local phase_run_id="$1"
  local phase_root="$2"
  local sequence="$3"
  local mode="$4"
  local repeat="$5"
  verify_lock "$RUN_ROOT/pre_${phase_run_id}_${sequence}_${mode}_R${repeat}_lock.json"
  printf '%s\n' \
    "$RUNNER --run-id $phase_run_id --sequence-id $sequence --mode $mode --repeat-id $repeat --output-root $phase_root --binary-sha256 $BINARY_SHA256 --fast-core $FAST_CORE --bag-core $BAG_CORE" \
    >> "$RUN_ROOT/replay_commands.txt"
  "$RUNNER" \
    --run-id "$phase_run_id" \
    --sequence-id "$sequence" \
    --mode "$mode" \
    --repeat-id "$repeat" \
    --output-root "$phase_root" \
    --binary-sha256 "$BINARY_SHA256" \
    --fast-core "$FAST_CORE" \
    --bag-core "$BAG_CORE"
  verify_lock "$RUN_ROOT/post_${phase_run_id}_${sequence}_${mode}_R${repeat}_lock.json"
}

aggregate_failure() {
  verify_lock "$RUN_ROOT/post_run_lock_verification.json" || true
  set +e
  python3 "$COMPARATOR" --aggregate --output-root "$RUN_ROOT" \
    > "$RUN_ROOT/aggregate.log" 2>&1
  set -e
}

BASELINE_ROOT="$RUN_ROOT/runs/baseline"
for sequence in avia_quick_shack avia_outdoor_run_100hz; do
  run_one multihyp_day5_remediation_baseline_v1 "$BASELINE_ROOT" "$sequence" AUDIT_ONLY 1
  run_one multihyp_day5_remediation_baseline_v1 "$BASELINE_ROOT" "$sequence" AUDIT_ONLY 2
  run_one multihyp_day5_remediation_baseline_v1 "$BASELINE_ROOT" "$sequence" AUDIT_ONLY 3
done
set +e
python3 "$COMPARATOR" --phase baseline --phase-root "$BASELINE_ROOT" --output-root "$RUN_ROOT" \
  > "$RUN_ROOT/baseline_compare.log" 2>&1
BASELINE_STATUS=$?
set -e
if [[ "$BASELINE_STATUS" -ne 0 ]]; then
  aggregate_failure
  echo "DAY5_REMEDIATION_STOPPED=BASELINE_RUNTIME_NONDETERMINISM" >&2
  exit 20
fi

CAPTURE_ROOT="$RUN_ROOT/runs/capture"
for sequence in avia_quick_shack avia_outdoor_run_100hz; do
  run_one multihyp_day5_remediation_capture_v1 "$CAPTURE_ROOT" "$sequence" AUDIT_ONLY 1
  run_one multihyp_day5_remediation_capture_v1 "$CAPTURE_ROOT" "$sequence" CAPTURE_ONLY 1
  run_one multihyp_day5_remediation_capture_v1 "$CAPTURE_ROOT" "$sequence" CAPTURE_ONLY 2
  run_one multihyp_day5_remediation_capture_v1 "$CAPTURE_ROOT" "$sequence" AUDIT_ONLY 2
done
set +e
python3 "$COMPARATOR" --phase capture --phase-root "$CAPTURE_ROOT" --output-root "$RUN_ROOT" \
  > "$RUN_ROOT/capture_compare.log" 2>&1
CAPTURE_STATUS=$?
set -e
if [[ "$CAPTURE_STATUS" -ne 0 ]]; then
  aggregate_failure
  echo "DAY5_REMEDIATION_STOPPED=TAP_CAPTURE_SIDE_EFFECT_OR_SCHEDULING" >&2
  exit 21
fi

EXPORT_ROOT="$RUN_ROOT/runs/export"
for sequence in avia_quick_shack avia_outdoor_run_100hz; do
  run_one multihyp_day5_remediation_export_v1 "$EXPORT_ROOT" "$sequence" AUDIT_ONLY 1
  run_one multihyp_day5_remediation_export_v1 "$EXPORT_ROOT" "$sequence" COMPACT_EXPORT 1
  run_one multihyp_day5_remediation_export_v1 "$EXPORT_ROOT" "$sequence" COMPACT_EXPORT 2
  run_one multihyp_day5_remediation_export_v1 "$EXPORT_ROOT" "$sequence" AUDIT_ONLY 2
done
set +e
python3 "$COMPARATOR" --phase export --phase-root "$EXPORT_ROOT" --output-root "$RUN_ROOT" \
  > "$RUN_ROOT/export_compare.log" 2>&1
EXPORT_STATUS=$?
set -e
if [[ "$EXPORT_STATUS" -ne 0 ]]; then
  aggregate_failure
  echo "DAY5_REMEDIATION_STOPPED=EXPORT_SIDE_EFFECT_OR_SCHEDULING" >&2
  exit 22
fi

verify_lock "$RUN_ROOT/post_run_lock_verification.json"
python3 "$COMPARATOR" --aggregate --output-root "$RUN_ROOT" \
  > "$RUN_ROOT/aggregate.log" 2>&1
echo "DAY5_REMEDIATION_MATRIX_COMPLETE=true"
