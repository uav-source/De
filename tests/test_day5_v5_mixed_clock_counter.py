from eval.day5_v5_adjudication import (
    analyze_clock_counter_semantics,
    recalculate_tail_clock,
)


PROTOCOL_SOURCE = """
def tail_clock_ns(start_clock_ns, published_index, step_ns):
    if step_ns <= 0:
        raise ValueError
    return int(start_clock_ns) + int(published_index) * int(step_ns)

class TailClockState:
    def note_bag_clock(self, value, wall):
        self.clock_backward_count += 1
        self.clock_duplicate_count += 1

    def note_publish(self, value, wall):
        self.clock_backward_count += 1
        self.clock_duplicate_count += 1

    def finish(self):
        self.handoff_pass = (
            self.clock_backward_count == 0
            and self.clock_duplicate_count == 0
            and self.clock_publisher_overlap_count == 0
        )
"""

NODE_SOURCE = """
class TailClockNode:
    def clock_callback(self, message):
        self.state.note_bag_clock(1, 2)

    def publish_loop(self):
        index = 0
        value = tail_clock_ns(self.state.tail_start_clock_ns, index, 1)
        self.state.note_publish(value, 2)
        index += 1
"""


def _handoff():
    return {
        "last_bag_clock_ns": 100,
        "tail_first_clock_ns": 110,
        "tail_clock_step_ns": 10,
        "tail_publish_count": 4,
        "tail_final_clock_ns": 140,
        "clock_backward_count": 0,
        "clock_duplicate_count": 7,
        "clock_publisher_overlap_count": 0,
    }


def test_mixed_counter_source_is_identified():
    result = analyze_clock_counter_semantics(
        PROTOCOL_SOURCE,
        NODE_SOURCE,
        "a" * 64,
        "b" * 64,
    )
    assert result["MIXED_CLOCK_COUNTER_CONFIRMED"] is True
    assert result["clock_duplicate_count_updated_during_bag_phase"] is True
    assert result["clock_duplicate_count_updated_during_tail_phase"] is True
    assert result["clock_duplicate_count_used_in_final_gate"] is True


def test_bag_only_counter_cannot_be_named_tail_duplicate():
    bag_only = PROTOCOL_SOURCE.replace(
        "        self.clock_duplicate_count += 1\n\n    def finish",
        "        pass\n\n    def finish",
    )
    result = analyze_clock_counter_semantics(
        bag_only,
        NODE_SOURCE,
        "a" * 64,
        "b" * 64,
    )
    assert result["MIXED_CLOCK_COUNTER_CONFIRMED"] is False


def test_positive_step_and_sequential_index_derive_no_tail_duplicate():
    semantics = analyze_clock_counter_semantics(
        PROTOCOL_SOURCE,
        NODE_SOURCE,
        "a" * 64,
        "b" * 64,
    )
    result = recalculate_tail_clock(
        _handoff(), semantics["locked_tail_generation_rule_confirmed"]
    )
    assert result["tail_clock_duplicate_count_derived"] == 0
    assert result["tail_clock_backward_count_derived"] == 0
    assert result["bag_or_mixed_clock_duplicate_count"] == 7
    assert result["full_tail_message_stream_individually_inspected"] is False


def test_unlocked_generation_rule_does_not_derive_tail_count():
    result = recalculate_tail_clock(_handoff(), False)
    assert result["tail_clock_duplicate_count_derived"] is None
    assert (
        result["EXECUTED_RUN_TAIL_CLOCK_MONOTONIC_ADJUDICATION"] is False
    )
