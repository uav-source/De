from __future__ import annotations

from collections import OrderedDict

import pytest

from fastlio2_adapter.tail_clock_protocol import (
    BAG_PLAYER_NODE,
    NODE_NAME,
    PROTOCOL_VERSION,
    TAIL_CLOCK_MAX_SIM_ADVANCE_SEC,
    TAIL_CLOCK_MAX_WALL_DURATION_SEC,
    TAIL_CLOCK_PUBLISH_HZ,
    TAIL_CLOCK_STEP_NS,
    TailClockState,
    first_tail_clock_ns,
    start_failure_reason,
    status_checksum,
    tail_clock_ns,
    validate_status,
)


def ready_state() -> TailClockState:
    state = TailClockState()
    state.note_bag_clock(1_000_000_000, 10)
    return state


def test_protocol_constants_are_frozen() -> None:
    assert PROTOCOL_VERSION == "day5_tail_clock_protocol_v1"
    assert NODE_NAME == "/day5_tail_clock"
    assert TAIL_CLOCK_STEP_NS == 1_000_000
    assert TAIL_CLOCK_PUBLISH_HZ == 500
    assert TAIL_CLOCK_MAX_WALL_DURATION_SEC == 90.0
    assert TAIL_CLOCK_MAX_SIM_ADVANCE_SEC == 45.0


def test_start_without_bag_clock_fails() -> None:
    assert start_failure_reason(
        bag_clock_message_count=0,
        clock_publishers=(),
        fast_node_present=True,
        use_sim_time=True,
        already_started=False,
    ) == "TAIL_CLOCK_NO_BAG_CLOCK"


def test_start_while_bag_publisher_exists_fails() -> None:
    assert start_failure_reason(
        bag_clock_message_count=1,
        clock_publishers=(BAG_PLAYER_NODE,),
        fast_node_present=True,
        use_sim_time=True,
        already_started=False,
    ) == "TAIL_CLOCK_BAG_PUBLISHER_STILL_ACTIVE"


def test_start_with_unknown_publisher_fails() -> None:
    assert start_failure_reason(
        bag_clock_message_count=1,
        clock_publishers=("/unknown",),
        fast_node_present=True,
        use_sim_time=True,
        already_started=False,
    ) == "TAIL_CLOCK_UNKNOWN_PUBLISHER_PRESENT"


@pytest.mark.parametrize(
    ("fast_present", "sim_time", "already_started"),
    [(False, True, False), (True, False, False), (True, True, True)],
)
def test_other_start_preconditions_fail(
    fast_present: bool,
    sim_time: bool,
    already_started: bool,
) -> None:
    assert start_failure_reason(
        bag_clock_message_count=1,
        clock_publishers=(),
        fast_node_present=fast_present,
        use_sim_time=sim_time,
        already_started=already_started,
    ) == "TAIL_CLOCK_START_FAILURE"


def test_first_clock_is_last_bag_plus_step() -> None:
    assert first_tail_clock_ns(10_000_000, TAIL_CLOCK_STEP_NS) == 11_000_000


def test_clock_sequence_is_formula_driven_and_strictly_monotonic() -> None:
    start = 100_000_000
    values = [tail_clock_ns(start, index, TAIL_CLOCK_STEP_NS) for index in range(20)]
    assert values[0] == start
    assert all(right - left == TAIL_CLOCK_STEP_NS for left, right in zip(values, values[1:]))


def test_invalid_clock_formula_inputs_fail() -> None:
    with pytest.raises(ValueError):
        first_tail_clock_ns(-1, 1)
    with pytest.raises(ValueError):
        tail_clock_ns(0, -1, 1)
    with pytest.raises(ValueError):
        tail_clock_ns(0, 0, 0)


def test_bag_clock_is_not_recorded_during_tail_publish() -> None:
    state = ready_state()
    assert state.begin(
        request_ns=20,
        clock_publishers=(),
        fast_node_present=True,
        use_sim_time=True,
    ) == "NONE"
    before = state.bag_clock_message_count
    state.note_bag_clock(2_000_000_000, 30)
    assert state.bag_clock_message_count == before
    assert state.last_bag_clock_ns == 1_000_000_000


def test_duplicate_and_backward_bag_clock_are_counted() -> None:
    state = TailClockState()
    state.note_bag_clock(10, 1)
    state.note_bag_clock(10, 2)
    state.note_bag_clock(9, 3)
    assert state.clock_duplicate_count == 1
    assert state.clock_backward_count == 1


def test_duplicate_and_backward_tail_clock_are_counted() -> None:
    state = ready_state()
    state.begin(
        request_ns=20,
        clock_publishers=(),
        fast_node_present=True,
        use_sim_time=True,
    )
    state.note_publish(state.tail_start_clock_ns, 30)
    state.note_publish(state.tail_start_clock_ns, 31)
    state.note_publish(state.tail_start_clock_ns - 1, 32)
    assert state.clock_duplicate_count == 1
    assert state.clock_backward_count == 1


def test_overlap_is_counted_without_accepting_unknown_publisher() -> None:
    state = ready_state()
    state.begin(
        request_ns=20,
        clock_publishers=(),
        fast_node_present=True,
        use_sim_time=True,
    )
    state.note_publishers((NODE_NAME, "/unknown"))
    assert state.clock_publisher_overlap_count == 1
    assert state.failure_reason == "TAIL_CLOCK_PUBLISHER_OVERLAP"


def test_successful_finish_requires_first_clock_and_no_overlap() -> None:
    state = ready_state()
    state.begin(
        request_ns=20,
        clock_publishers=(),
        fast_node_present=True,
        use_sim_time=True,
    )
    state.note_publish(state.tail_start_clock_ns, 30)
    state.note_publish(state.tail_start_clock_ns + TAIL_CLOCK_STEP_NS, 31)
    state.finish(request_ns=40, response_ns=50)
    assert state.stop_success
    assert state.handoff_pass


def test_repeated_start_is_rejected() -> None:
    state = ready_state()
    assert state.begin(
        request_ns=20,
        clock_publishers=(),
        fast_node_present=True,
        use_sim_time=True,
    ) == "NONE"
    assert state.begin(
        request_ns=21,
        clock_publishers=(),
        fast_node_present=True,
        use_sim_time=True,
    ) == "TAIL_CLOCK_START_FAILURE"
    assert state.start_success
    assert state.publishing
    assert state.failure_reason == "NONE"


def test_status_order_and_checksum_are_deterministic() -> None:
    state = ready_state()
    first = state.ordered_status()
    second = state.ordered_status()
    assert isinstance(first, OrderedDict)
    assert first == second
    assert status_checksum(first) == first["status_checksum"]
    assert validate_status(first)["protocol_version"] == PROTOCOL_VERSION
    changed = OrderedDict(first)
    changed["tail_publish_count"] = 1
    with pytest.raises(ValueError, match="checksum"):
        validate_status(changed)
