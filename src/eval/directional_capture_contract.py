"""Frozen configuration contract for Directional Capture Range MVP Day 1.

The lock is semantic: comments and harmless YAML formatting may change, but the
parsed values, their scalar types, list order, and mapping keys may not.  The
loader additionally rejects duplicate YAML keys so that a visually stale value
cannot be silently shadowed by a later one.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode


SCHEMA_VERSION = "directional_capture_range_day1_protocol_v1"
DAY1_PROTOCOL_RELATIVE = Path("configs/capture_range/day1_protocol.yaml")

# SHA-256 of compact, key-sorted JSON produced from the frozen YAML values.
# This deliberately ignores YAML comments and formatting while locking values,
# scalar types, list order, and the complete key set.
FROZEN_PROTOCOL_SEMANTIC_SHA256 = (
    "2e5ca9d314b4305baba6ce4e9e6e42a758f073d2f131ffb31efecbb427cef7b0"
)

FROZEN_AUDIT_STATUSES = {
    "STAGE2_GATE": "FAIL",
    "TRANSITION": "PIVOT",
    "EVALUATION_BUG_CONFIRMED": False,
    "PILOT_LABEL_INVALIDATED": True,
    "REFERENCE_INSUFFICIENT": True,
    "METHOD_NEGATIVE_CONFIRMED": False,
    "MEASUREMENT_PLAN_STATUS": "NEW_PREREGISTERED_REPLACEMENT_PILOT_REQUIRED",
}

PROTECTED_ARTIFACT_PATHS = (
    "artifacts/current/measurement_real_validation_pilot/",
    "artifacts/current/measurement_pilot_scientific_audit/",
    "artifacts/history/",
)

FROZEN_REGISTRATION_SETTINGS = {
    "max_iterations": 20,
    "k_neighbors": 5,
    "max_neighbor_distance_m": 0.75,
    "plane_fit_tolerance_m": 0.05,
    "huber_delta_m": 0.05,
    "damping": 0.000001,
    "rotation_step_tolerance_rad": 0.00001,
    "translation_step_tolerance_m": 0.00001,
    "min_correspondences": 30,
}


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """SafeLoader variant that refuses duplicate mapping keys."""


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader,
    node: MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable mapping key",
                key_node.start_mark,
            ) from exc
        if duplicate:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def load_capture_range_protocol(path: str | Path) -> Mapping[str, Any]:
    """Load and strictly validate the frozen Day 1 YAML protocol.

    ``FileNotFoundError`` and other path errors are left intact.  Invalid YAML,
    duplicate keys, non-mapping roots, unsupported YAML-native objects, and any
    semantic drift from the frozen protocol are reported as ``ValueError``.
    """

    protocol_path = Path(path)
    text = protocol_path.read_text(encoding="utf-8")
    try:
        value = yaml.load(text, Loader=_UniqueKeySafeLoader)
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid capture-range protocol YAML: {protocol_path}") from exc
    if not isinstance(value, dict):
        raise ValueError("capture-range protocol root must be a mapping")
    validate_capture_range_protocol(value)
    return value


def validate_capture_range_protocol(config: Mapping[str, Any]) -> None:
    """Reject any semantic change to the preregistered Day 1 protocol."""

    if not isinstance(config, dict):
        raise ValueError("capture-range protocol root must be a plain mapping")
    _validate_yaml_value(config, path="$", is_mapping_key=False)

    if config.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("capture-range protocol schema_version changed")

    state = config.get("frozen_scientific_state")
    if not isinstance(state, dict):
        raise ValueError("capture-range protocol frozen_scientific_state is missing")
    for field, expected in FROZEN_AUDIT_STATUSES.items():
        actual = state.get(field)
        if type(actual) is not type(expected) or actual != expected:
            raise ValueError(f"frozen scientific status changed: {field}")

    protected = config.get("protected_artifact_paths")
    if type(protected) is not list or tuple(protected) != PROTECTED_ARTIFACT_PATHS:
        raise ValueError("protected artifact paths changed")

    registration = config.get("registration")
    if not _exact_value(registration, FROZEN_REGISTRATION_SETTINGS):
        raise ValueError("Day 1 executable registration settings changed")

    semantic_hash = protocol_semantic_sha256(config)
    if semantic_hash != FROZEN_PROTOCOL_SEMANTIC_SHA256:
        raise ValueError(
            "capture-range protocol changed from the frozen Day 1 contract "
            f"(semantic sha256 {semantic_hash})"
        )


def protocol_semantic_sha256(config: Mapping[str, Any]) -> str:
    """Return the deterministic semantic digest used by the protocol lock."""

    _validate_yaml_value(config, path="$", is_mapping_key=False)
    try:
        payload = json.dumps(
            config,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("capture-range protocol is not canonical JSON data") from exc
    return hashlib.sha256(payload).hexdigest()


def _validate_yaml_value(value: Any, *, path: str, is_mapping_key: bool) -> None:
    """Allow only deterministic JSON-compatible values with strict types."""

    if is_mapping_key:
        if type(value) is not str:
            raise ValueError(f"capture-range protocol mapping key is not text at {path}")
        return
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(f"capture-range protocol contains a non-finite value at {path}")
        return
    if type(value) is list:
        for index, child in enumerate(value):
            _validate_yaml_value(child, path=f"{path}[{index}]", is_mapping_key=False)
        return
    if type(value) is dict:
        for key, child in value.items():
            _validate_yaml_value(key, path=f"{path}.<key>", is_mapping_key=True)
            _validate_yaml_value(child, path=f"{path}.{key}", is_mapping_key=False)
        return
    raise ValueError(
        f"capture-range protocol contains unsupported type {type(value).__name__} at {path}"
    )


def _exact_value(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(
            _exact_value(actual[key], child) for key, child in expected.items()
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _exact_value(left, right) for left, right in zip(actual, expected)
        )
    return actual == expected


# Concise aliases for callers that already carry the Day 1 context.
load_day1_protocol = load_capture_range_protocol
validate_day1_protocol = validate_capture_range_protocol


__all__ = [
    "DAY1_PROTOCOL_RELATIVE",
    "FROZEN_AUDIT_STATUSES",
    "FROZEN_PROTOCOL_SEMANTIC_SHA256",
    "FROZEN_REGISTRATION_SETTINGS",
    "PROTECTED_ARTIFACT_PATHS",
    "SCHEMA_VERSION",
    "load_capture_range_protocol",
    "load_day1_protocol",
    "protocol_semantic_sha256",
    "validate_capture_range_protocol",
    "validate_day1_protocol",
]
