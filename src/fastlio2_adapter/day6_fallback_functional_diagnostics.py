"""Shared contracts for Day 6 Fallback functional diagnostics.

This module is deliberately offline with respect to ROS and FAST-LIO2.  It
validates the fixed authorization and runtime identities, reads compact
observation binaries, and evaluates the bounded engineering gate.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import tarfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import scipy

from .frozen_observation import load_existing_converter
from .offline_detector_determinism import (
    EXPECTED_CONFIG_SHA256,
    EXPECTED_LOCK_SHA256,
    EXPECTED_SOURCE_SHA256,
    file_sha256,
    tree_sha256,
)
from .runtime_observation_v3 import validate_runtime_observation_v3


MAIN_RUN_ID = "multihyp_day6_fallback_functional_diagnostics_v1"
SUB_RUN_IDS = (
    "multihyp_day6_fallback_quick_r1",
    "multihyp_day6_fallback_quick_r2",
    "multihyp_day6_fallback_quick_r3",
)
SEQUENCE_ID = "avia_quick_shack"
EXPECTED_CLIP_SHA256 = (
    "272325265978787c838e010b1f0da963a15fb4b08ff8730fc3dd9901e32a0e20"
)
EXPECTED_AUTHORIZATION_SHA256 = (
    "09ce9348386640fdc36459340ace621d99c38df726a5424403c617087f31d920"
)
EXPECTED_FROZEN_REFERENCE_SHA256 = (
    "f68c9671e0058644b86fd1602b44b4a19ee35714e523cc10e1261650d538aca8"
)
EXPECTED_FROZEN_BINARY_SHA256 = (
    "d7f218068868985eee7ff01a8b7d1ce3467711d088e8c00b6c5de04ff0c120f3"
)
EXPECTED_FROZEN_ADAPTER_SHA256 = (
    "182b989aee619d83862cb45e9aef6fb0a50dd5b91d407e8d5ef13d694fd65232"
)
EXPECTED_RECORD_COUNT = 487
EXPECTED_RUNTIME_SCAN_COUNT = 490
EXPECTED_LIDAR_CALLBACK_COUNT = 491
EXPECTED_IMU_CALLBACK_COUNT = 9953
EXPECTED_FIRST_SCAN_INDEX = 3
EXPECTED_LAST_SCAN_INDEX = 489
EXPECTED_DEGEN_BRANCH = "spike/harmful-bias-multihyp-dev"
EXPECTED_DEGEN_HEAD = "711ac05ccc683263446fb8656c0054048832f54c"
EXPECTED_FAST_BRANCH = "spike/readonly-observation-tap-v1"
EXPECTED_FAST_HEAD = "f19b4c42a77dc11793c912d67b9e56dcafa279dc"
EXPECTED_FAST_BINARY_SHA256 = (
    "5af22373f923eea39d63c055fc0b2dd6353926fbe5a29535a1a35c7d453c1cc3"
)
EXPECTED_TAIL_ADJUDICATION_RULE_SHA256 = (
    "19794a877253615211d1b4bc5ffc1bcd0864b97b539f58ad0c9c320ed6952dd0"
)
EXPECTED_DETECTOR_ARTIFACT_TREE_SHA256 = (
    "6dcccf2de670f78080ae0097d357d1cfd7b87949caf48c31dd247ae81bb5c95e"
)
EXPECTED_ENVIRONMENT = {
    "PYTHONHASHSEED": "0",
    "OMP_NUM_THREADS": "1",
    "OMP_DYNAMIC": "FALSE",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
    "LC_ALL": "C",
    "LANG": "C",
    "TZ": "UTC",
}

METRIC_FIELDS = (
    "odi_trans",
    "ais_trans",
    "lambda_min_trans",
    "condition_number_trans",
    "primary_eigengap_ratio",
)
FLAG_FIELDS = (
    "valid",
    "primary_direction_stable",
    "degeneracy_triggered",
    "actionable_direction",
)
FORBIDDEN_RESULT_TOKENS = (
    "auroc",
    "auprc",
    "false_positive",
    "true_positive",
    "ground_truth_label",
    "detector_feedback_to_fastlio2",
)


class Day6FallbackError(ValueError):
    """Raised when a fixed Day 6 Fallback contract is violated."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_rows(rows: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(row.encode("utf-8"))
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))


def _json_member_by_suffix(
    handle: tarfile.TarFile, suffix: str
) -> dict[str, Any]:
    matches = [
        member
        for member in handle.getmembers()
        if member.isfile() and member.name.endswith(suffix)
    ]
    if len(matches) != 1:
        raise Day6FallbackError(
            f"authorization member resolution failed for {suffix}: {len(matches)}"
        )
    extracted = handle.extractfile(matches[0])
    if extracted is None:
        raise Day6FallbackError(f"cannot read authorization member: {suffix}")
    value = json.loads(extracted.read())
    if not isinstance(value, dict):
        raise Day6FallbackError(f"authorization JSON object required: {suffix}")
    return value


def validate_authorization_archive(path: Path) -> dict[str, Any]:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise Day6FallbackError("Day 6 authorization audit is missing")
    if path.suffix == ".json":
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise Day6FallbackError("authorization identity must be an object")
        required = {
            "authorization_audit_sha256": EXPECTED_AUTHORIZATION_SHA256,
            "FALLBACK_C_PASS": True,
            "OFFLINE_PRODUCTION_DETECTOR_DETERMINISM_PASS": True,
            "PRODUCTION_DETECTOR_DETERMINISM_ON_DIRECT_STREAM_PASS": True,
            "ADAPTER_PIPELINE_DETERMINISM_PASS": True,
            "DAY6_FALLBACK_FUNCTIONAL_DIAGNOSTICS_RECOMMENDED": True,
            "DAY6_QUICK_DIAGNOSTICS_AUTHORIZED": False,
            "DAY6_FALLBACK_FUNCTIONAL_DIAGNOSTICS_AUTHORIZED": True,
            "REAL_REPLAY_FUNCTIONAL_STATISTICAL_TOLERANCE_AUTHORIZED": True,
            "STRICT_CROSS_PROCESS_REPLAY_ROUTE_STATUS": "ABANDONED_AFTER_V5",
            "CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE": "NOT_PROVEN",
        }
        mismatches = {
            name: {"expected": expected, "actual": value.get(name)}
            for name, expected in required.items()
            if value.get(name) != expected
        }
        if mismatches:
            raise Day6FallbackError(
                f"authorization identity mismatch: {mismatches}"
            )
        return dict(value)
    actual_sha = sha256_file(path)
    if actual_sha != EXPECTED_AUTHORIZATION_SHA256:
        raise Day6FallbackError("Day 6 authorization audit SHA mismatch")
    with tarfile.open(path, "r:gz") as handle:
        gate = _json_member_by_suffix(
            handle,
            "/evidence/small_results/fallback_c_remediation_gate_summary.json",
        )
        manifest = _json_member_by_suffix(
            handle,
            "/evidence/small_results/"
            "fallback_offline_detector_determinism_remediation_manifest.json",
        )
    required_true = (
        "FALLBACK_C_PASS",
        "OFFLINE_PRODUCTION_DETECTOR_DETERMINISM_PASS",
        "PRODUCTION_DETECTOR_DETERMINISM_ON_DIRECT_STREAM_PASS",
        "ADAPTER_PIPELINE_DETERMINISM_PASS",
        "DAY6_FALLBACK_FUNCTIONAL_DIAGNOSTICS_RECOMMENDED",
    )
    failed = [name for name in required_true if gate.get(name) is not True]
    if failed:
        raise Day6FallbackError(
            f"authorization audit required gates are false: {failed}"
        )
    if gate.get("DAY6_QUICK_DIAGNOSTICS_AUTHORIZED") is not False:
        raise Day6FallbackError("old Day 6 authorization must remain false")
    if manifest.get("STRICT_CROSS_PROCESS_REPLAY_ROUTE_STATUS") != (
        "ABANDONED_AFTER_V5"
    ):
        raise Day6FallbackError("strict replay route is not frozen abandoned")
    if manifest.get("CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE") != "NOT_PROVEN":
        raise Day6FallbackError("bitwise replay status changed")
    return {
        "authorization_audit_sha256": actual_sha,
        "FALLBACK_C_PASS": True,
        "OFFLINE_PRODUCTION_DETECTOR_DETERMINISM_PASS": True,
        "PRODUCTION_DETECTOR_DETERMINISM_ON_DIRECT_STREAM_PASS": True,
        "ADAPTER_PIPELINE_DETERMINISM_PASS": True,
        "DAY6_FALLBACK_FUNCTIONAL_DIAGNOSTICS_RECOMMENDED": True,
        "DAY6_QUICK_DIAGNOSTICS_AUTHORIZED": False,
        "DAY6_FALLBACK_FUNCTIONAL_DIAGNOSTICS_AUTHORIZED": True,
        "REAL_REPLAY_FUNCTIONAL_STATISTICAL_TOLERANCE_AUTHORIZED": True,
        "STRICT_CROSS_PROCESS_REPLAY_ROUTE_STATUS": "ABANDONED_AFTER_V5",
        "CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE": "NOT_PROVEN",
    }


def validate_environment_lock() -> dict[str, Any]:
    actual = {name: os.environ.get(name) for name in EXPECTED_ENVIRONMENT}
    if actual != EXPECTED_ENVIRONMENT:
        raise Day6FallbackError(
            f"detector environment variable lock mismatch: {actual}"
        )
    python_version = platform.python_version()
    numpy_version = np.__version__
    scipy_version = scipy.__version__
    # Validate the frozen interpreter/library identity before calling the
    # NumPy 1.24 configuration API.  NumPy 1.26 removed ``get_info``; a
    # non-frozen environment must be reported as a version mismatch instead
    # of failing with an unrelated AttributeError during repository tests.
    if python_version != "3.8.10":
        raise Day6FallbackError("locked Python version mismatch")
    if numpy_version != "1.24.4":
        raise Day6FallbackError("locked NumPy version mismatch")
    if scipy_version != "1.10.1":
        raise Day6FallbackError("locked SciPy version mismatch")
    get_info = getattr(np.__config__, "get_info", None)
    if not callable(get_info):
        raise Day6FallbackError("locked NumPy BLAS inspection API is missing")
    blas = {
        name: np.__config__.get_info(name)
        for name in (
            "openblas64__info",
            "blas_ilp64_opt_info",
            "openblas64__lapack_info",
            "lapack_ilp64_opt_info",
        )
        if np.__config__.get_info(name)
    }
    identity = {
        "python_version": python_version,
        "python_implementation": platform.python_implementation(),
        "numpy_version": numpy_version,
        "scipy_version": scipy_version,
        "blas_identity": blas,
        "platform": platform.platform(),
        "environment_variables": actual,
    }
    if "blas_ilp64_opt_info" not in blas:
        raise Day6FallbackError("OpenBLAS ILP64 identity is missing")
    return identity


def detector_identity(root: Path) -> dict[str, Any]:
    source = root / "src/degen_detector/odi_tracker.py"
    config = root / "configs/detector/odi_stage2a.yaml"
    lock = (
        root
        / "artifacts/current/detector_stage2a/locked/detector_lock.json"
    )
    identity = {
        "production_detector_sha256": sha256_file(source),
        "detector_config_sha256": sha256_file(config),
        "detector_lock_sha256": sha256_file(lock),
        "detector_artifact_tree_sha256": tree_sha256(
            root / "artifacts/current/detector_stage2a"
        ),
        "detector_metric_version": "detector_stage2a_v1",
    }
    expected = {
        "production_detector_sha256": EXPECTED_SOURCE_SHA256,
        "detector_config_sha256": EXPECTED_CONFIG_SHA256,
        "detector_lock_sha256": EXPECTED_LOCK_SHA256,
        "detector_artifact_tree_sha256": (
            EXPECTED_DETECTOR_ARTIFACT_TREE_SHA256
        ),
    }
    mismatches = {
        name: {"expected": value, "actual": identity[name]}
        for name, value in expected.items()
        if identity[name] != value
    }
    if mismatches:
        raise Day6FallbackError(f"production detector identity mismatch: {mismatches}")
    return identity


def load_observation_binary(
    path: Path, *, expected_count: int = EXPECTED_RECORD_COUNT
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    converter = load_existing_converter()
    try:
        framed, integrity = converter.read_framed_binary(
            path,
            magic=converter.OBSERVATION_MAGIC,
            version=converter.OBSERVATION_VERSION,
        )
    except converter.BinaryFormatError as error:
        raise Day6FallbackError(str(error)) from error
    if len(framed) != expected_count:
        raise Day6FallbackError(
            f"observation count is {len(framed)}, expected {expected_count}"
        )
    records = [converter.decode_observation_record(item) for item in framed]
    for expected_index, record in enumerate(records):
        validate_runtime_observation_v3(record)
        if record["sequence_id"] != SEQUENCE_ID:
            raise Day6FallbackError("observation sequence changed")
        if int(record["scan_index"]) != EXPECTED_FIRST_SCAN_INDEX + expected_index:
            raise Day6FallbackError("observation scan index is not contiguous 3..489")
    if not integrity["file_checksum_valid"] or not integrity["trailer_valid"]:
        raise Day6FallbackError("observation binary integrity failed")
    integrity = dict(integrity)
    integrity.setdefault("extra_trailing_bytes", 0)
    integrity.setdefault("record_checksum_failure_count", 0)
    return records, integrity


def validate_record_index(
    rows: Sequence[Mapping[str, Any]],
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if len(rows) != len(records) or len(rows) != EXPECTED_RECORD_COUNT:
        raise Day6FallbackError("record index count mismatch")
    identities: set[tuple[int, str, str]] = set()
    for expected, (row, record) in enumerate(zip(rows, records)):
        if int(row["record_index"]) != expected:
            raise Day6FallbackError("record index is not contiguous")
        key = (
            int(row["scan_index"]),
            str(row["timestamp_begin"]),
            str(row["timestamp_end"]),
        )
        record_key = (
            int(record["scan_index"]),
            repr(float(record["timestamp_begin"])),
            repr(float(record["timestamp_end"])),
        )
        if key != record_key:
            raise Day6FallbackError("record index identity mismatch")
        if key in identities:
            raise Day6FallbackError("duplicate record index identity")
        identities.add(key)
    return {
        "record_index_row_count": len(rows),
        "record_index_contiguous": True,
        "duplicate_record_identity_count": 0,
        "record_index_pass": True,
    }


def forbidden_result_paths(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for raw_name, child in value.items():
            name = str(raw_name)
            if any(token in name.lower() for token in FORBIDDEN_RESULT_TOKENS):
                found.append(f"{path}.{name}")
            found.extend(forbidden_result_paths(child, f"{path}.{name}"))
    elif isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        for index, child in enumerate(value):
            found.extend(forbidden_result_paths(child, f"{path}[{index}]"))
    return found


REQUIRED_GATE_NAMES = (
    "DAY6_AUTHORIZATION_IDENTITY_PASS",
    "DEGEN_SOURCE_LOCK_PASS",
    "FAST_SOURCE_LOCK_PASS",
    "FAST_BINARY_LOCK_PASS",
    "CLIP_IDENTITY_PASS",
    "ENDPOINT_CONTRACT_PASS",
    "THREE_REAL_REPLAY_RUNS_COMPLETE_PASS",
    "RUN_1_COMPLETENESS_PASS",
    "RUN_2_COMPLETENESS_PASS",
    "RUN_3_COMPLETENESS_PASS",
    "TAIL_ADJUDICATION_RULE_REUSE_PASS",
    "END_OF_STREAM_DRAIN_PASS",
    "NORMAL_SHUTDOWN_PASS",
    "OBSERVATION_BINARY_INTEGRITY_PASS",
    "OBSERVATION_COUNT_COMPLETENESS_PASS",
    "REFERENCE_SCAN_ALIGNMENT_PASS",
    "IN_CALL_IMMUTABILITY_RECONFIRMED",
    "NO_TAP_DROP_PASS",
    "NO_WRITER_ERROR_PASS",
    "DETECTOR_ENVIRONMENT_LOCK_PASS",
    "PRODUCTION_DETECTOR_IDENTITY_PASS",
    "DETECTOR_ARTIFACT_IMMUTABILITY_PASS",
    "POST_REPLAY_DETECTOR_PROCESSING_PASS",
    "ADAPTER_DIRECT_CONTRACT_PASS",
    "INPUT_IMMUTABILITY_PASS",
    "DETECTOR_OUTPUT_COUNT_PASS",
    "DETECTOR_OUTPUT_SCHEMA_PASS",
    "NO_GT_PASS",
    "OUTPUT_TIMESTAMP_MONOTONICITY_PASS",
    "OUTPUT_CONTINUITY_DIAGNOSTICS_PASS",
    "DIRECTION_CONTINUITY_DIAGNOSTICS_PASS",
    "FLAG_CONTINUITY_DIAGNOSTICS_PASS",
    "METRIC_DESCRIPTIVE_STATISTICS_PASS",
    "LATENCY_CHARACTERIZATION_PASS",
    "REFERENCE_COMPARISON_COMPLETE",
    "CROSS_RUN_STATISTICAL_COMPARISON_COMPLETE",
    "PLOTS_COMPLETE",
    "DEGEN_TARGETED_TEST_PASS",
    "DEGEN_FULL_TEST_PASS",
    "DIFF_SCOPE_PASS",
    "AUDIT_PACKAGE_SCOPE_PASS",
)


def evaluate_day6_gate(facts: Mapping[str, Any]) -> dict[str, Any]:
    gates = {name: bool(facts.get(name, False)) for name in REQUIRED_GATE_NAMES}
    final = all(gates.values())
    gates.update(
        {
            "DAY6_FALLBACK_REAL_REPLAY_CAPTURE_PASS": final,
            "DAY6_FALLBACK_OBSERVATION_COMPLETENESS_PASS": final,
            "DAY6_FALLBACK_DETECTOR_EXECUTION_PASS": final,
            "DAY6_FALLBACK_CONTINUITY_DIAGNOSTICS_PASS": final,
            "DAY6_FALLBACK_STATISTICAL_CHARACTERIZATION_PASS": final,
            "REAL_REPLAY_FUNCTIONAL_STATISTICAL_TOLERANCE_PASS": final,
            "DAY6_FALLBACK_FUNCTIONAL_DIAGNOSTICS_PASS": final,
            "NEXT_PHASE_RECOMMENDED": final,
            "NEXT_PHASE_AUTHORIZED": False,
            "DAY6_QUICK_DIAGNOSTICS_AUTHORIZED": False,
            "CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE": "NOT_PROVEN",
            "CROSS_RUN_EXACT_OUTPUT_EQUALITY_REQUIRED": False,
            "CROSS_RUN_BITWISE_EQUIVALENCE_CLAIMED": False,
            "STAGE2_GATE": "FAIL",
            "TRANSITION": "PIVOT",
            "STAGE3_START_AUTHORIZED": False,
            "STAGE4_START_AUTHORIZED": False,
            "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
            "PATENT2_AUTHORIZED": False,
            "RISK_WARNING_AUTHORIZED": False,
            "PUBLIC_DISCLOSURE_AUTHORIZED": False,
            "HARMFUL_BIAS_DETECTABILITY_STATUS": (
                "NOT_EVALUATED_DAY6_FALLBACK_FUNCTIONAL_DIAGNOSTICS"
            ),
            "SCIENTIFIC_EFFECTIVENESS_EVALUATED": False,
            "HARMFUL_BIAS_DETECTABILITY_EVALUATED": False,
            "AUROC_COMPUTED": False,
            "AUPRC_COMPUTED": False,
            "FPR_COMPUTED": False,
            "RECALL_COMPUTED": False,
            "DETECTOR_FEEDBACK_TO_ESTIMATOR": False,
            "DETECTOR_FEEDBACK_TO_MAP": False,
            "ONLINE_DETECTOR_LATENCY_EVALUATED": False,
            "FAST_LIO2_ROBUST_UPDATE_INTEGRATED": False,
        }
    )
    return gates
