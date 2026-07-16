"""Typed Gate results and validation for the Stage 2 Day 14 decision."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Tuple

import yaml


DAY14_SCHEMA_VERSION = "stage2_day14_decision_v1"


class GateStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"
    EVIDENCE_INVALID = "EVIDENCE_INVALID"


@dataclass(frozen=True)
class GateResult:
    name: str
    status: GateStatus
    threshold: str
    observed: str
    reason: str
    evidence_paths: Tuple[str, ...]


@dataclass(frozen=True)
class Stage2Decision:
    separability: GateResult
    cross_geometry: GateResult
    causal_consistency: GateResult
    no_gt: GateResult
    overall_gate: GateStatus
    coherent_bias_harmful_mechanism_supported: Optional[bool]
    coherent_bias_stably_online_detectable: bool
    stage3_start_authorized: bool
    transition: str


METRIC_SUMMARY_FIELDS = (
    "metric", "sweep", "population", "observed", "ci95_lower",
    "ci95_upper", "threshold", "target_met", "source_path", "source_sha256",
)

EVIDENCE_INDEX_FIELDS = (
    "evidence_id", "stage_day", "description", "path", "sha256",
    "schema_version", "source_commit", "status", "used_by_gate",
)


def load_day14_config(path: Path) -> Mapping[str, Any]:
    value = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Day 14 config must be a mapping")
    validate_day14_config(value)
    return value


def validate_day14_config(config: Mapping[str, Any]) -> None:
    expected = {
        "schema_version": DAY14_SCHEMA_VERSION,
        "scientific_question": {
            "is_coherent_bias_stably_online_detectable": True,
        },
        "gates": {
            "separability": {"auroc_min": 0.80, "clean_fpr_max": 0.10},
            "cross_geometry": {"same_direction_geometry_ratio_min": 0.80},
            "causal_consistency": {
                "require_harmful_update_association": True,
                "require_gross_outlier_huber_handling": True,
            },
            "no_gt": {
                "require_online_only_statistics": True,
                "require_gt_removal_equivalence": True,
            },
        },
        "locked_primary_statistic": "huber_cusum_max",
        "locked_threshold": 13.745952939169019,
        "allow_trial_rerun": False,
        "allow_retuning": False,
        "allow_new_statistic": False,
        "allow_stage3_on_stage2_fail": False,
    }
    if value_not_exact(config, expected):
        raise ValueError("Day 14 decision config changed from the frozen contract")


def make_stage2_decision(
    separability: GateResult,
    cross_geometry: GateResult,
    causal_consistency: GateResult,
    no_gt: GateResult,
    harmful_mechanism_supported: Optional[bool],
) -> Stage2Decision:
    gates = (separability, cross_geometry, causal_consistency, no_gt)
    overall_pass = all(gate.status == GateStatus.PASS for gate in gates)
    overall = GateStatus.PASS if overall_pass else GateStatus.FAIL
    return Stage2Decision(
        separability=separability,
        cross_geometry=cross_geometry,
        causal_consistency=causal_consistency,
        no_gt=no_gt,
        overall_gate=overall,
        coherent_bias_harmful_mechanism_supported=harmful_mechanism_supported,
        coherent_bias_stably_online_detectable=overall_pass,
        stage3_start_authorized=overall_pass,
        transition="CONTINUE_STAGE3" if overall_pass else "PIVOT",
    )


def gate_result_dict(result: GateResult) -> Mapping[str, Any]:
    value = asdict(result)
    value["status"] = result.status.value
    value["evidence_paths"] = list(result.evidence_paths)
    return value


def validate_gate_summary(summary: Mapping[str, Any]) -> None:
    fixed = {
        "schema_version": DAY14_SCHEMA_VERSION,
        "SEPARABILITY_GATE": "FAIL",
        "CROSS_GEOMETRY_GATE": "PASS",
        "CAUSAL_CONSISTENCY_GATE": "FAIL",
        "NO_GT_GATE": "PASS",
        "STAGE2_GATE": "FAIL",
        "COHERENT_BIAS_HARMFUL_MECHANISM_SUPPORTED": True,
        "COHERENT_BIAS_STABLY_ONLINE_DETECTABLE": False,
        "STAGE3_START_AUTHORIZED": False,
        "STAGE4_START_AUTHORIZED": False,
        "PATENT2_AUTHORIZED": False,
        "COMPLETE_DEGEN_LIO_TRO_ROUTE_AUTHORIZED": False,
        "DETECTOR_PAPER_PIVOT_AUTHORIZED": True,
        "DETECTOR_ONLY_REAL_LIO_ADAPTER_PRIVATE_WORK": "AUTHORIZED",
        "FULL_DEGEN_LIO_FASTLIO2_INTEGRATION": "NOT_AUTHORIZED",
        "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
        "RISK_WARNING_AUTHORIZED": False,
        "PUBLIC_DISCLOSURE_AUTHORIZED": False,
        "transition": "PIVOT",
    }
    if any(
        summary.get(field) != expected
        or type(summary.get(field)) is not type(expected)
        for field, expected in fixed.items()
    ):
        raise ValueError("Day 14 final Gate summary changed")
    if not summary.get("stop_actions") or not summary.get("continue_actions"):
        raise ValueError("Day 14 transition actions are missing")
    details = summary.get("gate_details")
    if not isinstance(details, dict) or set(details) != {
        "separability", "cross_geometry", "causal_consistency", "no_gt"
    }:
        raise ValueError("Day 14 Gate details are incomplete")


def validate_decision_manifest(manifest: Mapping[str, Any]) -> None:
    required = {
        "schema_version", "created_at", "git_branch", "git_commit",
        "worktree_clean", "python_version", "numpy_version", "scipy_version",
        "config_path", "config_sha256", "source_tree_sha256",
        "decision_code_sha256", "statistics_code_sha256",
        "day13_v1_design_lock_sha256", "day13_v1_calibration_lock_sha256",
        "day13_v2_manifest_sha256", "day13_v2_summary_sha256",
        "stage2b_artifact_sha256", "stage2c_artifact_sha256",
        "evidence_file_count", "missing_evidence_count", "invalid_evidence_count",
        "calibration_rerun", "evaluation_rerun", "reserved_test_rerun",
        "estimator_invoked", "retuning_performed", "new_statistic_added",
        "threshold_changed", "seed_changed", "stress_changed",
        "day13_v1_unchanged", "day13_v2_artifact_unchanged",
        "stage2b_artifact_unchanged", "stage2c_artifact_unchanged",
        "DAY14_ENGINEERING_PASS", "DAY14_PROTOCOL_PASS", "DAY14_DECISION_PASS",
        "STAGE2_GATE",
    }
    missing = required - set(manifest)
    if missing:
        raise ValueError("Day 14 manifest missing: " + ", ".join(sorted(missing)))
    if manifest.get("schema_version") != DAY14_SCHEMA_VERSION:
        raise ValueError("Day 14 manifest schema changed")
    for field in (
        "config_sha256", "source_tree_sha256", "decision_code_sha256",
        "statistics_code_sha256", "day13_v1_design_lock_sha256",
        "day13_v1_calibration_lock_sha256", "day13_v2_manifest_sha256",
        "day13_v2_summary_sha256", "stage2b_artifact_sha256",
        "stage2c_artifact_sha256",
    ):
        text = str(manifest.get(field, ""))
        if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
            raise ValueError(f"invalid Day 14 manifest hash: {field}")
    _reject_infinity(manifest)


def evaluate_day14_completion(manifest: Mapping[str, Any]) -> bool:
    fixed = {
        "schema_version": DAY14_SCHEMA_VERSION,
        "worktree_clean": True,
        "missing_evidence_count": 0,
        "invalid_evidence_count": 0,
        "calibration_rerun": False,
        "evaluation_rerun": False,
        "reserved_test_rerun": False,
        "estimator_invoked": False,
        "retuning_performed": False,
        "new_statistic_added": False,
        "threshold_changed": False,
        "seed_changed": False,
        "stress_changed": False,
        "day13_v1_unchanged": True,
        "day13_v2_artifact_unchanged": True,
        "stage2b_artifact_unchanged": True,
        "stage2c_artifact_unchanged": True,
        "output_schema_pass": True,
        "STAGE2_GATE": "FAIL",
    }
    return all(
        manifest.get(field) == expected
        and type(manifest.get(field)) is type(expected)
        for field, expected in fixed.items()
    ) and int(manifest.get("evidence_file_count", 0)) > 0


def value_not_exact(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return True
    if isinstance(expected, Mapping):
        return set(actual) != set(expected) or any(
            value_not_exact(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return len(actual) != len(expected) or any(
            value_not_exact(a, b) for a, b in zip(actual, expected)
        )
    return actual != expected


def _reject_infinity(value: Any) -> None:
    if isinstance(value, Mapping):
        for child in value.values():
            _reject_infinity(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _reject_infinity(child)
    elif isinstance(value, float) and math.isinf(value):
        raise ValueError("Day 14 output contains infinity")
