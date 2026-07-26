#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FAST_WS="${FASTLIO2_WS:-$HOME/fastlio2_ws}"
FAST_ROOT="$FAST_WS/src/FAST_LIO"
BINARY="$FAST_WS/devel/lib/fast_lio/fastlio_mapping"
CONFIG="$ROOT/configs/real_data/mun_frl_lighthouse.yaml"
PILOT_CONFIG="$ROOT/configs/real_data/measurement_pilot.yaml"
INTERVAL_CONFIG="$ROOT/configs/real_data/mun_frl_pilot_intervals.yaml"
BAG="${MUN_FRL_BAG:-}"
RUN_DIR="$ROOT/results/measurement_real_validation/mun_frl_lighthouse_pilot/raw"
RATE="1.0"
ROS_PORT="19831"

usage() {
  echo "usage: $0 [--bag BAG] [--output-dir DIR] [--rate RATE] [--ros-port PORT]" >&2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bag) BAG="$2"; shift 2 ;;
    --output-dir) RUN_DIR="$2"; shift 2 ;;
    --rate) RATE="$2"; shift 2 ;;
    --ros-port) ROS_PORT="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) usage; echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

[[ -n "$BAG" && -f "$BAG" ]] || { echo "provide --bag or MUN_FRL_BAG" >&2; exit 2; }
[[ -x "$BINARY" ]] || { echo "FAST-LIO2 binary is missing: $BINARY" >&2; exit 2; }
[[ ! -e "$RUN_DIR" ]] || { echo "output directory already exists: $RUN_DIR" >&2; exit 2; }
mkdir -p "$RUN_DIR/ros_home" "$RUN_DIR/ros_log" "$RUN_DIR/topic_capture"

# shellcheck disable=SC1091
source /opt/ros/noetic/setup.bash
# shellcheck disable=SC1091
source "$FAST_WS/devel/setup.bash"

export ROS_MASTER_URI="http://127.0.0.1:$ROS_PORT"
export ROS_HOSTNAME="127.0.0.1"
export ROS_HOME="$RUN_DIR/ros_home"
export ROS_LOG_DIR="$RUN_DIR/ros_log"
export OMP_NUM_THREADS=1
export OMP_DYNAMIC=FALSE
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export LC_ALL=C
export LANG=C

BAG_SHA256="$(sha256sum "$BAG" | awk '{print $1}')"
EXPECTED_BAG_SHA256="562bafc57dab7fdac3d8959cf6836b3f4508c4fa60147b11d718552180543162"
[[ "$BAG_SHA256" == "$EXPECTED_BAG_SHA256" ]] || {
  echo "bag SHA-256 does not match frozen Lighthouse sample" >&2; exit 3;
}
BINARY_SHA256="$(sha256sum "$BINARY" | awk '{print $1}')"
CONFIG_BUNDLE_SHA256="$(sha256sum "$CONFIG" "$PILOT_CONFIG" "$INTERVAL_CONFIG" | sha256sum | awk '{print $1}')"
FAST_COMMIT="$(git -C "$FAST_ROOT" rev-parse HEAD)"
INTERVAL_LOCK_SHA256="$(sha256sum "$INTERVAL_CONFIG" | awk '{print $1}')"

ROSCORE_PID=""
FAST_PID=""
CAPTURE_PID=""
BAG_PID=""
cleanup() {
  set +e
  for pid in "$BAG_PID" "$CAPTURE_PID" "$FAST_PID" "$ROSCORE_PID"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill -INT "$pid" 2>/dev/null
      wait "$pid" 2>/dev/null
    fi
  done
}
trap cleanup EXIT INT TERM

roscore -p "$ROS_PORT" > "$RUN_DIR/roscore.log" 2>&1 &
ROSCORE_PID=$!
for _ in $(seq 1 100); do
  rosparam list >/dev/null 2>&1 && break
  sleep 0.1
done
rosparam list >/dev/null 2>&1 || { echo "roscore startup failed" >&2; exit 4; }

rosparam load "$CONFIG" /
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
rosparam set /harmful_bias/runtime_mode COMPACT_EXPORT
rosparam set /harmful_bias/runtime_equivalence_output_dir "$RUN_DIR"
rosparam set /harmful_bias/run_id measurement_real_mun_frl_lighthouse_v1
rosparam set /harmful_bias/sequence_id mun_frl_lighthouse
rosparam set /harmful_bias/bag_sha256 "$BAG_SHA256"
rosparam set /harmful_bias/config_bundle_sha256 "$CONFIG_BUNDLE_SHA256"
rosparam set /harmful_bias/fastlio2_binary_sha256 "$BINARY_SHA256"
rosparam set /harmful_bias/readonly_tap_buffer_capacity 8
rosparam set /harmful_bias/end_of_stream_audit_enabled false
rosparam set /harmful_bias/in_call_immutability_audit_enabled false
rosparam set /harmful_bias/experiment_a_stage_hash_enabled false
rosparam set /harmful_bias/day7_map_update_audit_enabled false
rosparam set /harmful_bias/day8_range_query_audit_enabled false

[[ "$(rosparam get /mapping/extrinsic_est_en)" == "false" ]]
[[ "$(rosparam get /preprocess/lidar_type)" == "2" ]]
[[ "$(rosparam get /preprocess/scan_line)" == "16" ]]
[[ "$(rosparam get /preprocess/timestamp_unit)" == "0" ]]
rosparam dump "$RUN_DIR/rosparams.yaml" /

"$BINARY" > "$RUN_DIR/fastlio2.log" 2>&1 &
FAST_PID=$!
for _ in $(seq 1 300); do
  rosnode info /laserMapping >/dev/null 2>&1 && break
  kill -0 "$FAST_PID" 2>/dev/null || { echo "FAST-LIO2 startup failed" >&2; exit 5; }
  sleep 0.1
done
rosnode info /laserMapping > "$RUN_DIR/rosnode_info_fastlio2.txt"

python3 "$ROOT/scripts/133_capture_mun_frl_offline_topics.py" \
  --output-dir "$RUN_DIR/topic_capture" > "$RUN_DIR/topic_capture.log" 2>&1 &
CAPTURE_PID=$!
for _ in $(seq 1 100); do
  rosnode info /mun_frl_offline_topic_capture >/dev/null 2>&1 && break
  kill -0 "$CAPTURE_PID" 2>/dev/null || { echo "topic capture startup failed" >&2; exit 6; }
  sleep 0.1
done

rosbag play "$BAG" __name:=mun_frl_bag_player \
  --pause --clock --rate "$RATE" --queue=10000 \
  --topics /velodyne_points /imu/data /fix \
  > "$RUN_DIR/rosbag.log" 2>&1 &
BAG_PID=$!
for _ in $(seq 1 300); do
  rosnode info /mun_frl_bag_player >/dev/null 2>&1 && break
  kill -0 "$BAG_PID" 2>/dev/null || { echo "rosbag startup failed" >&2; exit 7; }
  sleep 0.1
done
rosnode info /mun_frl_bag_player > "$RUN_DIR/rosnode_info_bag_player.txt"
rostopic info /velodyne_points > "$RUN_DIR/rostopic_info_velodyne.txt"
rostopic info /imu/data > "$RUN_DIR/rostopic_info_imu.txt"
rosservice call /mun_frl_bag_player/pause_playback "data: false" \
  > "$RUN_DIR/unpause_response.txt"

set +e
wait "$BAG_PID"
BAG_EXIT=$?
BAG_PID=""
set -e
[[ "$BAG_EXIT" -eq 0 ]] || { echo "rosbag play failed: $BAG_EXIT" >&2; exit 7; }
sleep 5

kill -INT "$CAPTURE_PID"
set +e
wait "$CAPTURE_PID"
CAPTURE_EXIT=$?
set -e
CAPTURE_PID=""
[[ "$CAPTURE_EXIT" -eq 0 || "$CAPTURE_EXIT" -eq 130 ]] || {
  echo "topic capture failed: $CAPTURE_EXIT" >&2; exit 8;
}

kill -INT "$FAST_PID"
set +e
wait "$FAST_PID"
FAST_EXIT=$?
set -e
FAST_PID=""
[[ "$FAST_EXIT" -eq 0 || "$FAST_EXIT" -eq 130 ]] || {
  echo "FAST-LIO2 failed: $FAST_EXIT" >&2; exit 9;
}

[[ -s "$RUN_DIR/runtime_audit_v2.bin" ]]
[[ -s "$RUN_DIR/observation_records_v3.bin" ]]
[[ -s "$RUN_DIR/topic_capture/fastlio_odometry.csv" ]]
[[ -s "$RUN_DIR/topic_capture/navsat_fix.csv" ]]
[[ "$(sha256sum "$BINARY" | awk '{print $1}')" == "$BINARY_SHA256" ]]

python3 - "$RUN_DIR/run_input_manifest.json" "$BAG" "$BAG_SHA256" \
  "$BINARY" "$BINARY_SHA256" "$FAST_COMMIT" "$CONFIG_BUNDLE_SHA256" \
  "$INTERVAL_LOCK_SHA256" "$RATE" "$FAST_EXIT" <<'PY'
import json
import pathlib
import sys

output, bag, bag_sha, binary, binary_sha, commit, config_sha, interval_sha, rate, fast_exit = sys.argv[1:]
value = {
    "schema_version": "measurement_real_run_input_manifest_v1",
    "dataset": "MUN-FRL",
    "sequence": "mun_frl_lighthouse",
    "bag_path": str(pathlib.Path(bag).resolve()),
    "bag_sha256": bag_sha,
    "fastlio2_binary_path": str(pathlib.Path(binary).resolve()),
    "fastlio2_binary_sha256": binary_sha,
    "fastlio2_commit": commit,
    "config_bundle_sha256": config_sha,
    "interval_lock_sha256": interval_sha,
    "intervals_frozen_before_detector": True,
    "transport_runtime_mode": "COMPACT_EXPORT",
    "research_runtime_mode": "measurement_mode",
    "bag_playback_rate": float(rate),
    "fastlio2_exit_code": int(fast_exit),
    "fastlio2_crash_count": 0,
    "bag_topics_played": ["/velodyne_points", "/imu/data", "/fix"],
    "bag_odometry_played": False,
    "reference_online_detector_access": False,
}
pathlib.Path(output).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
PY

echo "$RUN_DIR"
