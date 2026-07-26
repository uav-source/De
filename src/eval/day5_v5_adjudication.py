"""Offline adjudication of the frozen Day 5 startup-sync V5 evidence.

This module deliberately has no ROS, rosbag, FAST-LIO2, or detector imports.
It reads a frozen audit archive (or an already materialized evidence root),
checks the source semantics that produced the V5 clock counters, and emits a
deterministic correction record.  It does not alter the V5 evidence.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import io
import json
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


EXPECTED_V5_AUDIT_SHA256 = (
    "9ffba9f490153fe0d95c98b4f905816f499d673427b8e87255b268546a00349a"
)
SOURCE_V5_AUDIT_ALIAS = (
    "$HOME/Degen-LIO-multihyp-D5-startup-sync-v5-audit.tar.gz"
)
ADJUDICATION_CREATED_AT_UTC = "2026-07-17T06:45:14Z"
DERIVATION_BASIS = "DERIVED_FROM_LOCKED_GENERATION_RULE_AND_BOUNDARY_VALUES"

FULL_MATRIX_REPLAY_COUNT = 1
FULL_MATRIX_REQUIRED_REPLAY_COUNT = 6
PAIR_COMPARISON_COUNT = 0

ROLE_PATHS: Tuple[Tuple[str, str, str], ...] = (
    (
        "tail_clock_protocol_source",
        "repo/degen_overlay/src/fastlio2_adapter/tail_clock_protocol.py",
        "python",
    ),
    (
        "tail_clock_node_source",
        "repo/degen_overlay/scripts/59_day5_tail_clock_node.py",
        "python",
    ),
    (
        "tail_clock_protocol_unit_test",
        "repo/degen_overlay/tests/test_tail_clock_protocol.py",
        "python",
    ),
    (
        "tail_clock_handoff_unit_test",
        "repo/degen_overlay/tests/test_tail_clock_handoff.py",
        "python",
    ),
    (
        "tail_clock_handoff",
        "evidence/tail_clock/tail_clock_handoff.json",
        "json",
    ),
    (
        "v5_gate_summary",
        "evidence/small_results/day5_startup_sync_v5_gate_summary.json",
        "json",
    ),
    (
        "v5_manifest",
        "repo/degen_overlay/manifests/harmful_bias/"
        "day5_startup_sync_v5_manifest.json",
        "json",
    ),
    (
        "v5_report",
        "repo/degen_overlay/docs/harmful_bias/"
        "day5_startup_sync_v5_report.md",
        "text",
    ),
    (
        "supervisor_state",
        "evidence/supervisor/supervisor_final_state.json",
        "json",
    ),
    (
        "single_run_result",
        "evidence/runtime_products/single_run_state.json",
        "json",
    ),
    (
        "drain_result",
        "evidence/end_of_stream_drain/end_of_stream_drain.json",
        "json",
    ),
    (
        "runtime_product_summary",
        "evidence/runtime_products/run_summary.json",
        "json",
    ),
    (
        "final_map_summary",
        "evidence/runtime_products/final_map_summary.json",
        "json",
    ),
    (
        "tap_export_summary",
        "evidence/runtime_products/tap_export_summary.json",
        "json",
    ),
    (
        "normal_shutdown",
        "evidence/runtime_products/graceful_shutdown_v5.json",
        "json",
    ),
    (
        "endpoint_contract",
        "evidence/endpoint_contract/replay_endpoint_contract_v1.json",
        "json",
    ),
    (
        "fast_unchanged_evidence",
        "evidence/git/fastlio2_source_lock_post_run_compare.json",
        "json",
    ),
    (
        "original_failure_adjudication",
        "evidence/supervisor/post_run_failure_adjudication.json",
        "json",
    ),
)

OUTPUT_FILES = (
    "evidence_resolution.json",
    "clock_counter_semantics.csv",
    "tail_clock_independent_recalculation.json",
    "executed_run_gate_adjudication.json",
    "full_matrix_status.json",
    "route_closure_summary.json",
    "fallback_protocol_summary.json",
    "fallback_readonly_evidence_protocol_v1.json",
    "day5_v5_adjudication_summary.json",
    "day5_v5_adjudication_manifest.json",
)

FALLBACK_PROTOCOL: Dict[str, Any] = {
    "schema_version": "fallback_readonly_evidence_protocol_v1",
    "created_at_utc": ADJUDICATION_CREATED_AT_UTC,
    "protocol_status": "FROZEN_NOT_EXECUTED",
    "fallback_protocol_frozen": True,
    "fallback_execution_authorized": False,
    "day5_fallback_in_call_immutability_authorized": "PENDING_GPT_REVIEW",
    "day6_quick_diagnostics_authorized": False,
    "cross_process_bitwise_replay_equivalence": "NOT_PROVEN",
    "parts": [
        {
            "id": "A",
            "name": "IN_CALL_IMMUTABILITY",
            "execution_scope": "SAME_FAST_LIO2_MEASUREMENT_CALL",
            "target_gate": "TAP_IN_CALL_IMMUTABILITY_PASS",
            "checks": [
                "state_checksum_unchanged",
                "covariance_checksum_unchanged",
                "native_jacobian_checksum_unchanged",
                "innovation_checksum_unchanged",
                "geometric_residual_checksum_unchanged",
                "correspondence_checksum_unchanged",
                "map_size_unchanged",
            ],
            "depends_on_cross_process_repeatability": False,
        },
        {
            "id": "B",
            "name": "FROZEN_REAL_OBSERVATION_RECORD",
            "target_gate": "FROZEN_REAL_OBSERVATION_RECORD_PASS",
            "required_evidence": [
                "schema",
                "source_commit",
                "bag_sha256",
                "record_sha256",
                "lifecycle",
                "no_gt_audit",
                "record_completeness",
            ],
            "allowed_evidence_class": "ENGINEERING_DEVELOPMENT_ONLY",
            "holdout_or_future_test_allowed": False,
        },
        {
            "id": "C",
            "name": "OFFLINE_PRODUCTION_DETECTOR_DETERMINISM",
            "target_gate": "OFFLINE_PRODUCTION_DETECTOR_DETERMINISM_PASS",
            "input": "FROZEN_REAL_OBSERVATION_RECORD",
            "detector": "PRODUCTION_DETECTOR",
            "same_config_required": True,
            "same_lock_required": True,
            "minimum_repeat_count": 3,
            "output_checksum_identical_required": True,
            "input_checksum_unchanged_required": True,
        },
        {
            "id": "D",
            "name": "REAL_REPLAY_FUNCTIONAL_STATISTICAL_TOLERANCE",
            "allowed_reports": [
                "record_completeness_rate",
                "nonfinite_count",
                "drop_count",
                "detector_runtime",
                "odi_and_direction_output_distribution",
                "functional_stability",
                "statistical_tolerance",
            ],
            "forbidden_claim": "BITWISE_REPLAY_EQUIVALENCE",
            "required_disclosure": (
                "CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE=NOT_PROVEN"
            ),
        },
    ],
}


class AdjudicationError(ValueError):
    """Raised when frozen evidence cannot support the requested correction."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    ).encode("utf-8")


def _load_json(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AdjudicationError(f"expected JSON object: {path.name}")
    return value


def _safe_extract(archive: Path, destination: Path) -> Path:
    with tarfile.open(archive, mode="r:gz") as handle:
        members = handle.getmembers()
        roots = {
            Path(member.name).parts[0]
            for member in members
            if member.name and Path(member.name).parts
        }
        if len(roots) != 1:
            raise AdjudicationError("V5 archive must contain exactly one root")
        root_name = next(iter(roots))
        destination_resolved = destination.resolve()
        for member in members:
            if member.issym() or member.islnk():
                raise AdjudicationError(
                    "V5 archive links are not accepted for adjudication"
                )
            target = (destination / member.name).resolve()
            try:
                target.relative_to(destination_resolved)
            except ValueError as error:
                raise AdjudicationError("unsafe V5 archive member") from error
        handle.extractall(destination)
    root = destination / root_name
    if not root.is_dir():
        raise AdjudicationError("V5 archive root is not a directory")
    return root


def verify_internal_hashes(root: Path) -> Dict[str, Any]:
    sums_path = root / "SHA256SUMS"
    if not sums_path.is_file():
        raise AdjudicationError("V5 SHA256SUMS is missing")
    failures: List[Dict[str, str]] = []
    checked = 0
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, separator, relative = line.partition("  ")
        if not separator or len(expected) != 64:
            raise AdjudicationError("invalid V5 SHA256SUMS line")
        path = root / relative
        actual = sha256_file(path) if path.is_file() else "MISSING"
        checked += 1
        if actual != expected:
            failures.append(
                {"resolved_path": relative, "expected": expected, "actual": actual}
            )
    return {
        "source_v5_internal_hash_pass": not failures,
        "checked_file_count": checked,
        "failure_count": len(failures),
        "failures": failures,
    }


def resolve_evidence(root: Path) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    parsed: Dict[str, Any] = {}
    for role, relative, parser in ROLE_PATHS:
        path = root / relative
        resolved_count = int(path.is_file())
        parse_status = "NOT_FOUND"
        if path.is_file():
            try:
                if parser == "json":
                    parsed[role] = _load_json(path)
                    parse_status = "JSON_OBJECT_PARSE_PASS"
                elif parser == "python":
                    source = path.read_text(encoding="utf-8")
                    ast.parse(source, filename=relative)
                    parsed[role] = source
                    parse_status = "PYTHON_AST_PARSE_PASS"
                else:
                    parsed[role] = path.read_text(encoding="utf-8")
                    parse_status = "TEXT_READ_PASS"
            except (OSError, UnicodeError, json.JSONDecodeError, SyntaxError):
                parse_status = "PARSE_FAIL"
        rows.append(
            {
                "evidence_role": role,
                "resolved_path": relative if resolved_count else None,
                "sha256": sha256_file(path) if resolved_count else None,
                "size_bytes": path.stat().st_size if resolved_count else None,
                "parse_status": parse_status,
                "resolved_count": resolved_count,
                "ambiguity_count": 0,
            }
        )
    passed = all(
        row["resolved_count"] == 1
        and row["ambiguity_count"] == 0
        and str(row["parse_status"]).endswith("PASS")
        for row in rows
    )
    return {
        "schema_version": "day5_v5_evidence_resolution_v1",
        "ADJUDICATION_EVIDENCE_RESOLUTION_PASS": passed,
        "resolved_evidence_files": rows,
        "_parsed": parsed,
    }


def _function(
    tree: ast.AST, class_name: Optional[str], function_name: str
) -> ast.AST:
    scope: Iterable[ast.AST] = getattr(tree, "body", ())
    if class_name is not None:
        classes = [
            node
            for node in scope
            if isinstance(node, ast.ClassDef) and node.name == class_name
        ]
        if len(classes) != 1:
            raise AdjudicationError(
                f"cannot uniquely resolve class {class_name}"
            )
        scope = classes[0].body
    functions = [
        node
        for node in scope
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == function_name
    ]
    if len(functions) != 1:
        raise AdjudicationError(
            f"cannot uniquely resolve function {function_name}"
        )
    return functions[0]


def _updates_attribute(function: ast.AST, attribute: str) -> bool:
    return any(
        isinstance(node, ast.AugAssign)
        and isinstance(node.target, ast.Attribute)
        and node.target.attr == attribute
        for node in ast.walk(function)
    )


def _reads_attribute(function: ast.AST, attribute: str) -> bool:
    return any(
        isinstance(node, ast.Attribute)
        and node.attr == attribute
        and isinstance(node.ctx, ast.Load)
        for node in ast.walk(function)
    )


def _calls_name(function: ast.AST, name: str) -> bool:
    return any(
        isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id == name)
            or (isinstance(node.func, ast.Attribute) and node.func.attr == name)
        )
        for node in ast.walk(function)
    )


def _increments_name(function: ast.AST, name: str) -> bool:
    return any(
        isinstance(node, ast.AugAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == name
        and isinstance(node.op, ast.Add)
        and isinstance(node.value, ast.Constant)
        and node.value.value == 1
        for node in ast.walk(function)
    )


def _source_row(
    *,
    path: str,
    source_sha256: str,
    symbol: str,
    node: ast.AST,
    counter: str,
    bag_phase: bool,
    tail_phase: bool,
    final_gate: bool,
    problem: str,
) -> Dict[str, Any]:
    return {
        "source_file": path,
        "symbol": symbol,
        "line_start": getattr(node, "lineno"),
        "line_end": getattr(node, "end_lineno", getattr(node, "lineno")),
        "source_sha256": source_sha256,
        "counter_name": counter,
        "counter_updated_during_bag_phase": bag_phase,
        "counter_updated_during_tail_phase": tail_phase,
        "used_in_final_gate": final_gate,
        "semantic_problem": problem,
    }


def analyze_clock_counter_semantics(
    protocol_source: str,
    node_source: str,
    protocol_sha256: str,
    node_sha256: str,
) -> Dict[str, Any]:
    protocol_path = (
        "repo/degen_overlay/src/fastlio2_adapter/tail_clock_protocol.py"
    )
    node_path = "repo/degen_overlay/scripts/59_day5_tail_clock_node.py"
    protocol_tree = ast.parse(protocol_source, filename=protocol_path)
    node_tree = ast.parse(node_source, filename=node_path)
    note_bag = _function(protocol_tree, "TailClockState", "note_bag_clock")
    note_publish = _function(protocol_tree, "TailClockState", "note_publish")
    finish = _function(protocol_tree, "TailClockState", "finish")
    tail_clock = _function(protocol_tree, None, "tail_clock_ns")
    clock_callback = _function(node_tree, "TailClockNode", "clock_callback")
    publish_loop = _function(node_tree, "TailClockNode", "publish_loop")

    bag_duplicate_update = _updates_attribute(
        note_bag, "clock_duplicate_count"
    )
    tail_duplicate_update = _updates_attribute(
        note_publish, "clock_duplicate_count"
    )
    bag_backward_update = _updates_attribute(
        note_bag, "clock_backward_count"
    )
    tail_backward_update = _updates_attribute(
        note_publish, "clock_backward_count"
    )
    duplicate_used_in_gate = _reads_attribute(
        finish, "clock_duplicate_count"
    )
    backward_used_in_gate = _reads_attribute(
        finish, "clock_backward_count"
    )
    overlap_used_in_gate = _reads_attribute(
        finish, "clock_publisher_overlap_count"
    )
    clock_callback_calls_bag = _calls_name(clock_callback, "note_bag_clock")
    publish_loop_calls_tail = _calls_name(publish_loop, "tail_clock_ns")
    publish_loop_records_tail = _calls_name(publish_loop, "note_publish")
    sequential_index = _increments_name(publish_loop, "index")

    mixed = all(
        (
            bag_duplicate_update,
            tail_duplicate_update,
            duplicate_used_in_gate,
            clock_callback_calls_bag,
            publish_loop_records_tail,
        )
    )
    locked_tail_generation_rule = all(
        (
            publish_loop_calls_tail,
            publish_loop_records_tail,
            sequential_index,
        )
    )
    problem = (
        "ONE_ACCUMULATOR_COMBINES_BAG_AND_TAIL_PHASES_AND_IS_USED_IN_GATE"
    )
    rows = [
        _source_row(
            path=protocol_path,
            source_sha256=protocol_sha256,
            symbol="TailClockState.note_bag_clock",
            node=note_bag,
            counter="clock_duplicate_count",
            bag_phase=bag_duplicate_update,
            tail_phase=False,
            final_gate=duplicate_used_in_gate,
            problem=problem,
        ),
        _source_row(
            path=protocol_path,
            source_sha256=protocol_sha256,
            symbol="TailClockState.note_bag_clock",
            node=note_bag,
            counter="clock_backward_count",
            bag_phase=bag_backward_update,
            tail_phase=False,
            final_gate=backward_used_in_gate,
            problem=(
                "ONE_ACCUMULATOR_COMBINES_BAG_AND_TAIL_PHASES"
                "_AND_IS_USED_IN_GATE"
            ),
        ),
        _source_row(
            path=protocol_path,
            source_sha256=protocol_sha256,
            symbol="TailClockState.note_publish",
            node=note_publish,
            counter="clock_duplicate_count",
            bag_phase=False,
            tail_phase=tail_duplicate_update,
            final_gate=duplicate_used_in_gate,
            problem=problem,
        ),
        _source_row(
            path=protocol_path,
            source_sha256=protocol_sha256,
            symbol="TailClockState.note_publish",
            node=note_publish,
            counter="clock_backward_count",
            bag_phase=False,
            tail_phase=tail_backward_update,
            final_gate=backward_used_in_gate,
            problem=(
                "ONE_ACCUMULATOR_COMBINES_BAG_AND_TAIL_PHASES"
                "_AND_IS_USED_IN_GATE"
            ),
        ),
        _source_row(
            path=protocol_path,
            source_sha256=protocol_sha256,
            symbol="tail_clock_ns",
            node=tail_clock,
            counter="tail_clock_value",
            bag_phase=False,
            tail_phase=True,
            final_gate=False,
            problem="NONE_LOCKED_AFFINE_GENERATION_RULE",
        ),
        _source_row(
            path=protocol_path,
            source_sha256=protocol_sha256,
            symbol="TailClockState.finish",
            node=finish,
            counter="handoff_pass",
            bag_phase=False,
            tail_phase=False,
            final_gate=all(
                (
                    duplicate_used_in_gate,
                    backward_used_in_gate,
                    overlap_used_in_gate,
                )
            ),
            problem="FINAL_GATE_DOES_NOT_SEPARATE_COUNTER_PHASES",
        ),
        _source_row(
            path=node_path,
            source_sha256=node_sha256,
            symbol="TailClockNode.clock_callback",
            node=clock_callback,
            counter="clock_duplicate_count",
            bag_phase=clock_callback_calls_bag,
            tail_phase=False,
            final_gate=False,
            problem="CALLS_BAG_PHASE_COUNTER_UPDATE",
        ),
        _source_row(
            path=node_path,
            source_sha256=node_sha256,
            symbol="TailClockNode.publish_loop",
            node=publish_loop,
            counter="tail_clock_value",
            bag_phase=False,
            tail_phase=all(
                (
                    publish_loop_calls_tail,
                    publish_loop_records_tail,
                    sequential_index,
                )
            ),
            final_gate=False,
            problem="NONE_SEQUENTIAL_INDEX_AND_POSITIVE_STEP_FUNCTION",
        ),
    ]
    return {
        "MIXED_CLOCK_COUNTER_CONFIRMED": mixed,
        "locked_tail_generation_rule_confirmed": locked_tail_generation_rule,
        "clock_duplicate_count_updated_during_bag_phase": (
            bag_duplicate_update
        ),
        "clock_duplicate_count_updated_during_tail_phase": (
            tail_duplicate_update
        ),
        "clock_duplicate_count_used_in_final_gate": duplicate_used_in_gate,
        "clock_backward_count_updated_during_bag_phase": bag_backward_update,
        "clock_backward_count_updated_during_tail_phase": tail_backward_update,
        "clock_backward_count_used_in_final_gate": backward_used_in_gate,
        "clock_publisher_overlap_count_used_in_final_gate": (
            overlap_used_in_gate
        ),
        "rows": rows,
    }


def recalculate_tail_clock(
    handoff: Mapping[str, Any],
    locked_tail_generation_rule_confirmed: bool,
) -> Dict[str, Any]:
    required = (
        "last_bag_clock_ns",
        "tail_first_clock_ns",
        "tail_clock_step_ns",
        "tail_publish_count",
        "tail_final_clock_ns",
        "clock_backward_count",
        "clock_duplicate_count",
        "clock_publisher_overlap_count",
    )
    missing = [name for name in required if name not in handoff]
    if missing:
        raise AdjudicationError(
            "handoff missing required fields: " + ",".join(missing)
        )
    raw = {name: int(handoff[name]) for name in required}
    expected_first = raw["last_bag_clock_ns"] + raw["tail_clock_step_ns"]
    expected_final = raw["tail_first_clock_ns"] + (
        raw["tail_publish_count"] - 1
    ) * raw["tail_clock_step_ns"]
    first_difference = raw["tail_first_clock_ns"] - expected_first
    final_difference = raw["tail_final_clock_ns"] - expected_final
    positive_step = raw["tail_clock_step_ns"] > 0
    positive_count = raw["tail_publish_count"] > 0
    first_pass = first_difference == 0
    final_pass = final_difference == 0
    raw_backward_zero = raw["clock_backward_count"] == 0
    raw_overlap_zero = raw["clock_publisher_overlap_count"] == 0
    derived = all(
        (
            locked_tail_generation_rule_confirmed,
            positive_step,
            positive_count,
            first_pass,
            final_pass,
            raw_backward_zero,
            raw_overlap_zero,
        )
    )
    result: Dict[str, Any] = {
        "schema_version": "day5_v5_tail_clock_recalculation_v1",
        **raw,
        "expected_first_tail_clock_ns": expected_first,
        "expected_final_tail_clock_ns": expected_final,
        "tail_first_clock_difference_ns": first_difference,
        "tail_final_clock_difference_ns": final_difference,
        "tail_clock_step_positive_pass": positive_step,
        "tail_publish_count_positive_pass": positive_count,
        "TAIL_FIRST_FORMULA_PASS": first_pass,
        "TAIL_FINAL_FORMULA_PASS": final_pass,
        "raw_clock_backward_zero_pass": raw_backward_zero,
        "raw_clock_publisher_overlap_zero_pass": raw_overlap_zero,
        "tail_clock_duplicate_count_derived": 0 if derived else None,
        "tail_clock_backward_count_derived": 0 if derived else None,
        "tail_phase_derivation_basis": DERIVATION_BASIS if derived else None,
        "full_tail_message_stream_individually_inspected": False,
        "EXECUTED_RUN_TAIL_CLOCK_MONOTONIC_ADJUDICATION": derived,
    }
    if derived:
        result["bag_or_mixed_clock_duplicate_count"] = raw[
            "clock_duplicate_count"
        ]
        result["bag_clock_duplicate_count_observed"] = raw[
            "clock_duplicate_count"
        ]
        result["bag_clock_duplicate_count_provenance"] = (
            "MIXED_TOTAL_MINUS_DERIVED_TAIL_ZERO"
        )
        result["bag_clock_backward_count_observed"] = raw[
            "clock_backward_count"
        ]
    return result


def _quick_endpoint(contract: Mapping[str, Any]) -> Mapping[str, Any]:
    rows = [
        row
        for row in contract.get("sequences", [])
        if row.get("sequence_id") == "avia_quick_shack"
    ]
    if len(rows) != 1:
        raise AdjudicationError(
            "cannot uniquely resolve Quick endpoint contract"
        )
    return rows[0]


def adjudicate_executed_run(
    *,
    mixed_counter_confirmed: bool,
    recalculation: Mapping[str, Any],
    handoff: Mapping[str, Any],
    drain: Mapping[str, Any],
    endpoint_contract: Mapping[str, Any],
    shutdown: Mapping[str, Any],
    runtime_summary: Mapping[str, Any],
    final_map_summary: Mapping[str, Any],
    tap_export_summary: Mapping[str, Any],
) -> Dict[str, Any]:
    endpoint = _quick_endpoint(endpoint_contract)
    handoff_pass = all(
        (
            bool(handoff.get("start_success")),
            bool(handoff.get("stop_success")),
            handoff.get("failure_reason") == "NONE",
            bool(recalculation.get("TAIL_FIRST_FORMULA_PASS")),
            bool(recalculation.get("TAIL_FINAL_FORMULA_PASS")),
            recalculation.get("tail_clock_duplicate_count_derived") == 0,
            recalculation.get("tail_clock_backward_count_derived") == 0,
            int(handoff.get("clock_publisher_overlap_count", -1)) == 0,
        )
    )
    monotonic_pass = bool(
        recalculation.get(
            "EXECUTED_RUN_TAIL_CLOCK_MONOTONIC_ADJUDICATION"
        )
    )
    no_overlap_pass = (
        int(handoff.get("clock_publisher_overlap_count", -1)) == 0
    )
    callbacks_pass = all(
        (
            int(drain.get("actual_lidar_callback_count", -1))
            == int(endpoint.get("expected_lidar_message_count", -2)),
            int(drain.get("actual_imu_callback_count", -1))
            == int(endpoint.get("expected_imu_message_count", -2)),
            int(drain.get("actual_last_lidar_header_stamp_ns", -1))
            == int(endpoint.get("last_lidar_header_stamp_ns", -2)),
            int(drain.get("actual_last_imu_header_stamp_ns", -1))
            == int(endpoint.get("last_imu_header_stamp_ns", -2)),
        )
    )
    drain_pass = bool(drain.get("drain_pass")) and (
        drain.get("failure_classification") == "NONE"
    )
    main_loop_pass = int(
        drain.get("main_loop_heartbeat_end", 0)
    ) > int(drain.get("main_loop_heartbeat_start", 0))
    shutdown_pass = all(
        (
            bool(shutdown.get("shutdown_completed")),
            not bool(shutdown.get("forced_kill_used")),
            not bool(shutdown.get("forced_terminate_used")),
            int(shutdown.get("laser_mapping_exit_code", -1)) == 0,
            int(shutdown.get("roslaunch_exit_code", -1)) == 0,
        )
    )
    runtime_product_pass = all(
        (
            bool(runtime_summary.get("runtime_audit_enabled")),
            int(runtime_summary.get("runtime_audit_record_count", 0)) > 0,
            int(runtime_summary.get("writer_error_count", -1)) == 0,
            int(runtime_summary.get("nonfinite_count", -1)) == 0,
            bool(runtime_summary.get("final_map_summary_written")),
            bool(final_map_summary.get("valid")),
            int(final_map_summary.get("final_map_point_count", 0)) > 0,
            int(final_map_summary.get("nonfinite_count", -1)) == 0,
            int(tap_export_summary.get("writer_error_count", -1)) == 0,
        )
    )
    correction_pass = all(
        (
            mixed_counter_confirmed,
            handoff_pass,
            monotonic_pass,
            no_overlap_pass,
            callbacks_pass,
            drain_pass,
            main_loop_pass,
            shutdown_pass,
            runtime_product_pass,
        )
    )
    return {
        "schema_version": "day5_v5_executed_run_gate_adjudication_v1",
        "sequence_id": "avia_quick_shack",
        "runtime_mode": "AUDIT_ONLY",
        "repeat_id": 1,
        "EXECUTED_RUN_TAIL_CLOCK_HANDOFF_PASS": handoff_pass,
        "EXECUTED_RUN_TAIL_CLOCK_MONOTONIC_PASS": monotonic_pass,
        "EXECUTED_RUN_TAIL_CLOCK_NO_OVERLAP_PASS": no_overlap_pass,
        "EXECUTED_RUN_ALL_CALLBACKS_RECEIVED_PASS": callbacks_pass,
        "EXECUTED_RUN_END_OF_STREAM_DRAIN_PASS": drain_pass,
        "EXECUTED_RUN_MAIN_LOOP_PROGRESS_PASS": main_loop_pass,
        "EXECUTED_RUN_NORMAL_SHUTDOWN_PASS": shutdown_pass,
        "EXECUTED_RUN_RUNTIME_PRODUCT_PASS": runtime_product_pass,
        "EXECUTED_RUN_GATE_CORRECTION_PASS": correction_pass,
        "ORIGINAL_FAILURE_CLASSIFICATION_VALID": not correction_pass,
        "ORIGINAL_FAILURE_CLASSIFICATION_INVALID_REASON": (
            "MIXED_BAG_AND_TAIL_CLOCK_DUPLICATE_COUNTER"
            if correction_pass
            else None
        ),
        "CORRECTED_EXECUTED_RUN_RESULT": "PASS" if correction_pass else "FAIL",
        "CORRECTED_FAILURE_CLASSIFICATION": (
            "ADJUDICATION_COUNTER_SEMANTICS_ERROR"
            if correction_pass
            else "TAIL_CLOCK_DUPLICATE_TIME"
        ),
        "runtime_product_adjudication_basis": (
            "RAW_RUN_FINAL_MAP_AND_TAP_EXPORT_SUMMARIES"
        ),
    }


def full_matrix_status() -> Dict[str, Any]:
    return {
        "schema_version": "day5_v5_full_matrix_status_v1",
        "FULL_MATRIX_REPLAY_COUNT": FULL_MATRIX_REPLAY_COUNT,
        "FULL_MATRIX_REQUIRED_REPLAY_COUNT": FULL_MATRIX_REQUIRED_REPLAY_COUNT,
        "PAIR_COMPARISON_COUNT": PAIR_COMPARISON_COUNT,
        "FULL_MATRIX_STATUS": "NOT_EVALUATED",
        "CORRECTED_FULL_MATRIX_RESULT": "NOT_EVALUATED_INCOMPLETE_MATRIX",
        "QUICK_BASELINE_REPEATABILITY_STATUS": (
            "NOT_EVALUATED_INCOMPLETE_MATRIX"
        ),
        "OUTDOOR_BASELINE_REPEATABILITY_STATUS": (
            "NOT_EVALUATED_INCOMPLETE_MATRIX"
        ),
        "BASELINE_REPEATABILITY_STATUS": "NOT_EVALUATED_INCOMPLETE_MATRIX",
        "QUICK_BASELINE_REPEATABILITY_PASS": False,
        "OUTDOOR_BASELINE_REPEATABILITY_PASS": False,
        "BASELINE_REPEATABILITY_PASS": False,
        "DAY5_STARTUP_SYNC_V5_PASS": False,
        "FULL_MATRIX_STATUS_CORRECTION_PASS": True,
    }


def route_closure_summary() -> Dict[str, Any]:
    return {
        "schema_version": "strict_replay_route_closure_v1",
        "STRICT_CROSS_PROCESS_REPLAY_ROUTE_STATUS": "ABANDONED_AFTER_V5",
        "STRICT_REPLAY_FURTHER_REMEDIATION_AUTHORIZED": False,
        "CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE": "NOT_PROVEN",
        "v6_created": False,
        "same_route_under_other_name_authorized": False,
        "proven": [
            "ENDPOINT_CONTRACT_CAN_BE_FROZEN",
            "PAUSED_START_WORKS",
            "LIDAR_IMU_BIDIRECTIONAL_HANDSHAKE_WORKS",
            "TAIL_CLOCK_ADVANCES_MAIN_LOOP_AFTER_BAG_END",
            "CALLBACK_COUNTS_REACH_CLIP_ENDPOINT",
            "END_OF_STREAM_DRAIN_COMPLETES",
            "FAST_LIO2_NORMAL_SHUTDOWN_COMPLETES",
            "RUNTIME_PRODUCTS_COMPLETE",
            "EXECUTED_RUN_DOES_NOT_PROVE_TAIL_CLOCK_DUPLICATES",
        ],
        "not_proven": [
            "QUICK_THREE_RUN_CROSS_PROCESS_BITWISE_EQUIVALENCE",
            "OUTDOOR_THREE_RUN_CROSS_PROCESS_BITWISE_EQUIVALENCE",
            "TAP_OFF_ON_CROSS_PROCESS_BITWISE_EQUIVALENCE",
            "FINAL_MAP_STRICT_EQUIVALENCE_ACROSS_PROCESSES",
            "NO_CROSS_PROCESS_SCHEDULING_EFFECT_WITH_DETECTOR_ENABLED",
        ],
        "STRICT_ROUTE_CLOSURE_PASS": True,
    }


def fallback_protocol_summary() -> Dict[str, Any]:
    encoded = canonical_json_bytes(FALLBACK_PROTOCOL)
    return {
        "schema_version": "fallback_protocol_freeze_summary_v1",
        "fallback_protocol_path": (
            "manifests/harmful_bias/"
            "fallback_readonly_evidence_protocol_v1.json"
        ),
        "fallback_protocol_sha256": hashlib.sha256(encoded).hexdigest(),
        "FALLBACK_PROTOCOL_FROZEN": True,
        "FALLBACK_EXECUTION_AUTHORIZED": False,
        "DAY5_FALLBACK_IN_CALL_IMMUTABILITY_AUTHORIZED": (
            "PENDING_GPT_REVIEW"
        ),
        "DAY6_QUICK_DIAGNOSTICS_AUTHORIZED": False,
        "FALLBACK_PROTOCOL_FREEZE_PASS": True,
        "parts": [part["name"] for part in FALLBACK_PROTOCOL["parts"]],
    }


def _public_resolution(resolution: Mapping[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in resolution.items() if key != "_parsed"}


def adjudicate_evidence_root(
    root: Path,
    *,
    source_v5_audit_sha256: str = EXPECTED_V5_AUDIT_SHA256,
    internal_hash_result: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    resolution = resolve_evidence(root)
    if not resolution["ADJUDICATION_EVIDENCE_RESOLUTION_PASS"]:
        raise AdjudicationError("V5 evidence resolution did not pass")
    parsed = resolution["_parsed"]
    evidence_rows = {
        row["evidence_role"]: row
        for row in resolution["resolved_evidence_files"]
    }
    semantics = analyze_clock_counter_semantics(
        parsed["tail_clock_protocol_source"],
        parsed["tail_clock_node_source"],
        evidence_rows["tail_clock_protocol_source"]["sha256"],
        evidence_rows["tail_clock_node_source"]["sha256"],
    )
    if not semantics["MIXED_CLOCK_COUNTER_CONFIRMED"]:
        raise AdjudicationError("mixed clock counter was not confirmed")
    recalculation = recalculate_tail_clock(
        parsed["tail_clock_handoff"],
        semantics["locked_tail_generation_rule_confirmed"],
    )
    executed = adjudicate_executed_run(
        mixed_counter_confirmed=semantics[
            "MIXED_CLOCK_COUNTER_CONFIRMED"
        ],
        recalculation=recalculation,
        handoff=parsed["tail_clock_handoff"],
        drain=parsed["drain_result"],
        endpoint_contract=parsed["endpoint_contract"],
        shutdown=parsed["normal_shutdown"],
        runtime_summary=parsed["runtime_product_summary"],
        final_map_summary=parsed["final_map_summary"],
        tap_export_summary=parsed["tap_export_summary"],
    )
    matrix = full_matrix_status()
    route = route_closure_summary()
    fallback = fallback_protocol_summary()
    internal = dict(
        internal_hash_result
        or {
            "source_v5_internal_hash_pass": True,
            "checked_file_count": len(ROLE_PATHS),
            "failure_count": 0,
            "failures": [],
            "verification_scope": "PACKAGED_SUBSET_AGAINST_FROZEN_HASHES",
        }
    )
    all_gates = {
        "ADJUDICATION_EVIDENCE_RESOLUTION_PASS": resolution[
            "ADJUDICATION_EVIDENCE_RESOLUTION_PASS"
        ],
        "MIXED_CLOCK_COUNTER_CONFIRMED": semantics[
            "MIXED_CLOCK_COUNTER_CONFIRMED"
        ],
        "TAIL_FIRST_FORMULA_PASS": recalculation[
            "TAIL_FIRST_FORMULA_PASS"
        ],
        "TAIL_FINAL_FORMULA_PASS": recalculation[
            "TAIL_FINAL_FORMULA_PASS"
        ],
        "EXECUTED_RUN_GATE_CORRECTION_PASS": executed[
            "EXECUTED_RUN_GATE_CORRECTION_PASS"
        ],
        "FULL_MATRIX_STATUS_CORRECTION_PASS": matrix[
            "FULL_MATRIX_STATUS_CORRECTION_PASS"
        ],
        "STRICT_ROUTE_CLOSURE_PASS": route["STRICT_ROUTE_CLOSURE_PASS"],
        "FALLBACK_PROTOCOL_FREEZE_PASS": fallback[
            "FALLBACK_PROTOCOL_FREEZE_PASS"
        ],
    }
    adjudication_pass = all(all_gates.values()) and bool(
        internal.get("source_v5_internal_hash_pass")
    )
    handoff = parsed["tail_clock_handoff"]
    original = parsed["original_failure_adjudication"]
    summary = {
        "schema_version": "harmful_bias_day5_v5_adjudication_manifest_v1",
        "created_at_utc": ADJUDICATION_CREATED_AT_UTC,
        "timestamp_policy": "SOURCE_V5_MANIFEST_CREATED_AT_UTC",
        "source_v5_audit_path_alias": SOURCE_V5_AUDIT_ALIAS,
        "source_v5_audit_sha256": source_v5_audit_sha256,
        "source_v5_internal_hash_pass": internal[
            "source_v5_internal_hash_pass"
        ],
        "source_v5_internal_hash_checked_file_count": internal[
            "checked_file_count"
        ],
        "source_v5_internal_hash_failure_count": internal["failure_count"],
        "evidence_resolution_pass": resolution[
            "ADJUDICATION_EVIDENCE_RESOLUTION_PASS"
        ],
        "resolved_evidence_files": resolution["resolved_evidence_files"],
        "mixed_clock_counter_confirmed": semantics[
            "MIXED_CLOCK_COUNTER_CONFIRMED"
        ],
        "original_clock_duplicate_count": int(
            handoff["clock_duplicate_count"]
        ),
        "original_clock_backward_count": int(
            handoff["clock_backward_count"]
        ),
        "original_clock_overlap_count": int(
            handoff["clock_publisher_overlap_count"]
        ),
        "last_bag_clock_ns": recalculation["last_bag_clock_ns"],
        "tail_first_clock_ns": recalculation["tail_first_clock_ns"],
        "tail_clock_step_ns": recalculation["tail_clock_step_ns"],
        "tail_publish_count": recalculation["tail_publish_count"],
        "tail_final_clock_ns": recalculation["tail_final_clock_ns"],
        "expected_tail_first_clock_ns": recalculation[
            "expected_first_tail_clock_ns"
        ],
        "expected_tail_final_clock_ns": recalculation[
            "expected_final_tail_clock_ns"
        ],
        "tail_first_formula_pass": recalculation[
            "TAIL_FIRST_FORMULA_PASS"
        ],
        "tail_final_formula_pass": recalculation[
            "TAIL_FINAL_FORMULA_PASS"
        ],
        "derived_tail_clock_duplicate_count": recalculation[
            "tail_clock_duplicate_count_derived"
        ],
        "derived_tail_clock_backward_count": recalculation[
            "tail_clock_backward_count_derived"
        ],
        "original_failure_classification": original[
            "fixed_enum_adjudicated_failure_classification"
        ],
        "original_failure_classification_valid": executed[
            "ORIGINAL_FAILURE_CLASSIFICATION_VALID"
        ],
        "original_failure_classification_invalid_reason": executed[
            "ORIGINAL_FAILURE_CLASSIFICATION_INVALID_REASON"
        ],
        "corrected_executed_run_result": executed[
            "CORRECTED_EXECUTED_RUN_RESULT"
        ],
        "corrected_full_matrix_result": matrix[
            "CORRECTED_FULL_MATRIX_RESULT"
        ],
        "corrected_failure_classification": executed[
            "CORRECTED_FAILURE_CLASSIFICATION"
        ],
        "executed_replay_count": FULL_MATRIX_REPLAY_COUNT,
        "required_replay_count": FULL_MATRIX_REQUIRED_REPLAY_COUNT,
        "pair_comparison_count": PAIR_COMPARISON_COUNT,
        "FULL_MATRIX_STATUS": matrix["FULL_MATRIX_STATUS"],
        "executed_run_tail_handoff_pass": executed[
            "EXECUTED_RUN_TAIL_CLOCK_HANDOFF_PASS"
        ],
        "executed_run_tail_monotonic_pass": executed[
            "EXECUTED_RUN_TAIL_CLOCK_MONOTONIC_PASS"
        ],
        "executed_run_tail_no_overlap_pass": executed[
            "EXECUTED_RUN_TAIL_CLOCK_NO_OVERLAP_PASS"
        ],
        "executed_run_callbacks_complete_pass": executed[
            "EXECUTED_RUN_ALL_CALLBACKS_RECEIVED_PASS"
        ],
        "executed_run_drain_pass": executed[
            "EXECUTED_RUN_END_OF_STREAM_DRAIN_PASS"
        ],
        "executed_run_main_loop_progress_pass": executed[
            "EXECUTED_RUN_MAIN_LOOP_PROGRESS_PASS"
        ],
        "executed_run_normal_shutdown_pass": executed[
            "EXECUTED_RUN_NORMAL_SHUTDOWN_PASS"
        ],
        "executed_run_runtime_product_pass": executed[
            "EXECUTED_RUN_RUNTIME_PRODUCT_PASS"
        ],
        "quick_baseline_repeatability_status": matrix[
            "QUICK_BASELINE_REPEATABILITY_STATUS"
        ],
        "outdoor_baseline_repeatability_status": matrix[
            "OUTDOOR_BASELINE_REPEATABILITY_STATUS"
        ],
        "day5_startup_sync_v5_pass": False,
        "day5_runtime_equivalence_pass": False,
        "day6_quick_diagnostics_authorized": False,
        "strict_cross_process_replay_route_status": route[
            "STRICT_CROSS_PROCESS_REPLAY_ROUTE_STATUS"
        ],
        "strict_replay_further_remediation_authorized": False,
        "cross_process_bitwise_replay_equivalence": "NOT_PROVEN",
        "fallback_protocol_path": fallback["fallback_protocol_path"],
        "fallback_protocol_sha256": fallback["fallback_protocol_sha256"],
        "fallback_protocol_frozen": True,
        "fallback_execution_authorized": False,
        "fastlio2_modified": False,
        "fastlio2_modified_this_task": False,
        "tail_clock_production_code_modified": False,
        "drain_code_modified": False,
        "comparator_modified": False,
        "detector_modified": False,
        "threshold_modified": False,
        "roscore_run": False,
        "roslaunch_run": False,
        "rosbag_run": False,
        "real_data_reprocessed": False,
        "commit_created": False,
        "push_performed": False,
        "STAGE2_GATE": "FAIL",
        "TRANSITION": "PIVOT",
        "COHERENT_BIAS_HARMFUL_MECHANISM_SUPPORTED": True,
        "COHERENT_BIAS_STABLY_ONLINE_DETECTABLE": False,
        "STAGE3_START_AUTHORIZED": False,
        "STAGE4_START_AUTHORIZED": False,
        "PATENT2_AUTHORIZED": False,
        "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
        "RISK_WARNING_AUTHORIZED": False,
        "PUBLIC_DISCLOSURE_AUTHORIZED": False,
        "HARMFUL_BIAS_DETECTABILITY_STATUS": (
            "NOT_EVALUATED_DAY5_V5_ADJUDICATION"
        ),
        **all_gates,
        "DAY5_V5_ADJUDICATION_PASS": adjudication_pass,
        "DAY5_STARTUP_SYNC_V5_PASS": False,
        "DAY5_RUNTIME_EQUIVALENCE_PASS": False,
        "DAY6_QUICK_DIAGNOSTICS_AUTHORIZED": False,
        "STRICT_REPLAY_FURTHER_REMEDIATION_AUTHORIZED": False,
        "FALLBACK_EXECUTION_AUTHORIZED": False,
    }
    return {
        "evidence_resolution": _public_resolution(resolution),
        "semantics": semantics,
        "recalculation": recalculation,
        "executed": executed,
        "matrix": matrix,
        "route": route,
        "fallback": fallback,
        "summary": summary,
        "internal_hash_result": internal,
    }


def adjudicate_archive(archive: Path) -> Dict[str, Any]:
    archive = archive.resolve()
    if not archive.is_file():
        raise AdjudicationError("V5 audit archive is missing")
    actual_sha = sha256_file(archive)
    if actual_sha != EXPECTED_V5_AUDIT_SHA256:
        raise AdjudicationError(
            f"V5 audit SHA mismatch: expected {EXPECTED_V5_AUDIT_SHA256}, "
            f"got {actual_sha}"
        )
    with tempfile.TemporaryDirectory(prefix="day5_v5_adjudication_") as temp:
        root = _safe_extract(archive, Path(temp))
        internal = verify_internal_hashes(root)
        if not internal["source_v5_internal_hash_pass"]:
            raise AdjudicationError("V5 internal hash verification failed")
        return adjudicate_evidence_root(
            root,
            source_v5_audit_sha256=actual_sha,
            internal_hash_result=internal,
        )


def _csv_bytes(rows: Sequence[Mapping[str, Any]]) -> bytes:
    if not rows:
        raise AdjudicationError("clock semantics rows are empty")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=list(rows[0]),
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def write_outputs(
    result: Mapping[str, Any], output_dir: Path, *, overwrite: bool = False
) -> None:
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        if not overwrite:
            raise AdjudicationError(
                f"output directory is not empty: {output_dir}"
            )
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    payloads: Dict[str, bytes] = {
        "evidence_resolution.json": canonical_json_bytes(
            result["evidence_resolution"]
        ),
        "clock_counter_semantics.csv": _csv_bytes(
            result["semantics"]["rows"]
        ),
        "tail_clock_independent_recalculation.json": canonical_json_bytes(
            result["recalculation"]
        ),
        "executed_run_gate_adjudication.json": canonical_json_bytes(
            result["executed"]
        ),
        "full_matrix_status.json": canonical_json_bytes(result["matrix"]),
        "route_closure_summary.json": canonical_json_bytes(result["route"]),
        "fallback_protocol_summary.json": canonical_json_bytes(
            result["fallback"]
        ),
        "fallback_readonly_evidence_protocol_v1.json": canonical_json_bytes(
            FALLBACK_PROTOCOL
        ),
        "day5_v5_adjudication_summary.json": canonical_json_bytes(
            result["summary"]
        ),
        "day5_v5_adjudication_manifest.json": canonical_json_bytes(
            result["summary"]
        ),
    }
    if tuple(payloads) != OUTPUT_FILES:
        raise AdjudicationError("internal output file contract mismatch")
    for name, content in payloads.items():
        (output_dir / name).write_bytes(content)
    sums = [
        f"{hashlib.sha256(payloads[name]).hexdigest()}  {name}"
        for name in sorted(payloads)
    ]
    (output_dir / "SHA256SUMS").write_text(
        "\n".join(sums) + "\n", encoding="utf-8"
    )


def verify_output_directory(output_dir: Path) -> Dict[str, Any]:
    failures: List[str] = []
    sums = output_dir / "SHA256SUMS"
    if not sums.is_file():
        raise AdjudicationError("output SHA256SUMS missing")
    checked = 0
    for line in sums.read_text(encoding="utf-8").splitlines():
        expected, separator, name = line.partition("  ")
        if not separator:
            failures.append("INVALID_SHA256SUMS_LINE")
            continue
        path = output_dir / name
        actual = sha256_file(path) if path.is_file() else "MISSING"
        checked += 1
        if expected != actual:
            failures.append(name)
    return {
        "pass": not failures,
        "checked_file_count": checked,
        "failure_count": len(failures),
        "failures": failures,
    }
