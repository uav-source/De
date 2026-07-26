"""Runtime v2 entrypoint sharing the frozen production detector thin core."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .detector_adapter import (
    DETECTOR_RESIDUAL_INPUT_FIELD,
    DETECTOR_TRANSLATION_FRAME,
    MEASUREMENT_WEIGHT_REPRESENTATION,
    PRODUCTION_ENTRYPOINT,
    _evaluate_production_detector_core,
)
from .detector_output_schema import canonical_sha256
from .readonly_runtime_observation_schema import validate_runtime_observation


SCHEMA_VERSION = "readonly_detector_output_v2"
RECORD_VERSION = "readonly_detector_output_v2"
RECORD_SOURCE = "FASTLIO2_RUNTIME"
DETECTOR_EXECUTION_MODE = "POST_REPLAY_READONLY_PRODUCTION_DETECTOR"

_RUNTIME_OUTPUT_FIELDS = frozenset(
    {
        "record_source",
        "run_id",
        "sequence_id",
        "detector_execution_mode",
    }
)


def evaluate_runtime_observation(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate one real record and evaluate it outside the filter thread."""

    validate_runtime_observation(record)
    return _evaluate_production_detector_core(
        record,
        base_output_factory=_runtime_base_output,
        seal_output=_seal_runtime_output,
    )


def validate_runtime_detector_output(record: Mapping[str, Any]) -> None:
    """Validate v2 provenance and the frozen numerical output contract."""

    from .detector_output_schema import validate_readonly_detector_output

    if not isinstance(record, Mapping):
        raise ValueError("runtime detector output must be a mapping")
    if record.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected runtime detector output schema")
    if record.get("record_version") != RECORD_VERSION:
        raise ValueError("unexpected runtime detector output record version")
    if record.get("record_source") != RECORD_SOURCE:
        raise ValueError("runtime detector output source mismatch")
    if record.get("synthetic_only") is not False:
        raise ValueError("runtime detector output synthetic_only must be false")
    if record.get("detector_execution_mode") != DETECTOR_EXECUTION_MODE:
        raise ValueError("runtime detector execution mode mismatch")
    for name in ("run_id", "sequence_id"):
        if not isinstance(record.get(name), str) or not record[name]:
            raise ValueError(f"{name} must be nonempty")

    frozen = {
        key: value for key, value in record.items() if key not in _RUNTIME_OUTPUT_FIELDS
    }
    frozen["schema_version"] = "fastlio2-readonly-detector-output-v1"
    frozen["record_version"] = "readonly_detector_output_v1"
    frozen["synthetic_only"] = True
    frozen["detector_output_checksum"] = _v1_compatible_checksum(frozen)
    validate_readonly_detector_output(frozen)

    expected = runtime_detector_output_payload_checksum(record)
    if record["detector_output_checksum"] != expected:
        raise ValueError("runtime detector output checksum mismatch")


def runtime_detector_output_payload_checksum(record: Mapping[str, Any]) -> str:
    payload = dict(record)
    payload["detector_output_checksum"] = "0" * 64
    return canonical_sha256(payload)


def _v1_compatible_checksum(record: Mapping[str, Any]) -> str:
    payload = dict(record)
    payload.pop("detector_output_checksum", None)
    return canonical_sha256(payload)


def _runtime_base_output(
    record: Mapping[str, Any],
    detector_input: Mapping[str, Any],
    provenance: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "record_version": RECORD_VERSION,
        "record_source": RECORD_SOURCE,
        "run_id": str(record["run_id"]),
        "sequence_id": str(record["sequence_id"]),
        "detector_execution_mode": DETECTOR_EXECUTION_MODE,
        "scan_index": int(record["scan_index"]),
        "timestamp_begin": float(record["timestamp_begin"]),
        "timestamp_end": float(record["timestamp_end"]),
        "measurement_call_index": int(record["measurement_call_index"]),
        "input_observation_checksum": canonical_sha256(record),
        "detector_input_checksum": str(detector_input["checksum"]),
        "detector_output_checksum": "0" * 64,
        "detector_metric_version": provenance["detector_metric_version"],
        "detector_entrypoint": PRODUCTION_ENTRYPOINT,
        "detector_source_sha256": provenance["detector_source_sha256"],
        "detector_config_sha256": provenance["detector_config_sha256"],
        "detector_lock_sha256": provenance["detector_lock_sha256"],
        "detector_residual_input_field": DETECTOR_RESIDUAL_INPUT_FIELD,
        "measurement_weight_representation": MEASUREMENT_WEIGHT_REPRESENTATION,
        "valid_correspondence_count": int(record["valid_correspondence_count"]),
        "primary_weak_direction_frame": DETECTOR_TRANSLATION_FRAME,
        "synthetic_only": False,
    }


def _seal_runtime_output(output: dict[str, Any]) -> dict[str, Any]:
    output["detector_output_checksum"] = runtime_detector_output_payload_checksum(
        output
    )
    validate_runtime_detector_output(output)
    return output
