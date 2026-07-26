import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module():
    spec = importlib.util.spec_from_file_location("startup_handshake", ROOT / "scripts/48_wait_rosbag_connections.py")
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


def test_exact_two_topic_snapshot_passes():
    assert M.evaluate_snapshot(snapshot())["snapshot_pass"] is True


def test_missing_publisher_fails():
    value = snapshot(); value["publisher_state"] = value["publisher_state"][:1]
    assert M.evaluate_snapshot(value)["snapshot_pass"] is False


def test_missing_subscriber_fails():
    value = snapshot(); value["subscriber_state"] = value["subscriber_state"][:1]
    assert M.evaluate_snapshot(value)["snapshot_pass"] is False


def test_disconnected_bus_fails():
    value = snapshot(); value["publisher_bus_info"][0][5] = False
    assert M.evaluate_snapshot(value)["snapshot_pass"] is False


def test_only_lidar_connected_fails():
    value = snapshot(); value["publisher_bus_info"] = value["publisher_bus_info"][:1]; value["subscriber_bus_info"] = value["subscriber_bus_info"][:1]
    assert M.evaluate_snapshot(value)["snapshot_pass"] is False


def test_only_imu_connected_fails():
    value = snapshot(); value["publisher_bus_info"] = value["publisher_bus_info"][1:]; value["subscriber_bus_info"] = value["subscriber_bus_info"][1:]
    assert M.evaluate_snapshot(value)["snapshot_pass"] is False


def test_extra_publisher_fails():
    value = snapshot(); value["publisher_state"][0][1].append("/unexpected")
    assert M.evaluate_snapshot(value)["extra_publisher_present"] is True


def test_extra_subscriber_fails():
    value = snapshot(); value["subscriber_state"][0][1].append("/unexpected")
    assert M.evaluate_snapshot(value)["extra_subscriber_present"] is True


def test_pause_service_missing_or_wrong_type_fails():
    missing = snapshot(); missing["service_state"] = []
    wrong = snapshot(); wrong["pause_service_type"] = "std_srvs/Empty"
    assert M.evaluate_snapshot(missing)["snapshot_pass"] is False
    assert M.evaluate_snapshot(wrong)["snapshot_pass"] is False


def test_pause_service_response_failure_fails():
    assert M.unpause_succeeded(1, "success: True") is False
    assert M.unpause_succeeded(0, "success: False") is False
    assert M.unpause_succeeded(0, "success: True") is True


def test_twenty_continuous_polls_pass_but_nineteen_do_not():
    result = M.wait_for_stable_handshake(snapshot, stable_poll_required=20, poll_interval_seconds=0.001, timeout_seconds=1, sleep=lambda _: None)
    assert result["handshake_pass"] is True
    calls = 0
    def fetch():
        nonlocal calls
        calls += 1
        if calls <= 19:
            return snapshot()
        raise RuntimeError("not stable")
    ticks = iter([0] + [0] * 39 + [2_000_000_000] * 4)
    result = M.wait_for_stable_handshake(fetch, stable_poll_required=20, poll_interval_seconds=0.1, timeout_seconds=1, monotonic_ns=lambda: next(ticks), sleep=lambda _: None)
    assert result["handshake_pass"] is False


def test_unpause_is_not_called_before_stable_handshake():
    calls = []
    ticks = iter([0, 0, 2_000_000_000, 2_000_000_000])
    result = M.perform_handshake_and_unpause(
        lambda: {**snapshot(), "publisher_bus_info": []},
        stable_poll_required=1,
        poll_interval_seconds=0.1,
        timeout_seconds=1,
        monotonic_ns=lambda: next(ticks),
        sleep=lambda _: None,
        unpause=lambda: calls.append(True),
    )
    assert result["handshake_pass"] is False
    assert result["unpause_success"] is False
    assert calls == []
