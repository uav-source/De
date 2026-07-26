#!/usr/bin/env python3
"""Wait for the read-only FAST-LIO2 end-of-stream drain gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.end_of_stream_drain import (  # noqa: E402
    DRAIN_TIMEOUT_SEC,
    MAX_CONSECUTIVE_SERVICE_TIMEOUTS,
    POLL_INTERVAL_SEC,
    SERVICE_CALL_TIMEOUT_SEC,
    STABLE_POLL_COUNT,
    DrainError,
    bounded_trigger_call,
    wait_for_drain,
    write_poll_trace,
)
from fastlio2_adapter.replay_endpoint_contract import (  # noqa: E402
    sequence_contract,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint-contract", required=True, type=Path)
    parser.add_argument("--sequence-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--repeat-id", required=True, type=int)
    parser.add_argument("--master-uri", required=True)
    parser.add_argument("--service-name", default="/harmful_bias/end_of_stream_status")
    parser.add_argument("--stable-poll-count", type=int, default=STABLE_POLL_COUNT)
    parser.add_argument("--poll-interval", type=float, default=POLL_INTERVAL_SEC)
    parser.add_argument("--timeout", type=float, default=DRAIN_TIMEOUT_SEC)
    parser.add_argument(
        "--service-call-timeout",
        type=float,
        default=SERVICE_CALL_TIMEOUT_SEC,
    )
    parser.add_argument(
        "--max-consecutive-service-timeouts",
        type=int,
        default=MAX_CONSECUTIVE_SERVICE_TIMEOUTS,
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--trace-output", required=True, type=Path)
    return parser.parse_args()


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        import os
        os.fsync(stream.fileno())
    temporary.replace(path)


def main() -> int:
    args = parse_args()
    import os
    os.environ["ROS_MASTER_URI"] = args.master_uri

    contract_bytes = args.endpoint_contract.read_bytes()
    contract = json.loads(contract_bytes)
    endpoint = sequence_contract(contract, args.sequence_id)

    locked_environment = dict(os.environ)

    def fetch():
        return bounded_trigger_call(
            args.service_name,
            environment=locked_environment,
            timeout_sec=args.service_call_timeout,
        )

    try:
        result, trace = wait_for_drain(
            fetch,
            endpoint,
            stable_required=args.stable_poll_count,
            poll_interval_sec=args.poll_interval,
            timeout_sec=args.timeout,
            max_consecutive_service_timeouts=(
                args.max_consecutive_service_timeouts
            ),
        )
    except DrainError as error:
        write_poll_trace(args.trace_output, error.trace)
        result = {
            "run_id": args.run_id,
            "sequence_id": args.sequence_id,
            "repeat_id": args.repeat_id,
            "endpoint_contract_sha256": hashlib.sha256(contract_bytes).hexdigest(),
            "drain_pass": False,
            "failure_classification": error.classification,
            "message": str(error),
            "service_call_timeout_sec": args.service_call_timeout,
            "service_call_timeout_count": error.service_call_timeout_count,
            "max_consecutive_service_timeouts": (
                error.max_consecutive_service_timeouts
            ),
            "stable_poll_required": args.stable_poll_count,
            "stable_poll_observed": max(
                (
                    int(row.get("stable_poll_observed", 0))
                    for row in error.trace
                ),
                default=0,
            ),
        }
        _atomic_json(args.output, result)
        return 20
    snapshot = result.pop("final_snapshot")
    output = {
        "run_id": args.run_id,
        "sequence_id": args.sequence_id,
        "repeat_id": args.repeat_id,
        "endpoint_contract_sha256": hashlib.sha256(contract_bytes).hexdigest(),
        "expected_lidar_callback_count": endpoint["expected_lidar_message_count"],
        "actual_lidar_callback_count": snapshot["lidar_callback_count"],
        "expected_imu_callback_count": endpoint["expected_imu_message_count"],
        "actual_imu_callback_count": snapshot["imu_callback_count"],
        "expected_last_lidar_header_stamp_ns": endpoint["last_lidar_header_stamp_ns"],
        "actual_last_lidar_header_stamp_ns": snapshot["last_lidar_header_stamp_ns"],
        "expected_last_imu_header_stamp_ns": endpoint["last_imu_header_stamp_ns"],
        "actual_last_imu_header_stamp_ns": snapshot["last_imu_raw_header_stamp_ns"],
        "final_processed_measure_group_count": snapshot["processed_measure_group_count"],
        "last_processed_lidar_begin_stamp_ns": snapshot["last_processed_lidar_begin_stamp_ns"],
        "last_processed_lidar_end_stamp_ns": snapshot["last_processed_lidar_end_stamp_ns"],
        "unprocessed_lidar_tail_count": snapshot["lidar_buffer_size"],
        "remaining_imu_count": snapshot["imu_buffer_size"],
        "service_call_timeout_sec": args.service_call_timeout,
        **result,
    }
    write_poll_trace(args.trace_output, trace)
    _atomic_json(args.output, output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
