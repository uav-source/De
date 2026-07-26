from __future__ import annotations

from pathlib import Path

from fastlio2_adapter.tail_clock_protocol import (
    NODE_NAME,
    TAIL_CLOCK_STEP_NS,
    TailClockState,
    tail_clock_ns,
)


ROOT = Path(__file__).resolve().parents[1]
NODE_SOURCE = ROOT / "scripts/59_day5_tail_clock_node.py"


def test_complete_handoff_has_exact_boundary_and_no_overlap() -> None:
    state = TailClockState()
    for index in range(10):
        state.note_bag_clock(1_000_000_000 + index * 10_000_000, index)
    last_bag = state.last_bag_clock_ns
    assert state.begin(
        request_ns=100,
        clock_publishers=(),
        fast_node_present=True,
        use_sim_time=True,
    ) == "NONE"
    for index in range(100):
        state.note_publish(
            tail_clock_ns(state.tail_start_clock_ns, index, TAIL_CLOCK_STEP_NS),
            200 + index,
        )
    state.note_publishers((NODE_NAME,))
    state.finish(request_ns=500, response_ns=510)
    assert state.tail_first_clock_ns == last_bag + TAIL_CLOCK_STEP_NS
    assert state.clock_publisher_overlap_count == 0
    assert state.clock_duplicate_count == 0
    assert state.clock_backward_count == 0
    assert state.handoff_pass


def test_playback_phase_never_creates_tail_values() -> None:
    state = TailClockState()
    for index in range(50):
        state.note_bag_clock(index * 1_000_000, index)
    assert state.tail_publish_count == 0
    assert not state.publishing


def test_stop_freezes_publish_count() -> None:
    state = TailClockState()
    state.note_bag_clock(10, 1)
    state.begin(
        request_ns=2,
        clock_publishers=(),
        fast_node_present=True,
        use_sim_time=True,
    )
    state.note_publish(state.tail_start_clock_ns, 3)
    state.finish(request_ns=4, response_ns=5)
    count = state.tail_publish_count
    state.note_bag_clock(999, 6)
    assert state.tail_publish_count == count
    assert not state.publishing


def test_node_uses_wall_scheduling_and_explicit_thread_join() -> None:
    source = NODE_SOURCE.read_text(encoding="utf-8")
    assert "time.monotonic_ns()" in source
    assert "stop_event.wait(" in source
    assert "publish_thread.join(" in source
    assert "rospy.Rate" not in source
    assert "rospy.sleep" not in source


def test_node_enforces_both_wall_and_sim_advance_limits() -> None:
    source = NODE_SOURCE.read_text(encoding="utf-8")
    assert "now_ns - wall_start_ns >= max_wall_ns" in source
    assert "index * self.state.tail_clock_step_ns >= max_advance_ns" in source
    assert "time.monotonic_ns()" in source


def test_node_has_only_clock_subscription_source_literal() -> None:
    source = NODE_SOURCE.read_text(encoding="utf-8")
    assert "rospy.Subscriber(" in source
    assert 'CLOCK_TOPIC,' in source
    for forbidden in (
        "/livox/lidar",
        "/livox/imu",
        "pose_gt",
        "ground_truth",
        "future",
        "holdout",
        "map",
        "state_ikfom",
    ):
        assert forbidden not in source


def test_node_publisher_is_created_only_by_start_handler() -> None:
    source = NODE_SOURCE.read_text(encoding="utf-8")
    prefix, start_body = source.split("    def start(", 1)
    assert "rospy.Publisher(" not in prefix
    assert "self.rospy.Publisher(" in start_body
