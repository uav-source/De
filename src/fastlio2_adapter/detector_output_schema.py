"""Structural validation and canonical checksums for Day 4 detector outputs."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from typing import Any


SCHEMA_VERSION = "fastlio2-readonly-detector-output-v1"
RECORD_VERSION = "readonly_detector_output_v1"
PRIMARY_WEAK_DIRECTION_FRAME = "WORLD"

INVALID_REASONS = (
    "NONE",
    "OBSERVATION_SCHEMA_INVALID",
    "UNSUPPORTED_WEIGHT_REPRESENTATION",
    "TOO_FEW_CORRESPONDENCES",
    "NONFINITE_DETECTOR_INPUT",
    "DETECTOR_CONTRACT_MISMATCH",
    "DETECTOR_REJECTED",
    "DETECTOR_OUTPUT_NONFINITE",
)

_FIELDS = frozenset(
    {
        "schema_version",
        "record_version",
        "scan_index",
        "timestamp_begin",
        "timestamp_end",
        "measurement_call_index",
        "input_observation_checksum",
        "detector_input_checksum",
        "detector_output_checksum",
        "detector_metric_version",
        "detector_entrypoint",
        "detector_source_sha256",
        "detector_config_sha256",
        "detector_lock_sha256",
        "detector_residual_input_field",
        "measurement_weight_representation",
        "valid_correspondence_count",
        "valid",
        "invalid_reason",
        "odi_trans",
        "ais_trans",
        "lambda_min_trans",
        "condition_number_trans",
        "translation_eigenvalues_ascending",
        "primary_weak_direction",
        "primary_weak_direction_frame",
        "primary_eigengap_ratio",
        "primary_direction_stable",
        "degeneracy_triggered",
        "actionable_direction",
        "synthetic_only",
    }
)

_OPTIONAL_NUMERIC_FIELDS = (
    "odi_trans",
    "ais_trans",
    "lambda_min_trans",
    "condition_number_trans",
    "primary_eigengap_ratio",
)

_BOOLEAN_FIELDS = (
    "valid",
    "primary_direction_stable",
    "degeneracy_triggered",
    "actionable_direction",
    "synthetic_only",
)

_FORBIDDEN_FIELD_TOKENS = (
    "pose_gt",
    "axis_gt",
    "oracle_axis",
    "scene_label",
    "harmful_label",
    "future_frame",
    "holdout_label",
    "ground_truth",
    "final_harmful_score",
    "harmful_trigger",
    "candidate_offsets",
    "candidate_costs",
    "imu_conflict",
    "future_gain",
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def canonical_json_bytes(value: Any) -> bytes:
    """Return the single canonical JSON encoding used by Day 4 checksums."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def detector_output_payload_checksum(record: Mapping[str, Any]) -> str:
    payload = dict(record)
    payload.pop("detector_output_checksum", None)
    return canonical_sha256(payload)


def validate_readonly_detector_output(record: Mapping[str, Any]) -> None:
    """Validate output shape and consistency without recomputing detector math."""

    if not isinstance(record, Mapping):
        raise ValueError("detector output must be a mapping")
    _reject_forbidden_fields(record)
    missing = sorted(_FIELDS - set(record))
    extra = sorted(set(record) - _FIELDS)
    if missing or extra:
        raise ValueError(
            f"detector output field mismatch: missing={missing}, extra={extra}"
        )

    _require_constant(record, "schema_version", SCHEMA_VERSION)
    _require_constant(record, "record_version", RECORD_VERSION)
    _require_uint(record, "scan_index")
    _require_finite(record, "timestamp_begin")
    _require_finite(record, "timestamp_end")
    if float(record["timestamp_end"]) < float(record["timestamp_begin"]):
        raise ValueError("timestamp_end must not precede timestamp_begin")
    _require_uint(record, "measurement_call_index", maximum=(1 << 32) - 1)

    for name in (
        "input_observation_checksum",
        "detector_input_checksum",
        "detector_output_checksum",
        "detector_source_sha256",
        "detector_config_sha256",
        "detector_lock_sha256",
    ):
        value = record[name]
        if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
            raise ValueError(f"{name} must be a lowercase SHA-256 digest")

    for name in (
        "detector_metric_version",
        "detector_entrypoint",
        "detector_residual_input_field",
        "measurement_weight_representation",
    ):
        if not isinstance(record[name], str) or not record[name]:
            raise ValueError(f"{name} must be a nonempty string")

    _require_constant(record, "primary_weak_direction_frame", "WORLD")
    _require_constant(
        record, "measurement_weight_representation", "CONSTANT_SCALAR_VARIANCE"
    )
    _require_constant(record, "detector_residual_input_field", "formal_filter_innovation_h")
    _require_uint(record, "valid_correspondence_count", minimum=1, maximum=(1 << 32) - 1)

    for name in _BOOLEAN_FIELDS:
        if not isinstance(record[name], bool):
            raise ValueError(f"{name} must be boolean")
    if record["synthetic_only"] is not True:
        raise ValueError("synthetic_only must be true for Day 4 output")

    reason = record["invalid_reason"]
    if reason not in INVALID_REASONS:
        raise ValueError(f"unsupported invalid_reason: {reason!r}")

    if record["valid"]:
        if reason != "NONE":
            raise ValueError("valid output requires invalid_reason=NONE")
        for name in _OPTIONAL_NUMERIC_FIELDS:
            _require_finite(record, name)
        eigenvalues = _require_vector(
            record, "translation_eigenvalues_ascending", length=3
        )
        if any(
            eigenvalues[index] > eigenvalues[index + 1]
            for index in range(len(eigenvalues) - 1)
        ):
            raise ValueError("translation eigenvalues must be nondecreasing")
        direction = _require_vector(record, "primary_weak_direction", length=3)
        norm = math.sqrt(sum(value * value for value in direction))
        if abs(norm - 1.0) > 1.0e-12:
            raise ValueError("primary weak direction must have unit norm")
    else:
        if reason == "NONE":
            raise ValueError("invalid output requires an explicit invalid_reason")
        for name in _OPTIONAL_NUMERIC_FIELDS:
            if record[name] is not None:
                raise ValueError(f"invalid output requires {name}=null")
        for name in (
            "translation_eigenvalues_ascending",
            "primary_weak_direction",
        ):
            if record[name] is not None:
                raise ValueError(f"invalid output requires {name}=null")
        for name in (
            "primary_direction_stable",
            "degeneracy_triggered",
            "actionable_direction",
        ):
            if record[name] is not False:
                raise ValueError(f"invalid output requires {name}=false")

    if record["actionable_direction"] and not record["primary_direction_stable"]:
        raise ValueError("actionable direction requires stable direction")
    if record["actionable_direction"] and not record["degeneracy_triggered"]:
        raise ValueError("actionable direction requires degeneracy trigger")

    expected_checksum = detector_output_payload_checksum(record)
    if record["detector_output_checksum"] != expected_checksum:
        raise ValueError("detector_output_checksum mismatch")


def _reject_forbidden_fields(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for raw_name, child in value.items():
            if not isinstance(raw_name, str):
                raise ValueError(f"{path} contains a non-string field name")
            lowered = raw_name.lower()
            if any(token in lowered for token in _FORBIDDEN_FIELD_TOKENS):
                raise ValueError(f"output contains forbidden field: {raw_name}")
            _reject_forbidden_fields(child, f"{path}.{raw_name}")
    elif _is_sequence(value):
        for index, child in enumerate(value):
            _reject_forbidden_fields(child, f"{path}[{index}]")


def _require_constant(record: Mapping[str, Any], name: str, expected: Any) -> None:
    if record[name] != expected:
        raise ValueError(f"{name} must equal {expected!r}")


def _require_uint(
    record: Mapping[str, Any],
    name: str,
    *,
    minimum: int = 0,
    maximum: int = (1 << 64) - 1,
) -> int:
    value = record[name]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} is outside the allowed unsigned range")
    return value


def _require_finite(record: Mapping[str, Any], name: str) -> float:
    value = record[name]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _require_vector(
    record: Mapping[str, Any], name: str, *, length: int
) -> list[float]:
    values = record[name]
    if not _is_sequence(values) or len(values) != length:
        raise ValueError(f"{name} must have length {length}")
    result: list[float] = []
    for index, value in enumerate(values):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name}[{index}] must be numeric")
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ValueError(f"{name}[{index}] must be finite")
        result.append(numeric)
    return result


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    )
