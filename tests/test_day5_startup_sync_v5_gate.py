from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from fastlio2_adapter.replay_endpoint_contract import (
    CONTRACT_SOURCE,
    ENDPOINT_POLICY,
    EXPECTED_CLIPS,
    SCHEMA_VERSION,
    canonical_json_bytes,
)


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SMALL_RESULTS = {
    "tail_clock_handoff_summary.csv",
    "tail_clock_monotonicity_audit.csv",
    "clock_publisher_transition_audit.csv",
    "drain_service_timeout_summary.csv",
    "end_of_stream_drain_summary.csv",
    "callback_endpoint_summary.csv",
    "supervisor_summary.csv",
    "single_run_inventory.csv",
    "baseline_pairwise_equivalence.csv",
    "baseline_repeatability_summary.csv",
    "gate_summary.csv",
    "day5_startup_sync_v5_summary.json",
    "day5_startup_sync_v5_gate_summary.json",
    "full_log_index.csv",
}


def load_finalizer():
    path = ROOT / "scripts/62_finalize_day5_startup_sync_v5.py"
    spec = importlib.util.spec_from_file_location(
        "day5_v5_finalizer", path
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def endpoint_fixture(path: Path) -> None:
    sequences = []
    for sequence_id in sorted(EXPECTED_CLIPS):
        expected = EXPECTED_CLIPS[sequence_id]
        sequences.append(
            {
                "sequence_id": sequence_id,
                "clip_sha256": expected["clip_sha256"],
                "expected_lidar_message_count": expected[
                    "expected_lidar_message_count"
                ],
                "expected_imu_message_count": expected[
                    "expected_imu_message_count"
                ],
            }
        )
    value = {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": "2026-01-01T00:00:00.000000Z",
        "contract_source": CONTRACT_SOURCE,
        "endpoint_policy": ENDPOINT_POLICY,
        "sequences": sequences,
    }
    value["contract_checksum_sha256"] = hashlib.sha256(
        canonical_json_bytes(value)
    ).hexdigest()
    path.write_bytes(canonical_json_bytes(value))


def test_constants_freeze_final_attempt_and_tolerance() -> None:
    module = load_finalizer()
    assert module.RUN_ID == "multihyp_day5_startup_sync_v5"
    assert module.TOLERANCE == 1e-12
    assert module.REPEATS == (1, 2, 3)
    assert module.PAIRS == ((1, 2), (1, 3), (2, 3))


def test_tail_rows_require_exact_first_clock_and_no_overlap() -> None:
    module = load_finalizer()
    summary, monotonic, transition = module.tail_clock_rows(
        [
            {
                "sequence_id": "avia_quick_shack",
                "repeat_id": 1,
                "last_bag_clock_ns": 10,
                "tail_first_clock_ns": 11,
                "tail_clock_step_ns": 1,
                "clock_duplicate_count": 0,
                "clock_backward_count": 0,
                "clock_publisher_overlap_count": 0,
            }
        ]
    )
    assert summary[0]["first_tail_exact_pass"] is True
    assert monotonic[0]["monotonic_pass"] is True
    assert transition[0]["no_overlap_pass"] is True


def test_partial_real_replay_abandons_strict_route_and_writes_outputs(
    tmp_path: Path,
) -> None:
    module = load_finalizer()
    run_root = tmp_path / "run"
    run_dir = module.run_dir(run_root, "avia_quick_shack", 1)
    run_dir.mkdir(parents=True)
    (run_dir / "single_run_state.json").write_text(
        json.dumps(
            {
                "status": "FAILED",
                "failure_classification": "TAIL_CLOCK_NO_BAG_CLOCK",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    endpoint = tmp_path / "endpoint.json"
    endpoint_fixture(endpoint)
    lock = tmp_path / "lock.json"
    lock.write_text(
        json.dumps(
            {
                "endpoint_contract_sha256": hashlib.sha256(
                    endpoint.read_bytes()
                ).hexdigest(),
                "fastlio2_unchanged_pass": True,
                "tail_clock_protocol_test_pass": True,
                "service_call_timeout_sec": 2.0,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run_root / "matrix_state.json").write_text(
        json.dumps(
            {
                "status": "FAILED",
                "failure_classification": "TAIL_CLOCK_NO_BAG_CLOCK",
                "runner_interruption_count": 0,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    summary = module.finalize_partial(run_root, endpoint, lock)
    assert summary["executed_replay_count"] == 1
    assert summary["successful_replay_count"] == 0
    assert summary["DAY5_STARTUP_SYNC_V5_PASS"] is False
    assert (
        summary["STRICT_CROSS_PROCESS_REPLAY_ROUTE_STATUS"]
        == "ABANDONED_AFTER_V5"
    )
    assert summary["STRICT_REPLAY_FURTHER_REMEDIATION_AUTHORIZED"] is False
    assert summary["CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE"] == "NOT_PROVEN"
    assert REQUIRED_SMALL_RESULTS <= {
        path.name for path in run_root.iterdir() if path.is_file()
    }


def test_run_directory_is_fixed_audit_only_layout(tmp_path: Path) -> None:
    module = load_finalizer()
    assert module.run_dir(tmp_path, "avia_quick_shack", 2) == (
        tmp_path
        / "runs/baseline/avia_quick_shack/AUDIT_ONLY_R2"
    )

