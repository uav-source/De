"""Deterministic, estimator-independent tail-clock state protocol."""

import hashlib
import json
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List


PROTOCOL_VERSION = "day5_tail_clock_protocol_v1"
NODE_NAME = "/day5_tail_clock"
START_SERVICE = "/day5_tail_clock/start"
STOP_SERVICE = "/day5_tail_clock/stop"
STATUS_SERVICE = "/day5_tail_clock/status"
CLOCK_TOPIC = "/clock"
BAG_PLAYER_NODE = "/day5_bag_player"
FAST_NODE = "/laserMapping"
TAIL_CLOCK_STEP_NS = 1_000_000
TAIL_CLOCK_PUBLISH_HZ = 500
TAIL_CLOCK_MAX_WALL_DURATION_SEC = 90.0
TAIL_CLOCK_MAX_SIM_ADVANCE_SEC = 45.0
STATUS_FIELDS = (
    "node_name",
    "protocol_version",
    "bag_clock_message_count",
    "last_bag_clock_ns",
    "last_bag_clock_wall_receive_ns",
    "clock_publishers_before_handoff",
    "clock_publishers_during_handoff",
    "clock_publishers_after_handoff",
    "tail_start_request_monotonic_ns",
    "tail_start_response_monotonic_ns",
    "tail_start_clock_ns",
    "tail_first_clock_ns",
    "tail_first_publish_monotonic_ns",
    "tail_clock_step_ns",
    "tail_clock_publish_hz",
    "tail_clock_max_wall_duration_sec",
    "tail_clock_max_sim_advance_sec",
    "tail_publish_count",
    "tail_final_clock_ns",
    "tail_stop_request_monotonic_ns",
    "tail_stop_response_monotonic_ns",
    "clock_backward_count",
    "clock_duplicate_count",
    "clock_publisher_overlap_count",
    "publishing",
    "start_success",
    "stop_success",
    "handoff_pass",
    "failure_reason",
)


def canonical_status_bytes(value: Dict[str, Any]) -> bytes:
    selected = OrderedDict((key, value[key]) for key in STATUS_FIELDS)
    return json.dumps(
        selected,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")


def status_checksum(value: Dict[str, Any]) -> str:
    return "SHA256:" + hashlib.sha256(canonical_status_bytes(value)).hexdigest()


def validate_status(value: Dict[str, Any]) -> Dict[str, Any]:
    if tuple(value) != STATUS_FIELDS + ("status_checksum",):
        raise ValueError("tail-clock status field order mismatch")
    if value["protocol_version"] != PROTOCOL_VERSION:
        raise ValueError("tail-clock protocol version mismatch")
    if value["status_checksum"] != status_checksum(value):
        raise ValueError("tail-clock status checksum mismatch")
    return dict(value)


def first_tail_clock_ns(last_bag_clock_ns: int, step_ns: int) -> int:
    if last_bag_clock_ns < 0:
        raise ValueError("last bag clock must be nonnegative")
    if step_ns <= 0:
        raise ValueError("tail clock step must be positive")
    return int(last_bag_clock_ns) + int(step_ns)


def tail_clock_ns(start_clock_ns: int, published_index: int, step_ns: int) -> int:
    if published_index < 0:
        raise ValueError("published index must be nonnegative")
    if step_ns <= 0:
        raise ValueError("tail clock step must be positive")
    return int(start_clock_ns) + int(published_index) * int(step_ns)


def start_failure_reason(
    *,
    bag_clock_message_count: int,
    clock_publishers: Iterable[str],
    fast_node_present: bool,
    use_sim_time: bool,
    already_started: bool,
) -> str:
    publishers = tuple(sorted(set(clock_publishers)))
    if bag_clock_message_count <= 0:
        return "TAIL_CLOCK_NO_BAG_CLOCK"
    if BAG_PLAYER_NODE in publishers:
        return "TAIL_CLOCK_BAG_PUBLISHER_STILL_ACTIVE"
    if publishers:
        return "TAIL_CLOCK_UNKNOWN_PUBLISHER_PRESENT"
    if not fast_node_present:
        return "TAIL_CLOCK_START_FAILURE"
    if not use_sim_time:
        return "TAIL_CLOCK_START_FAILURE"
    if already_started:
        return "TAIL_CLOCK_START_FAILURE"
    return "NONE"


@dataclass
class TailClockState:
    node_name: str = NODE_NAME
    protocol_version: str = PROTOCOL_VERSION
    bag_clock_message_count: int = 0
    last_bag_clock_ns: int = 0
    last_bag_clock_wall_receive_ns: int = 0
    clock_publishers_before_handoff: List[str] = field(default_factory=list)
    clock_publishers_during_handoff: List[str] = field(default_factory=list)
    clock_publishers_after_handoff: List[str] = field(default_factory=list)
    tail_start_request_monotonic_ns: int = 0
    tail_start_response_monotonic_ns: int = 0
    tail_start_clock_ns: int = 0
    tail_first_clock_ns: int = 0
    tail_first_publish_monotonic_ns: int = 0
    tail_clock_step_ns: int = TAIL_CLOCK_STEP_NS
    tail_clock_publish_hz: int = TAIL_CLOCK_PUBLISH_HZ
    tail_clock_max_wall_duration_sec: float = TAIL_CLOCK_MAX_WALL_DURATION_SEC
    tail_clock_max_sim_advance_sec: float = TAIL_CLOCK_MAX_SIM_ADVANCE_SEC
    tail_publish_count: int = 0
    tail_final_clock_ns: int = 0
    tail_stop_request_monotonic_ns: int = 0
    tail_stop_response_monotonic_ns: int = 0
    clock_backward_count: int = 0
    clock_duplicate_count: int = 0
    clock_publisher_overlap_count: int = 0
    publishing: bool = False
    start_success: bool = False
    stop_success: bool = False
    handoff_pass: bool = False
    failure_reason: str = "NONE"

    def note_bag_clock(self, clock_ns: int, wall_receive_ns: int) -> None:
        if self.publishing:
            return
        value = int(clock_ns)
        if self.bag_clock_message_count:
            if value < self.last_bag_clock_ns:
                self.clock_backward_count += 1
            elif value == self.last_bag_clock_ns:
                self.clock_duplicate_count += 1
        self.bag_clock_message_count += 1
        self.last_bag_clock_ns = value
        self.last_bag_clock_wall_receive_ns = int(wall_receive_ns)

    def begin(
        self,
        *,
        request_ns: int,
        clock_publishers: Iterable[str],
        fast_node_present: bool,
        use_sim_time: bool,
    ) -> str:
        publishers = sorted(set(clock_publishers))
        already_active = self.start_success or self.publishing
        reason = start_failure_reason(
            bag_clock_message_count=self.bag_clock_message_count,
            clock_publishers=publishers,
            fast_node_present=fast_node_present,
            use_sim_time=use_sim_time,
            already_started=already_active,
        )
        if reason != "NONE":
            if already_active:
                return reason
            self.tail_start_request_monotonic_ns = int(request_ns)
            self.clock_publishers_before_handoff = publishers
            self.failure_reason = reason
            self.start_success = False
            return reason
        self.tail_start_request_monotonic_ns = int(request_ns)
        self.clock_publishers_before_handoff = publishers
        self.tail_start_clock_ns = first_tail_clock_ns(
            self.last_bag_clock_ns,
            self.tail_clock_step_ns,
        )
        self.publishing = True
        self.start_success = True
        self.stop_success = False
        self.failure_reason = "NONE"
        return "NONE"

    def note_publish(self, value_ns: int, publish_ns: int) -> None:
        value = int(value_ns)
        if self.tail_publish_count:
            if value < self.tail_final_clock_ns:
                self.clock_backward_count += 1
            elif value == self.tail_final_clock_ns:
                self.clock_duplicate_count += 1
        if self.tail_publish_count == 0:
            self.tail_first_clock_ns = value
            self.tail_first_publish_monotonic_ns = int(publish_ns)
        self.tail_publish_count += 1
        self.tail_final_clock_ns = value

    def note_publishers(self, publishers: Iterable[str]) -> None:
        values = sorted(set(publishers))
        self.clock_publishers_during_handoff = values
        unexpected = [value for value in values if value != self.node_name]
        if unexpected:
            self.clock_publisher_overlap_count += 1
            self.failure_reason = "TAIL_CLOCK_PUBLISHER_OVERLAP"

    def finish(self, *, request_ns: int, response_ns: int) -> None:
        self.tail_stop_request_monotonic_ns = int(request_ns)
        self.tail_stop_response_monotonic_ns = int(response_ns)
        self.publishing = False
        self.stop_success = self.start_success
        self.handoff_pass = bool(
            self.start_success
            and self.stop_success
            and self.tail_publish_count > 0
            and self.tail_first_clock_ns == self.tail_start_clock_ns
            and self.clock_backward_count == 0
            and self.clock_duplicate_count == 0
            and self.clock_publisher_overlap_count == 0
            and self.failure_reason == "NONE"
        )

    def ordered_status(self) -> OrderedDict:
        value = OrderedDict(
            (key, getattr(self, key)) for key in STATUS_FIELDS
        )
        value["status_checksum"] = status_checksum(value)
        return value
