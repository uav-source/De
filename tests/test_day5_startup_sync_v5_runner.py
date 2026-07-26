from __future__ import annotations

import importlib.util
from pathlib import Path

from fastlio2_adapter.end_of_stream_drain import ServicePoll
from fastlio2_adapter.tail_clock_protocol import TailClockState


ROOT = Path(__file__).resolve().parents[1]


def load_runner():
    path = ROOT / "scripts/60_run_single_startup_sync_v5.py"
    spec = importlib.util.spec_from_file_location("day5_v5_runner", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v5_runner_identity_and_mode_are_fixed() -> None:
    module = load_runner()
    assert module.RUN_ID == "multihyp_day5_startup_sync_v5"
    assert module.MODE == "AUDIT_ONLY"
    assert module.REPEATS == (1, 2, 3)
    assert module.SEQUENCES == (
        "avia_quick_shack",
        "avia_outdoor_run_100hz",
    )


def test_runner_orders_handoff_drain_shutdown_and_stop() -> None:
    source = (
        ROOT / "scripts/60_run_single_startup_sync_v5.py"
    ).read_text(encoding="utf-8")
    execute = source.split("def execute(", 1)[1]
    bag_exit = execute.index("rosbag_exit = rosbag.wait")
    bag_release = execute.index("wait_for_bag_clock_release(", bag_exit)
    tail_start = execute.index('lock["tail_clock_start_service"]', bag_release)
    drain = execute.index(
        "scripts/55_wait_fastlio2_end_of_stream_drain.py", tail_start
    )
    shutdown = execute.index("shutdown = graceful_shutdown(", drain)
    tail_stop = execute.index('lock["tail_clock_stop_service"]', shutdown)
    assert bag_exit < bag_release < tail_start < drain < shutdown < tail_stop


def test_failed_trigger_payload_preserves_tail_failure_class(
    monkeypatch,
) -> None:
    module = load_runner()
    state = TailClockState()
    state.begin(
        request_ns=1,
        clock_publishers=(),
        fast_node_present=True,
        use_sim_time=True,
    )
    payload = dict(state.ordered_status())
    monkeypatch.setattr(
        module,
        "bounded_trigger_call",
        lambda *_args, **_kwargs: ServicePoll(
            snapshot=payload,
            evidence={
                "service_success": False,
                "service_timeout": False,
            },
        ),
    )
    result = module.trigger_status(
        "/day5_tail_clock/start",
        environment={},
        timeout_sec=2.0,
    )
    assert result["failure_reason"] == "TAIL_CLOCK_NO_BAG_CLOCK"
    assert result["start_success"] is False


def test_runner_never_requests_capture_or_detector_modes() -> None:
    source = (
        ROOT / "scripts/60_run_single_startup_sync_v5.py"
    ).read_text(encoding="utf-8")
    assert '"CAPTURE_ONLY"' not in source
    assert '"COMPACT_EXPORT"' not in source
    assert "src/degen_detector" not in source

