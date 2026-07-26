"""Schema and fail-closed gates for the same-call read-only tap audit."""

from __future__ import annotations

import json
import re
from collections import OrderedDict
from typing import Any, Mapping


SCHEMA_VERSION = "in_call_immutability_status_v1"
CHECKSUM_ALGORITHM = "FNV1A64_EXACT_BYTES_V1"
MISMATCH_FIELDS = OrderedDict(
    (
        ("state_mismatch_count", "MEASUREMENT_STATE_IMMUTABILITY_PASS"),
        (
            "covariance_mismatch_count",
            "FILTER_COVARIANCE_IMMUTABILITY_PASS",
        ),
        ("jacobian_mismatch_count", "NATIVE_JACOBIAN_IMMUTABILITY_PASS"),
        (
            "innovation_mismatch_count",
            "FORMAL_INNOVATION_IMMUTABILITY_PASS",
        ),
        (
            "geometric_residual_mismatch_count",
            "GEOMETRIC_RESIDUAL_IMMUTABILITY_PASS",
        ),
        (
            "accepted_index_mismatch_count",
            "ACCEPTED_INDEX_IMMUTABILITY_PASS",
        ),
        (
            "correspondence_mismatch_count",
            "FORMAL_CORRESPONDENCE_IMMUTABILITY_PASS",
        ),
        ("map_size_mismatch_count", "MAP_SIZE_IMMUTABILITY_PASS"),
    )
)
INTEGER_FIELDS = (
    "audited_call_count",
    "all_unchanged_count",
    "mutation_detected_count",
    *MISMATCH_FIELDS.keys(),
    "tap_call_attempt_count",
    "tap_record_emitted_count",
    "nonfinite_checksum_input_count",
    "internal_audit_error_count",
)


class InCallImmutabilityError(ValueError):
    """The status or run evidence violates the frozen audit contract."""


def _fnv1a64(value: bytes) -> int:
    result = 14695981039346656037
    for byte in value:
        result ^= byte
        result = (result * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return result


def _checksum_payload(value: Mapping[str, Any]) -> str:
    first = value["first_mismatch"]
    return "".join(
        (
            f"schema_version={SCHEMA_VERSION}\n",
            f"enabled={'true' if value['enabled'] else 'false'}\n",
            f"audited_call_count={value['audited_call_count']}\n",
            f"all_unchanged_count={value['all_unchanged_count']}\n",
            f"mutation_detected_count={value['mutation_detected_count']}\n",
            f"state_mismatch_count={value['state_mismatch_count']}\n",
            f"covariance_mismatch_count={value['covariance_mismatch_count']}\n",
            f"jacobian_mismatch_count={value['jacobian_mismatch_count']}\n",
            f"innovation_mismatch_count={value['innovation_mismatch_count']}\n",
            "geometric_residual_mismatch_count="
            f"{value['geometric_residual_mismatch_count']}\n",
            "accepted_index_mismatch_count="
            f"{value['accepted_index_mismatch_count']}\n",
            "correspondence_mismatch_count="
            f"{value['correspondence_mismatch_count']}\n",
            f"map_size_mismatch_count={value['map_size_mismatch_count']}\n",
            f"has_first_mismatch={'true' if first is not None else 'false'}\n",
            "first_mismatch_scan_index="
            f"{first['scan_index'] if first is not None else 'null'}\n",
            "first_mismatch_measurement_call_index="
            f"{first['measurement_call_index'] if first is not None else 'null'}\n",
            "first_mismatch_fields="
            f"{','.join(first['fields']) if first is not None else ''}\n",
            f"tap_call_attempt_count={value['tap_call_attempt_count']}\n",
            f"tap_record_emitted_count={value['tap_record_emitted_count']}\n",
            "nonfinite_checksum_input_count="
            f"{value['nonfinite_checksum_input_count']}\n",
            "internal_audit_error_count="
            f"{value['internal_audit_error_count']}\n",
        )
    )


def expected_status_checksum(value: Mapping[str, Any]) -> str:
    checksum = _fnv1a64(_checksum_payload(value).encode("utf-8"))
    return f"FNV1A64:{checksum:016x}"


def validate_status(value: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version",
        "checksum_algorithm",
        "enabled",
        *INTEGER_FIELDS,
        "first_mismatch",
        "audit_status_checksum",
    }
    missing = sorted(required - set(value))
    if missing:
        raise InCallImmutabilityError(f"missing status fields: {missing}")
    if value["schema_version"] != SCHEMA_VERSION:
        raise InCallImmutabilityError("wrong status schema")
    if value["checksum_algorithm"] != CHECKSUM_ALGORITHM:
        raise InCallImmutabilityError("wrong checksum algorithm")
    if not isinstance(value["enabled"], bool):
        raise InCallImmutabilityError("enabled must be boolean")
    for field in INTEGER_FIELDS:
        if (
            not isinstance(value[field], int)
            or isinstance(value[field], bool)
            or value[field] < 0
        ):
            raise InCallImmutabilityError(
                f"{field} must be a nonnegative integer"
            )
    first = value["first_mismatch"]
    if first is not None:
        if not isinstance(first, Mapping):
            raise InCallImmutabilityError("first_mismatch must be null or object")
        if set(first) != {
            "scan_index",
            "measurement_call_index",
            "fields",
            "before_after",
        }:
            raise InCallImmutabilityError("first_mismatch fields are unstable")
        if not isinstance(first["fields"], list) or not all(
            isinstance(field, str) for field in first["fields"]
        ):
            raise InCallImmutabilityError("first mismatch fields must be text")
    checksum = value["audit_status_checksum"]
    if not isinstance(checksum, str) or not re.fullmatch(
        r"FNV1A64:[0-9a-f]{16}", checksum
    ):
        raise InCallImmutabilityError("invalid audit status checksum format")
    if checksum != expected_status_checksum(value):
        raise InCallImmutabilityError("audit status checksum mismatch")
    return dict(value)


def status_from_trigger_snapshot(value: Mapping[str, Any]) -> dict[str, Any]:
    return validate_status(value)


def evaluate_gate(
    status: Mapping[str, Any],
    run_facts: Mapping[str, Any],
) -> dict[str, Any]:
    value = validate_status(status)
    gates: OrderedDict[str, bool] = OrderedDict()
    gates["IN_CALL_HOOK_PLACEMENT_CONFIRMED"] = bool(
        run_facts.get("hook_placement_confirmed")
    )
    gates["CANONICAL_CHECKSUM_REUSE_PASS"] = bool(
        run_facts.get("canonical_checksum_reuse")
    )
    gates["COVARIANCE_IN_CALL_ACCESS_CONFIRMED"] = bool(
        run_facts.get("covariance_access_confirmed")
    )
    gates["IN_CALL_AUDIT_IMPLEMENTATION_PASS"] = bool(
        run_facts.get("implementation_pass")
    )
    gates["STATIC_READONLY_AUDIT_PASS"] = bool(
        run_facts.get("static_readonly_audit_pass")
    )
    gates["FAST_BUILD_PASS"] = bool(run_facts.get("fast_build_pass"))
    gates["FAST_TEST_PASS"] = bool(run_facts.get("fast_test_pass"))
    gates["DEGEN_TARGETED_TEST_PASS"] = bool(
        run_facts.get("degen_targeted_test_pass")
    )
    gates["DEGEN_FULL_TEST_PASS"] = bool(
        run_facts.get("degen_full_test_pass")
    )
    for name in (
        "REAL_ENGINEERING_RUN_COMPLETENESS_PASS",
        "ALL_CALLBACKS_RECEIVED_PASS",
        "END_OF_STREAM_DRAIN_PASS",
        "NORMAL_SHUTDOWN_PASS",
    ):
        gates[name] = bool(run_facts.get(name.lower()))
    gates["AUDITED_CALL_COUNT_POSITIVE_PASS"] = (
        value["audited_call_count"] > 0
    )
    gates["AUDITED_CALL_COVERAGE_PASS"] = (
        value["audited_call_count"] == value["tap_call_attempt_count"]
    )
    for field, gate in MISMATCH_FIELDS.items():
        gates[gate] = value[field] == 0
    gates["NO_NONFINITE_PASS"] = (
        value["nonfinite_checksum_input_count"] == 0
    )
    gates["NO_GT_PASS"] = bool(run_facts.get("no_gt_pass"))
    gates["NO_DROP_PASS"] = int(run_facts.get("tap_drop_count", -1)) == 0
    gates["DIFF_SCOPE_PASS"] = bool(run_facts.get("diff_scope_pass"))
    counters_pass = bool(
        value["enabled"]
        and value["mutation_detected_count"] == 0
        and value["internal_audit_error_count"] == 0
        and value["all_unchanged_count"] == value["audited_call_count"]
        and all(value[field] == 0 for field in MISMATCH_FIELDS)
    )
    gates["DAY5_FALLBACK_IN_CALL_IMMUTABILITY_PASS"] = bool(
        counters_pass and all(gates.values())
    )
    gates["FROZEN_REAL_OBSERVATION_RECORD_AUTHORIZED"] = gates[
        "DAY5_FALLBACK_IN_CALL_IMMUTABILITY_PASS"
    ]
    gates["DAY6_QUICK_DIAGNOSTICS_AUTHORIZED"] = False
    gates["OFFLINE_PRODUCTION_DETECTOR_DETERMINISM_AUTHORIZED"] = False
    gates["REAL_REPLAY_FUNCTIONAL_STATISTICAL_TOLERANCE_AUTHORIZED"] = False
    gates["STRICT_REPLAY_FURTHER_REMEDIATION_AUTHORIZED"] = False
    return dict(gates)


def canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"
