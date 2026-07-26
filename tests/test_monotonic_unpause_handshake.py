import importlib.util
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module():
    spec = importlib.util.spec_from_file_location("monotonic_handshake", ROOT / "scripts/48_wait_rosbag_connections.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


M = load_module()


def snapshot():
    return {
        "publisher_state": [["/livox/lidar", ["/day5_bag_player"]], ["/livox/imu", ["/day5_bag_player"]]],
        "subscriber_state": [["/livox/lidar", ["/laserMapping"]], ["/livox/imu", ["/laserMapping"]]],
        "service_state": [["/day5_bag_player/pause_playback", ["/day5_bag_player"]]],
        "publisher_bus_info": [[1, "/laserMapping", "o", "TCPROS", "/livox/lidar", True, []], [2, "/laserMapping", "o", "TCPROS", "/livox/imu", True, []]],
        "subscriber_bus_info": [[3, "/day5_bag_player", "i", "TCPROS", "/livox/lidar", True, []], [4, "/day5_bag_player", "i", "TCPROS", "/livox/imu", True, []]],
        "pause_service_type": "std_srvs/SetBool",
        "bag_player_node_uri": "/day5_bag_player",
    }


def service_result(success=True, start=30, end=40):
    return {
        "unpause_call_start_monotonic_ns": start,
        "unpause_call_end_monotonic_ns": end,
        "unpause_wall_time_utc": "2026-07-17T02:00:00+00:00",
        "pause_service_name": M.PAUSE_SERVICE,
        "pause_service_type": M.PAUSE_SERVICE_TYPE,
        "request": {"data": False},
        "response_success": success,
        "response_message": "Playback is now resumed" if success else "failed",
        "pause_service_response": "success: True" if success else "success: False",
        "subprocess_returncode": 0,
        "service_exception": None,
        "unpause_success": success,
    }


def test_four_monotonic_fields_are_ordered_and_wall_time_is_zoned():
    ticks = iter([10, 11, 20])
    result = M.perform_handshake_and_unpause(
        snapshot,
        stable_poll_required=1,
        poll_interval_seconds=0.1,
        timeout_seconds=1,
        monotonic_ns=lambda: next(ticks),
        sleep=lambda _: None,
        unpause=lambda: service_result(),
    )
    assert result["handshake_start_monotonic_ns"] <= result["handshake_ready_monotonic_ns"] <= result["unpause_call_start_monotonic_ns"] <= result["unpause_call_end_monotonic_ns"]
    assert datetime.fromisoformat(result["unpause_wall_time_utc"]).tzinfo is not None
    assert result["unpause_success"] is True


def test_service_failure_turns_handshake_into_failure():
    ticks = iter([10, 11, 20])
    result = M.perform_handshake_and_unpause(
        snapshot,
        stable_poll_required=1,
        poll_interval_seconds=0.1,
        timeout_seconds=1,
        monotonic_ns=lambda: next(ticks),
        sleep=lambda _: None,
        unpause=lambda: service_result(False),
    )
    assert result["handshake_pass"] is False
    assert result["failure_reason"] == "PAUSE_SERVICE_CALL_FAILED"


def test_real_service_wrapper_brackets_call_with_python_monotonic_clock():
    class Completed:
        returncode = 0
        stdout = 'success: True\nmessage: "Playback is now resumed"\n'

    calls = []
    ticks = iter([100, 200])
    result = M.invoke_unpause_service(
        monotonic_ns=lambda: next(ticks),
        wall_now=lambda: datetime(2026, 7, 17, tzinfo=timezone.utc),
        command_runner=lambda *args, **kwargs: calls.append((args, kwargs)) or Completed(),
    )
    assert result["unpause_call_start_monotonic_ns"] == 100
    assert result["unpause_call_end_monotonic_ns"] == 200
    assert result["unpause_success"] is True
    assert calls[0][0][0][:3] == ["rosservice", "call", M.PAUSE_SERVICE]


def test_v2_runner_has_no_shell_clock_or_duplicate_pause_call():
    runner = (ROOT / "scripts/50_run_day5_startup_sync_matrix.py").read_text()
    handshake = (ROOT / "scripts/48_wait_rosbag_connections.py").read_text()
    assert "date +%s%N" not in runner
    assert "unpause_monotonic_ns" not in runner
    assert "unpause_monotonic_ns" not in handshake
    assert "rosservice call" not in runner
    assert "48_wait_rosbag_connections.py" in runner

