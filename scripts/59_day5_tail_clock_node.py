#!/usr/bin/env python3
"""External wall-scheduled clock handoff node for Day 5 V5."""

import argparse
import json
import os
import sys
import threading
import time
import xmlrpc.client
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.tail_clock_protocol import (  # noqa: E402
    BAG_PLAYER_NODE,
    CLOCK_TOPIC,
    FAST_NODE,
    NODE_NAME,
    START_SERVICE,
    STATUS_SERVICE,
    STOP_SERVICE,
    TailClockState,
    tail_clock_ns,
)


def atomic_status(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


class TailClockNode:
    def __init__(self, state_output: Path) -> None:
        import rospy
        from rosgraph_msgs.msg import Clock
        from std_srvs.srv import Trigger

        self.rospy = rospy
        self.Clock = Clock
        self.state_output = state_output
        self.state = TailClockState()
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.first_publish_event = threading.Event()
        self.publisher = None
        self.publish_thread: Optional[threading.Thread] = None
        self.master = xmlrpc.client.ServerProxy(
            os.environ["ROS_MASTER_URI"],
            allow_none=True,
        )
        self.subscriber = rospy.Subscriber(
            CLOCK_TOPIC,
            Clock,
            self.clock_callback,
            queue_size=1000,
        )
        self.start_service = rospy.Service(
            START_SERVICE,
            Trigger,
            self.start,
        )
        self.stop_service = rospy.Service(
            STOP_SERVICE,
            Trigger,
            self.stop,
        )
        self.status_service = rospy.Service(
            STATUS_SERVICE,
            Trigger,
            self.status,
        )
        rospy.on_shutdown(self.shutdown)
        self.persist()

    def clock_publishers(self) -> List[str]:
        code, _text, system_state = self.master.getSystemState(NODE_NAME)
        if int(code) != 1:
            raise RuntimeError("ROS master system-state query failed")
        publishers = {
            topic: names for topic, names in system_state[0]
        }
        return sorted(set(publishers.get(CLOCK_TOPIC, [])))

    def clock_subscribers(self) -> List[str]:
        code, _text, system_state = self.master.getSystemState(NODE_NAME)
        if int(code) != 1:
            raise RuntimeError("ROS master system-state query failed")
        subscribers = {
            topic: names for topic, names in system_state[1]
        }
        return sorted(set(subscribers.get(CLOCK_TOPIC, [])))

    def node_present(self, node_name: str) -> bool:
        try:
            code, _text, _uri = self.master.lookupNode(NODE_NAME, node_name)
            return int(code) == 1
        except Exception:
            return False

    def sim_time_enabled(self) -> bool:
        try:
            code, _text, value = self.master.getParam(
                NODE_NAME,
                "/use_sim_time",
            )
            return int(code) == 1 and value is True
        except Exception:
            return False

    def persist(self) -> None:
        with self.lock:
            atomic_status(self.state_output, dict(self.state.ordered_status()))

    def response(self, success: bool):
        from std_srvs.srv import TriggerResponse

        with self.lock:
            message = json.dumps(
                self.state.ordered_status(),
                separators=(",", ":"),
            )
        return TriggerResponse(success=success, message=message)

    def clock_callback(self, message: Any) -> None:
        with self.lock:
            if self.state.publishing:
                return
            value_ns = (
                int(message.clock.secs) * 1_000_000_000
                + int(message.clock.nsecs)
            )
            self.state.note_bag_clock(value_ns, time.monotonic_ns())
            if self.state.bag_clock_message_count % 500 == 0:
                self.persist()

    def start(self, _request: Any):
        request_ns = time.monotonic_ns()
        try:
            publishers = self.clock_publishers()
        except Exception:
            publishers = [BAG_PLAYER_NODE]
        with self.lock:
            reason = self.state.begin(
                request_ns=request_ns,
                clock_publishers=publishers,
                fast_node_present=self.node_present(FAST_NODE),
                use_sim_time=self.sim_time_enabled(),
            )
            if reason != "NONE":
                self.state.tail_start_response_monotonic_ns = (
                    time.monotonic_ns()
                )
                self.persist()
                return self.response(False)
            self.stop_event.clear()
            self.first_publish_event.clear()
            self.publisher = self.rospy.Publisher(
                CLOCK_TOPIC,
                self.Clock,
                queue_size=100,
            )
        connection_deadline = time.monotonic_ns() + 5_000_000_000
        while (
            FAST_NODE not in self.clock_subscribers()
            and time.monotonic_ns() < connection_deadline
            and not self.rospy.is_shutdown()
        ):
            self.stop_event.wait(0.01)
        if FAST_NODE not in self.clock_subscribers():
            with self.lock:
                self.state.failure_reason = "TAIL_CLOCK_START_FAILURE"
                self.state.start_success = False
                self.state.publishing = False
                self.publisher.unregister()
                self.publisher = None
                self.state.tail_start_response_monotonic_ns = (
                    time.monotonic_ns()
                )
                self.persist()
            return self.response(False)
        self.publish_thread = threading.Thread(
            target=self.publish_loop,
            name="day5-tail-clock-publisher",
            daemon=False,
        )
        self.publish_thread.start()
        if not self.first_publish_event.wait(2.0):
            with self.lock:
                self.state.failure_reason = "TAIL_CLOCK_START_FAILURE"
            self.stop_event.set()
            self.publish_thread.join(timeout=3.0)
            with self.lock:
                self.state.start_success = False
                self.state.publishing = False
                if self.publisher is not None:
                    self.publisher.unregister()
                    self.publisher = None
                self.state.tail_start_response_monotonic_ns = (
                    time.monotonic_ns()
                )
                self.persist()
            return self.response(False)
        with self.lock:
            self.state.tail_start_response_monotonic_ns = time.monotonic_ns()
            self.state.note_publishers(self.clock_publishers())
            self.persist()
        return self.response(True)

    def publish_loop(self) -> None:
        period_ns = int(1_000_000_000 / self.state.tail_clock_publish_hz)
        wall_start_ns = time.monotonic_ns()
        next_publish_ns = wall_start_ns
        index = 0
        max_wall_ns = int(
            self.state.tail_clock_max_wall_duration_sec * 1_000_000_000
        )
        max_advance_ns = int(
            self.state.tail_clock_max_sim_advance_sec * 1_000_000_000
        )
        while not self.stop_event.is_set() and not self.rospy.is_shutdown():
            now_ns = time.monotonic_ns()
            if now_ns - wall_start_ns >= max_wall_ns:
                with self.lock:
                    self.state.failure_reason = "TAIL_CLOCK_STOP_FAILURE"
                    self.state.publishing = False
                    self.persist()
                return
            if index * self.state.tail_clock_step_ns >= max_advance_ns:
                with self.lock:
                    self.state.failure_reason = "TAIL_CLOCK_STOP_FAILURE"
                    self.state.publishing = False
                    self.persist()
                return
            value_ns = tail_clock_ns(
                self.state.tail_start_clock_ns,
                index,
                self.state.tail_clock_step_ns,
            )
            message = self.Clock()
            message.clock.secs = value_ns // 1_000_000_000
            message.clock.nsecs = value_ns % 1_000_000_000
            self.publisher.publish(message)
            publish_ns = time.monotonic_ns()
            with self.lock:
                self.state.note_publish(value_ns, publish_ns)
                if index % 250 == 0:
                    self.state.note_publishers(self.clock_publishers())
                    self.persist()
            if index == 0:
                self.first_publish_event.set()
            index += 1
            next_publish_ns = wall_start_ns + index * period_ns
            wait_sec = max(
                0.0,
                (next_publish_ns - time.monotonic_ns()) / 1_000_000_000.0,
            )
            self.stop_event.wait(wait_sec)

    def status(self, _request: Any):
        with self.lock:
            if self.state.publishing:
                try:
                    self.state.note_publishers(self.clock_publishers())
                except Exception:
                    pass
            self.persist()
        return self.response(True)

    def stop(self, _request: Any):
        request_ns = time.monotonic_ns()
        with self.lock:
            if not self.state.start_success:
                self.state.failure_reason = (
                    self.state.failure_reason
                    if self.state.failure_reason != "NONE"
                    else "TAIL_CLOCK_STOP_FAILURE"
                )
                self.state.tail_stop_request_monotonic_ns = request_ns
                self.state.tail_stop_response_monotonic_ns = (
                    time.monotonic_ns()
                )
                self.persist()
                return self.response(False)
            if not self.state.publishing and self.state.stop_success:
                return self.response(False)
        self.stop_event.set()
        if self.publish_thread is not None:
            self.publish_thread.join(timeout=3.0)
        thread_alive = bool(
            self.publish_thread is not None
            and self.publish_thread.is_alive()
        )
        with self.lock:
            if thread_alive:
                self.state.failure_reason = "TAIL_CLOCK_STOP_FAILURE"
            if self.publisher is not None:
                self.publisher.unregister()
                self.publisher = None
        disappear_deadline = time.monotonic_ns() + 2_000_000_000
        publishers: List[str] = []
        while time.monotonic_ns() < disappear_deadline:
            try:
                publishers = self.clock_publishers()
            except Exception:
                publishers = []
            if NODE_NAME not in publishers:
                break
            self.stop_event.wait(0.01)
        response_ns = time.monotonic_ns()
        with self.lock:
            self.state.clock_publishers_after_handoff = publishers
            self.state.finish(request_ns=request_ns, response_ns=response_ns)
            if thread_alive or NODE_NAME in publishers:
                self.state.stop_success = False
                self.state.handoff_pass = False
                self.state.failure_reason = "TAIL_CLOCK_STOP_FAILURE"
            self.persist()
            success = self.state.stop_success and self.state.handoff_pass
        threading.Thread(
            target=self.shutdown_after_response,
            name="day5-tail-clock-shutdown",
            daemon=True,
        ).start()
        return self.response(success)

    def shutdown_after_response(self) -> None:
        time.sleep(0.05)
        self.rospy.signal_shutdown("tail-clock stop completed")

    def shutdown(self) -> None:
        self.stop_event.set()
        if self.publish_thread is not None:
            self.publish_thread.join(timeout=3.0)
        with self.lock:
            if self.publisher is not None:
                self.publisher.unregister()
                self.publisher = None
            self.state.publishing = False
            self.persist()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    import rospy

    args = parse_args()
    rospy.init_node("day5_tail_clock", anonymous=False, disable_signals=False)
    TailClockNode(args.state_output.expanduser().resolve())
    rospy.spin()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
