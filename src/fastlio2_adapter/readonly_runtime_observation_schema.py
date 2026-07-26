"""Strict validation for real FAST-LIO2 runtime observation v2 records."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from .readonly_observation_schema import (
    validate_first_valid_observation_record,
)


SCHEMA_VERSION = "readonly_observation_v2"
RECORD_VERSION = "readonly_observation_v2"
RECORD_SOURCE = "FASTLIO2_RUNTIME"
ADAPTER_CONTRACT_VERSION = "fastlio2-readonly-observation-v2"

_RUNTIME_FIELDS = frozenset(
    {
        "record_source",
        "run_id",
        "sequence_id",
        "fastlio2_commit",
        "fastlio2_binary_sha256",
        "bag_sha256",
        "config_bundle_sha256",
        "adapter_contract_version",
    }
)
_FORBIDDEN_TOKENS = (
    "pose_gt",
    "axis_gt",
    "oracle_axis",
    "scene_label",
    "harmful_label",
    "ground_truth",
    "future_frame",
    "holdout_label",
    "candidate_offsets",
    "candidate_costs",
    "imu_conflict",
    "final_harmful_score",
    "harmful_trigger",
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def validate_runtime_observation(record: Mapping[str, Any]) -> None:
    """Validate provenance plus every frozen Day 3 observation field."""

    if not isinstance(record, Mapping):
        raise ValueError("runtime observation must be a mapping")
    _reject_forbidden_fields(record)
    missing = sorted(_RUNTIME_FIELDS - set(record))
    if missing:
        raise ValueError(f"runtime observation missing fields: {missing}")

    if record.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"schema_version must equal {SCHEMA_VERSION!r}")
    if record.get("record_version") != RECORD_VERSION:
        raise ValueError(f"record_version must equal {RECORD_VERSION!r}")
    if record.get("record_source") != RECORD_SOURCE:
        raise ValueError(f"record_source must equal {RECORD_SOURCE!r}")
    if record.get("synthetic_only") is not False:
        raise ValueError("runtime observation synthetic_only must be false")
    if record.get("adapter_contract_version") != ADAPTER_CONTRACT_VERSION:
        raise ValueError("unexpected runtime adapter contract version")

    for name in ("run_id", "sequence_id"):
        value = record[name]
        if not isinstance(value, str) or _IDENTIFIER_RE.fullmatch(value) is None:
            raise ValueError(f"{name} must be a nonempty safe identifier")
    commit = record["fastlio2_commit"]
    if not isinstance(commit, str) or _COMMIT_RE.fullmatch(commit) is None:
        raise ValueError("fastlio2_commit must be lowercase 40-hex")
    for name in (
        "fastlio2_binary_sha256",
        "bag_sha256",
        "config_bundle_sha256",
    ):
        value = record[name]
        if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
            raise ValueError(f"{name} must be lowercase SHA-256")

    frozen = {key: value for key, value in record.items() if key not in _RUNTIME_FIELDS}
    frozen["schema_version"] = "fastlio2-readonly-observation-v1"
    frozen["record_version"] = "readonly_observation_v1"
    frozen["synthetic_only"] = True
    validate_first_valid_observation_record(frozen)


def _reject_forbidden_fields(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for raw_name, child in value.items():
            if not isinstance(raw_name, str):
                raise ValueError(f"{path} contains a non-string field name")
            lowered = raw_name.lower()
            if any(token in lowered for token in _FORBIDDEN_TOKENS):
                raise ValueError(f"record contains forbidden field: {raw_name}")
            _reject_forbidden_fields(child, f"{path}.{raw_name}")
    elif isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        for index, child in enumerate(value):
            _reject_forbidden_fields(child, f"{path}[{index}]")
