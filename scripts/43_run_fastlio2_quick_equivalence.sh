#!/usr/bin/env bash
set -euo pipefail

RUN_ID=""
SEQUENCE_ID=""
MODE=""
REPEAT_ID=""
OUTPUT_ROOT=""
BINARY_SHA256=""
FAST_CORE=""
BAG_CORE=""
STARTUP_SYNC=false
CLIP_PATH=""
CLIP_SHA256=""

while (($#)); do
  case "$1" in
    --run-id) RUN_ID="$2"; shift 2 ;;
    --sequence-id) SEQUENCE_ID="$2"; shift 2 ;;
    --mode) MODE="$2"; shift 2 ;;
    --repeat-id) REPEAT_ID="$2"; shift 2 ;;
    --output-root) OUTPUT_ROOT="$2"; shift 2 ;;
    --binary-sha256) BINARY_SHA256="$2"; shift 2 ;;
    --fast-core) FAST_CORE="$2"; shift 2 ;;
    --bag-core) BAG_CORE="$2"; shift 2 ;;
    --startup-sync) STARTUP_SYNC=true; shift ;;
    --clip-path) CLIP_PATH="$2"; shift 2 ;;
    --clip-sha256) CLIP_SHA256="$2"; shift 2 ;;
    *) echo "ERROR: unsupported argument: $1" >&2; exit 2 ;;
  esac
done

for value in "$RUN_ID" "$SEQUENCE_ID" "$MODE" "$REPEAT_ID" \
  "$OUTPUT_ROOT" "$BINARY_SHA256" "$FAST_CORE" "$BAG_CORE"; do
  test -n "$value" || { echo "ERROR: all fixed run arguments are required" >&2; exit 2; }
done
if [[ "$STARTUP_SYNC" == true ]]; then
  [[ "$RUN_ID" == "multihyp_day5_startup_sync_v1" ]] || {
    echo "ERROR: startup-sync requires its fresh locked run ID" >&2; exit 2;
  }
  [[ "$MODE" == "AUDIT_ONLY" ]] || {
    echo "ERROR: startup-sync permits AUDIT_ONLY only" >&2; exit 2;
  }
  test -n "$CLIP_PATH" && [[ "$CLIP_SHA256" =~ ^[0-9a-f]{64}$ ]] || {
    echo "ERROR: startup-sync requires a frozen clip path and SHA" >&2; exit 2;
  }
else
  [[ "$RUN_ID" =~ ^multihyp_day5_remediation_(baseline|capture|export)_v1$ ]] || {
    echo "ERROR: only frozen Day 5 remediation phase run IDs are supported" >&2
    exit 2
  }
fi
[[ "$MODE" == "AUDIT_ONLY" || "$MODE" == "CAPTURE_ONLY" || "$MODE" == "COMPACT_EXPORT" ]] || {
  echo "ERROR: invalid runtime mode" >&2; exit 2;
}
[[ "$REPEAT_ID" =~ ^[123]$ ]] || { echo "ERROR: repeat id must be 1, 2, or 3" >&2; exit 2; }
[[ "$BINARY_SHA256" =~ ^[0-9a-f]{64}$ ]] || { echo "ERROR: invalid binary SHA" >&2; exit 2; }
[[ "$FAST_CORE" =~ ^[0-9]+$ && "$BAG_CORE" =~ ^[0-9]+$ && "$FAST_CORE" != "$BAG_CORE" ]] || {
  echo "ERROR: FAST and rosbag require two distinct fixed CPU cores" >&2; exit 2;
}
test "$(nproc)" -ge 2 || { echo "ERROR: fewer than two logical CPU cores" >&2; exit 2; }
OUTPUT_ROOT="$(realpath -m "$OUTPUT_ROOT")"

case "$SEQUENCE_ID" in
  avia_quick_shack)
    BAG_PATH="${HARMFUL_BIAS_QUICK_SHACK_BAG:-$HOME/fastlio2_ws/bags/2020-09-16-quick-shack.bag}"
    BAG_ALIAS="2020-09-16-quick-shack.bag"
    BAG_SHA256="05a56e75898f952766f136d1e5db64a35d202e990e3b1052558369d8384d7ffe"
    CLIP_DURATION="50.001004"
    BAG_MESSAGE_COUNT="10450"
    SEQUENCE_SLOT="1"
    ;;
  avia_outdoor_run_100hz)
    BAG_PATH="${HARMFUL_BIAS_QUICK_OUTDOOR_BAG:-$HOME/fastlio2_ws/bags/outdoor_run_100Hz_2020-12-27-17-12-19.bag}"
    BAG_ALIAS="outdoor_run_100Hz_2020-12-27-17-12-19.bag"
    BAG_SHA256="13bde5d88ce054d88904873e924e2619153efdf5b63df7f3bbab4f16eb72a253"
    CLIP_DURATION="63.857759"
    BAG_MESSAGE_COUNT="21208"
    SEQUENCE_SLOT="2"
    ;;
  *) echo "ERROR: only the two frozen Quick sequence IDs are supported" >&2; exit 2 ;;
esac

ORIGINAL_BAG_SHA256="$BAG_SHA256"
if [[ "$STARTUP_SYNC" == true ]]; then
  BAG_PATH="$(realpath -e "$CLIP_PATH")"
  BAG_ALIAS="$(basename "$BAG_PATH")"
  BAG_SHA256="$CLIP_SHA256"
  BAG_MESSAGE_COUNT="0"
fi

case "$MODE" in
  AUDIT_ONLY) MODE_SLOT="1" ;;
  CAPTURE_ONLY) MODE_SLOT="2" ;;
  COMPACT_EXPORT) MODE_SLOT="3" ;;
esac

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FAST_ROOT="$HOME/fastlio2_ws/src/FAST_LIO"
FAST_WS="$HOME/fastlio2_ws"
BINARY="$FAST_WS/devel/lib/fast_lio/fastlio_mapping"
RUN_LABEL="${MODE}_R${REPEAT_ID}"
RUN_DIR="$OUTPUT_ROOT/$SEQUENCE_ID/$RUN_LABEL"
test ! -e "$RUN_DIR" || { echo "ERROR: run directory already exists: $RUN_DIR" >&2; exit 2; }
mkdir -p "$RUN_DIR" "$RUN_DIR/ros_home" "$RUN_DIR/ros_log"

test -f "$BAG_PATH" && test -s "$BAG_PATH" || { echo "ERROR: frozen bag unavailable" >&2; exit 3; }
test "$(sha256sum "$BAG_PATH" | awk '{print $1}')" = "$BAG_SHA256" || { echo "ERROR: frozen bag SHA mismatch" >&2; exit 3; }
test -x "$BINARY" || { echo "ERROR: FAST-LIO2 binary missing" >&2; exit 4; }
test "$(sha256sum "$BINARY" | awk '{print $1}')" = "$BINARY_SHA256" || { echo "ERROR: locked binary SHA mismatch" >&2; exit 4; }

source /opt/ros/noetic/setup.bash
source "$FAST_WS/devel/setup.bash"
rosbag info --yaml "$BAG_PATH" > "$RUN_DIR/bag_info.yaml"
grep -q '/livox/lidar' "$RUN_DIR/bag_info.yaml"
grep -q '/livox/imu' "$RUN_DIR/bag_info.yaml"

CONFIG_BUNDLE_SHA256="$({ sha256sum "$FAST_ROOT/config/avia.yaml"; sha256sum "$FAST_ROOT/launch/mapping_avia.launch"; } | sha256sum | awk '{print $1}')"
if [[ "$STARTUP_SYNC" == true ]]; then
  ROS_PORT="$((19500 + SEQUENCE_SLOT * 100 + REPEAT_ID))"
else
  ROS_PORT="$((19100 + SEQUENCE_SLOT * 100 + MODE_SLOT * 10 + REPEAT_ID))"
fi
export ROS_MASTER_URI="http://127.0.0.1:$ROS_PORT"
export ROS_HOSTNAME="127.0.0.1"
export ROS_HOME="$RUN_DIR/ros_home"
export ROS_LOG_DIR="$RUN_DIR/ros_log"
export OMP_NUM_THREADS=1
export OMP_DYNAMIC=FALSE
export OMP_SCHEDULE=static
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export LC_ALL=C
export LANG=C

ROSCORE_PID=""
ROSLAUNCH_PID=""
BAG_PID=""
cleanup() {
  set +e
  if [[ -n "$BAG_PID" ]] && kill -0 "$BAG_PID" 2>/dev/null; then
    kill -INT "$BAG_PID" 2>/dev/null
    wait "$BAG_PID" 2>/dev/null
  fi
  if [[ -n "$ROSLAUNCH_PID" ]] && kill -0 "$ROSLAUNCH_PID" 2>/dev/null; then
    kill -INT "$ROSLAUNCH_PID" 2>/dev/null
    wait "$ROSLAUNCH_PID" 2>/dev/null
  fi
  if [[ -n "$ROSCORE_PID" ]] && kill -0 "$ROSCORE_PID" 2>/dev/null; then
    kill -INT "$ROSCORE_PID" 2>/dev/null
    wait "$ROSCORE_PID" 2>/dev/null
  fi
}
trap cleanup EXIT INT TERM

roscore -p "$ROS_PORT" > "$RUN_DIR/roscore.log" 2>&1 &
ROSCORE_PID=$!
for _ in $(seq 1 100); do
  rosparam list >/dev/null 2>&1 && break
  sleep 0.1
done
rosparam list >/dev/null 2>&1 || { echo "ERROR: roscore did not become ready" >&2; exit 5; }

rosparam load "$FAST_ROOT/config/avia.yaml" /
test "$(rosparam get /mapping/extrinsic_est_en)" = "false" || {
  echo "ERROR: frozen config has extrinsic estimation enabled" >&2; exit 5;
}
rosparam set /use_sim_time true
rosparam set /feature_extract_enable false
rosparam set /point_filter_num 3
rosparam set /max_iteration 3
rosparam set /filter_size_surf 0.5
rosparam set /filter_size_map 0.5
rosparam set /cube_side_length 1000.0
rosparam set /runtime_pos_log_enable false
rosparam set /publish/path_en false
rosparam set /publish/scan_publish_en false
rosparam set /publish/dense_publish_en false
rosparam set /publish/scan_bodyframe_pub_en false
rosparam set /pcd_save/pcd_save_en false
rosparam set /harmful_bias/runtime_mode "$MODE"
rosparam set /harmful_bias/runtime_equivalence_output_dir "$RUN_DIR"
rosparam set /harmful_bias/run_id "${RUN_ID}_${SEQUENCE_ID}_${RUN_LABEL}"
rosparam set /harmful_bias/sequence_id "$SEQUENCE_ID"
rosparam set /harmful_bias/bag_sha256 "$BAG_SHA256"
rosparam set /harmful_bias/config_bundle_sha256 "$CONFIG_BUNDLE_SHA256"
rosparam set /harmful_bias/fastlio2_binary_sha256 "$BINARY_SHA256"

tee "$RUN_DIR/day5_runtime.launch" >/dev/null <<'EOF'
<launch>
  <node pkg="fast_lio" type="fastlio_mapping" name="laserMapping" output="screen" required="true" />
</launch>
EOF
taskset -c "$FAST_CORE" roslaunch "$RUN_DIR/day5_runtime.launch" > "$RUN_DIR/roslaunch.log" 2>&1 &
ROSLAUNCH_PID=$!
taskset -pc "$ROSLAUNCH_PID" > "$RUN_DIR/fast_cpu_affinity.txt"
for _ in $(seq 1 300); do
  rosnode info /laserMapping >/dev/null 2>&1 && break
  kill -0 "$ROSLAUNCH_PID" 2>/dev/null || { echo "ERROR: FAST-LIO2 exited during startup" >&2; exit 6; }
  sleep 0.1
done
rosnode info /laserMapping > "$RUN_DIR/rosnode_info.txt"
rosparam dump "$RUN_DIR/rosparams.yaml" /
env | LC_ALL=C sort > "$RUN_DIR/runtime_environment.txt"

if [[ "$STARTUP_SYNC" == true ]]; then
  printf 'taskset -c %s rosbag play %s --pause --clock --rate 0.25 --queue=10000 __name:=day5_bag_player\n' \
    "$BAG_CORE" "$BAG_ALIAS" > "$RUN_DIR/bag_command.txt"
  taskset -c "$BAG_CORE" rosbag play "$BAG_PATH" --pause --clock --rate 0.25 --queue=10000 \
    __name:=day5_bag_player > "$RUN_DIR/rosbag.log" 2>&1 &
  BAG_PID=$!
  taskset -pc "$BAG_PID" > "$RUN_DIR/rosbag_cpu_affinity.txt"
  python3 "$ROOT/scripts/48_wait_rosbag_connections.py" \
    --run-id "$RUN_ID" --sequence-id "$SEQUENCE_ID" --repeat-id "$REPEAT_ID" \
    --master-uri "$ROS_MASTER_URI" --stable-polls 20 --poll-interval 0.1 --timeout 30 \
    --output "$RUN_DIR/connection_handshake.json"
  rosnode info /laserMapping > "$RUN_DIR/rosnode_info_laser_mapping.txt"
  rosnode info /day5_bag_player > "$RUN_DIR/rosnode_info_bag_player.txt"
  rostopic info /livox/lidar > "$RUN_DIR/rostopic_info_livox_lidar.txt"
  rostopic info /livox/imu > "$RUN_DIR/rostopic_info_livox_imu.txt"
  rosservice list > "$RUN_DIR/rosservice_list.txt"
  {
    rosservice type /day5_bag_player/pause_playback
    rosservice uri /day5_bag_player/pause_playback
  } > "$RUN_DIR/rosservice_info_pause_playback.txt"
  test "$(head -1 "$RUN_DIR/rosservice_info_pause_playback.txt")" = "std_srvs/SetBool" || {
    echo "ERROR: wrong pause service type" >&2; exit 7;
  }
  UNPAUSE_NS="$(date +%s%N)"
  set +e
  rosservice call /day5_bag_player/pause_playback "data: false" \
    > "$RUN_DIR/pause_service_response.txt" 2>&1
  UNPAUSE_STATUS=$?
  set -e
  grep -Eq 'success: (True|true)' "$RUN_DIR/pause_service_response.txt" || UNPAUSE_STATUS=1
  python3 - "$RUN_DIR/connection_handshake.json" "$UNPAUSE_NS" "$UNPAUSE_STATUS" <<'PY'
import json, pathlib, sys
path = pathlib.Path(sys.argv[1])
value = json.loads(path.read_text())
value["unpause_monotonic_ns"] = int(sys.argv[2])
value["pause_service_response"] = pathlib.Path(path.parent / "pause_service_response.txt").read_text()
value["unpause_success"] = int(sys.argv[3]) == 0
if not value["unpause_success"]:
    value["handshake_pass"] = False
    value["failure_reason"] = "PAUSE_SERVICE_CALL_FAILED"
path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
PY
  test "$UNPAUSE_STATUS" -eq 0 || { echo "ERROR: pause service unpause failed" >&2; exit 7; }
  set +e
  wait "$BAG_PID"
  ROSBAG_EXIT_CODE=$?
  BAG_PID=""
  set -e
else
  printf 'taskset -c %s rosbag play --clock --rate 0.25 --start 0.0 --duration %s %s\n' \
    "$BAG_CORE" "$CLIP_DURATION" "$BAG_ALIAS" > "$RUN_DIR/bag_command.txt"
  set +e
  taskset -c "$BAG_CORE" rosbag play --clock --rate 0.25 --start 0.0 --duration "$CLIP_DURATION" "$BAG_PATH" \
    > "$RUN_DIR/rosbag.log" 2>&1 &
  BAG_PID=$!
  taskset -pc "$BAG_PID" > "$RUN_DIR/rosbag_cpu_affinity.txt"
  wait "$BAG_PID"
  ROSBAG_EXIT_CODE=$?
  BAG_PID=""
  set -e
fi
test "$ROSBAG_EXIT_CODE" -eq 0 || { echo "ERROR: rosbag play failed" >&2; exit 7; }
sleep 5

kill -INT "$ROSLAUNCH_PID"
sleep 1
if kill -0 "$ROSLAUNCH_PID" 2>/dev/null; then
  rosnode kill /laserMapping > "$RUN_DIR/rosnode_shutdown.txt" 2>&1 || true
fi
set +e
wait "$ROSLAUNCH_PID"
ROSLAUNCH_EXIT_CODE=$?
set -e
ROSLAUNCH_PID=""
[[ "$ROSLAUNCH_EXIT_CODE" -eq 0 || "$ROSLAUNCH_EXIT_CODE" -eq 130 ]] || {
  echo "ERROR: FAST-LIO2/roslaunch exit code $ROSLAUNCH_EXIT_CODE" >&2; exit 8;
}
test "$(sha256sum "$BINARY" | awk '{print $1}')" = "$BINARY_SHA256" || { echo "ERROR: binary changed during replay" >&2; exit 9; }
test -s "$RUN_DIR/runtime_audit_v2.bin"
test -s "$RUN_DIR/run_summary.json"
test -s "$RUN_DIR/final_map_summary.json"
test -s "$RUN_DIR/tap_export_summary.json"

CONVERTER_ARGS=(
  --runtime-audit "$RUN_DIR/runtime_audit_v2.bin"
  --output-dir "$RUN_DIR/converted"
)
if [[ "$MODE" == "COMPACT_EXPORT" ]]; then
  test -s "$RUN_DIR/observation_records_v3.bin"
  CONVERTER_ARGS+=(--observations "$RUN_DIR/observation_records_v3.bin")
else
  test ! -e "$RUN_DIR/observation_records_v3.bin"
fi
CONVERSION_START_NS="$(date +%s%N)"
python3 "$ROOT/scripts/46_convert_fastlio2_runtime_binary.py" "${CONVERTER_ARGS[@]}" \
  > "$RUN_DIR/binary_conversion.log" 2>&1
CONVERSION_RUNTIME_NS="$(( $(date +%s%N) - CONVERSION_START_NS ))"
test -s "$RUN_DIR/converted/runtime_frames.csv"
if [[ "$MODE" == "COMPACT_EXPORT" ]]; then
  python3 "$ROOT/scripts/45_evaluate_fastlio2_runtime_records.py" \
    --input "$RUN_DIR/converted/observation_records_v3.jsonl" \
    --output-dir "$RUN_DIR/detector" > "$RUN_DIR/detector.log" 2>&1
fi

RUNTIME_ROW_COUNT="$(awk 'END {print NR-1}' "$RUN_DIR/converted/runtime_frames.csv")"
OBSERVATION_ROW_COUNT="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["observation_record_count"])' "$RUN_DIR/converted/binary_conversion_summary.json")"
tee "$RUN_DIR/run_metadata.json" >/dev/null <<EOF
{
  "run_id": "${RUN_ID}_${SEQUENCE_ID}_${RUN_LABEL}",
  "phase_run_id": "$RUN_ID",
  "sequence_id": "$SEQUENCE_ID",
  "runtime_mode": "$MODE",
  "repeat_id": $REPEAT_ID,
  "local_alias": "$BAG_ALIAS",
  "bag_sha256": "$BAG_SHA256",
  "original_bag_sha256": "$ORIGINAL_BAG_SHA256",
  "bag_message_count": $BAG_MESSAGE_COUNT,
  "clip_start_sec": 0.0,
  "clip_duration_sec": $CLIP_DURATION,
  "playback_rate": 0.25,
  "use_clock": true,
  "ros_master_port": $ROS_PORT,
  "fast_cpu_core": $FAST_CORE,
  "rosbag_cpu_core": $BAG_CORE,
  "rosbag_exit_code": $ROSBAG_EXIT_CODE,
  "roslaunch_exit_code": $ROSLAUNCH_EXIT_CODE,
  "runtime_audit_row_count": $RUNTIME_ROW_COUNT,
  "observation_record_count": $OBSERVATION_ROW_COUNT,
  "offline_conversion_runtime_ns": $CONVERSION_RUNTIME_NS,
  "fastlio2_binary_sha256_before": "$BINARY_SHA256",
  "fastlio2_binary_sha256_after": "$BINARY_SHA256",
  "config_bundle_sha256": "$CONFIG_BUNDLE_SHA256"
}
EOF

kill -INT "$ROSCORE_PID"
set +e
wait "$ROSCORE_PID"
set -e
ROSCORE_PID=""
trap - EXIT INT TERM
if [[ "$STARTUP_SYNC" == true ]]; then
  echo "DAY5_STARTUP_SYNC_REPLAY_COMPLETE=$SEQUENCE_ID/$RUN_LABEL"
else
  echo "DAY5_REMEDIATION_REPLAY_COMPLETE=$SEQUENCE_ID/$RUN_LABEL"
fi
