"""Read-only Stage 2 Day 14 final decision and evidence audit."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
import shutil
import subprocess
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import scipy

from eval.analysis_lock import compute_directory_hash, sha256_file
from eval.stage2_day14_schema import (
    DAY14_SCHEMA_VERSION,
    EVIDENCE_INDEX_FIELDS,
    METRIC_SUMMARY_FIELDS,
    GateResult,
    GateStatus,
    Stage2Decision,
    evaluate_day14_completion,
    gate_result_dict,
    load_day14_config,
    make_stage2_decision,
    validate_decision_manifest,
    validate_gate_summary,
)


BASE_CHECKPOINT = "checkpoint/day13-v2-pass-before-day14"
V1_RUN_RELATIVE = Path(
    "results/stage2_failure_analysis/day13_new_seed/"
    "stage2_failure_day13_new_seed_v1"
)
STAGE2B_RELATIVE = Path("artifacts/history/stage2b_column_scaling_no_go")
STAGE2C_RELATIVE = Path("artifacts/current/weak_update_stage2c")
DAY8_MANIFEST_RELATIVE = Path(
    "results/stage2_failure_analysis/day8_quick/"
    "stage2_failure_day8_quick_v2/run_manifest.json"
)
DAY9_MANIFEST_RELATIVE = Path(
    "results/stage2_failure_analysis/day9_quick/"
    "stage2_failure_day9_quick_v2/run_manifest.json"
)
DAY10_RELATIVE = Path(
    "results/stage2_failure_analysis/day10_quick/stage2_failure_day10_quick_v2"
)
DAY11_RELATIVE = Path(
    "results/stage2_failure_analysis/day11b_replay/"
    "stage2_failure_day11b_replay_v2"
)
DAY12_MANIFEST_RELATIVE = Path(
    "results/stage2_failure_analysis/day12_figures/"
    "stage2_failure_day12_figures_v3/run_manifest.json"
)
DAY13_V2_REQUIRED = (
    "analysis_correction_manifest.json",
    "day13_correction_summary.json",
    "preliminary_criteria_summary_v2.json",
    "auroc_summary_v2.csv",
    "matched_population_audit.csv",
    "locked_threshold_operating_points_v2.csv",
    "fpr_breakdown_v2.csv",
    "gross_control_interpretation_v2.csv",
)
OUTPUT_FILES = {
    "stage2_gate_summary.json",
    "stage2_metric_summary.csv",
    "stage2_evidence_index.csv",
    "stage2_decision_manifest.json",
    "stage2_final_decision.md",
    "stage2_transition_plan.md",
    "SHA256SUMS",
}

STOP_ACTIONS = (
    "Stage 3 innovation-gating development",
    "Stage 4 bias-state estimator",
    "Patent 2",
    "complete robust Degen-LIO T-RO route",
    "further CUSUM/window/threshold or alpha tuning on the same evaluation",
    "risk-warning claims",
)
CONTINUE_ACTIONS = (
    "Patent 1 filing and archive",
    "degeneracy-detection and weak-direction paper",
    "private detector-only real-LIO adapter",
    "public-dataset external validation of H1",
    "comparison of ODI with condition number, lambda_min, and localizability metrics",
    "open-scene false-trigger, direction-stability, and runtime reporting",
)


def evaluate_separability(
    geometry_auroc: float,
    observation_auroc: float,
    weak_clean_fpr: float,
    matched_clean_fprs: Tuple[float, ...],
    auroc_min: float,
    clean_fpr_max: float,
) -> GateResult:
    values = (
        float(geometry_auroc), float(observation_auroc), float(weak_clean_fpr),
        *(float(value) for value in matched_clean_fprs),
    )
    if not matched_clean_fprs or not all(math.isfinite(value) for value in values):
        status = GateStatus.EVIDENCE_INVALID
        reason = "AUROC/FPR evidence is missing or nonfinite."
    else:
        lenient_auroc_pass = max(geometry_auroc, observation_auroc) >= auroc_min
        strict_auroc_pass = min(geometry_auroc, observation_auroc) >= auroc_min
        fpr_pass = weak_clean_fpr <= clean_fpr_max and all(
            value <= clean_fpr_max for value in matched_clean_fprs
        )
        status = GateStatus.PASS if lenient_auroc_pass and fpr_pass else GateStatus.FAIL
        reason = (
            "Lenient interpretation (at least one sweep) and strict interpretation "
            f"(both sweeps) are {'satisfied' if strict_auroc_pass else 'not satisfied'}; "
            "low matched-clean FPR cannot substitute for inadequate AUROC/TPR."
        )
    return GateResult(
        name="separability",
        status=status,
        threshold=f"AUROC >= {auroc_min}; clean FPR <= {clean_fpr_max}",
        observed=(
            f"geometry_auroc={geometry_auroc}; observation_auroc={observation_auroc}; "
            f"weak_clean_fpr={weak_clean_fpr}; matched_clean_fprs={matched_clean_fprs}"
        ),
        reason=reason,
        evidence_paths=(),
    )


def evaluate_cross_geometry_stability(
    per_geometry_effects: Sequence[Mapping[str, Any]],
    required_ratio: float,
) -> GateResult:
    if not per_geometry_effects:
        return GateResult(
            name="cross_geometry",
            status=GateStatus.NOT_ESTABLISHED,
            threshold=f"same-direction geometry ratio >= {required_ratio}",
            observed="no locked per-geometry evidence",
            reason="Pooled or frame-level evidence cannot replace independent geometry units.",
            evidence_paths=(),
        )
    groups: Dict[str, List[Mapping[str, Any]]] = {}
    for row in per_geometry_effects:
        groups.setdefault(str(row.get("sweep")), []).append(row)
    if set(groups) != {"geometry", "observation"}:
        status = GateStatus.EVIDENCE_INVALID
        observed = "required Geometry/Observation groups are incomplete"
    else:
        ratios = {}
        invalid = False
        for sweep, rows in groups.items():
            seeds = [int(row["geometry_seed"]) for row in rows]
            invalid = invalid or len(seeds) != len(set(seeds)) or not rows
            positive = sum(int(_as_bool(row["positive_effect"])) for row in rows)
            ratios[sweep] = (positive, len(rows), float(positive / len(rows)))
        status = (
            GateStatus.EVIDENCE_INVALID if invalid
            else GateStatus.PASS
            if all(value[2] >= required_ratio for value in ratios.values())
            else GateStatus.FAIL
        )
        observed = "; ".join(
            f"{sweep}={positive}/{total}={ratio}"
            for sweep, (positive, total, ratio) in sorted(ratios.items())
        )
    return GateResult(
        name="cross_geometry",
        status=status,
        threshold=f"same-direction geometry ratio >= {required_ratio} in each sweep",
        observed=observed,
        reason=(
            "The locked Day 13 definition uses positive median coherent-minus-clean "
            "primary-score difference per independent geometry; this Gate cannot "
            "override separability."
        ),
        evidence_paths=(),
    )


def evaluate_causal_consistency(
    causal_rows: Sequence[Mapping[str, Any]],
    gross_rows: Sequence[Mapping[str, Any]],
) -> Tuple[GateResult, Optional[bool], str]:
    if not causal_rows:
        return (
            GateResult(
                "causal_consistency", GateStatus.NOT_ESTABLISHED,
                "harmful association supported and gross Huber handling stable",
                "causal evidence missing", "Both preregistered components are required.", (),
            ),
            None,
            "NOT_ESTABLISHED",
        )
    try:
        differences = [float(row["paired_harmful_fraction_difference"]) for row in causal_rows]
        harmful_supported = bool(differences) and all(
            math.isfinite(value) and value > 0.0 for value in differences
        )
    except (KeyError, TypeError, ValueError):
        harmful_supported = False
        differences = []
    required_groups = {
        ("geometry", "L3"), ("geometry", "L4"),
        ("observation", "O3"), ("observation", "O4"),
    }
    available = {(str(row.get("sweep")), str(row.get("level"))) for row in gross_rows}
    gross_valid = available == required_groups
    gross_stable = gross_valid and all(
        math.isfinite(float(row["median_contaminated_huber_downweighted_ratio"]))
        and float(row["median_contaminated_huber_downweighted_ratio"]) > 0.0
        for row in gross_rows
    )
    if not gross_valid:
        status = GateStatus.NOT_ESTABLISHED
        gross_conclusion = "NOT_ESTABLISHED"
    elif not harmful_supported or not gross_stable:
        status = GateStatus.FAIL
        gross_conclusion = "PARTIAL_OR_FAIL"
    else:
        status = GateStatus.PASS
        gross_conclusion = "STABLY_HANDLED"
    l4 = next(
        (row for row in gross_rows if row.get("sweep") == "geometry" and row.get("level") == "L4"),
        {},
    )
    observed = (
        f"harmful_positive_groups={sum(value > 0.0 for value in differences)}/"
        f"{len(differences)}; geometry_L4_median_downweighted="
        f"{l4.get('median_contaminated_huber_downweighted_ratio', 'missing')}; "
        f"geometry_L4_zero_downweight_ratio={l4.get('zero_downweight_case_ratio', 'missing')}"
    )
    return (
        GateResult(
            name="causal_consistency",
            status=status,
            threshold=(
                "coherent harmful-update association supported and gross outliers "
                "stably handled by Huber across all frozen levels"
            ),
            observed=observed,
            reason=(
                "A supported harmful mechanism does not imply online discrimination; "
                "Geometry L4 prevents a claim of stable gross-outlier handling."
            ),
            evidence_paths=(),
        ),
        harmful_supported,
        gross_conclusion,
    )


def evaluate_no_gt_path(evidence: Mapping[str, Any]) -> GateResult:
    required = (
        "online_statistics_no_gt", "gt_removal_trajectory_equivalent",
        "gt_removal_detector_equivalent", "gt_removal_primary_statistic_equivalent",
        "forbidden_gt_fields_absent", "gt_offline_only",
    )
    if any(field not in evidence for field in required):
        status = GateStatus.NOT_ESTABLISHED
        reason = "One or more required no-GT evidence items are missing."
    elif all(evidence[field] is True for field in required):
        status = GateStatus.PASS
        reason = "Online trajectories, detector/window records, and statistics are GT-independent."
    else:
        status = GateStatus.FAIL
        reason = "At least one explicit no-GT equivalence or dependency check failed."
    observed = "; ".join(f"{field}={evidence.get(field, 'missing')}" for field in required)
    return GateResult(
        name="no_gt", status=status,
        threshold="all online-only and GT-removal equivalence checks must pass",
        observed=observed, reason=reason, evidence_paths=(),
    )


def finalize_stage2_day14(
    root: Path,
    config_path: Path,
    day13_v2_dir: Path,
    output_dir: Path,
    overwrite: bool = False,
    report_path: Optional[Path] = None,
) -> Mapping[str, Any]:
    root = Path(root).resolve()
    config_path = Path(config_path).resolve()
    day13_v2_dir = Path(day13_v2_dir).resolve()
    output_dir = Path(output_dir).resolve()
    report_path = Path(
        report_path or root / "reports/stage2/day14_stage2_decision.md"
    ).resolve()
    if output_dir == day13_v2_dir or day13_v2_dir in output_dir.parents:
        raise ValueError("Day 14 output cannot overwrite or descend from Day 13 V2")
    clean_at_start = _git_worktree_clean(root)
    config = load_day14_config(config_path)
    inputs = _resolve_inputs(root, day13_v2_dir)
    before = _frozen_hashes(inputs)
    _verify_frozen_chain(root, inputs, before)
    if output_dir.exists():
        if not overwrite:
            raise FileExistsError(f"Day 14 output exists: {output_dir}")
        shutil.rmtree(output_dir)

    v2_manifest = _read_json(inputs["day13_v2_manifest"])
    v2_summary = _read_json(inputs["day13_v2_summary"])
    auroc_rows = _read_csv(inputs["day13_v2_auroc"])
    operating_rows = _read_csv(inputs["day13_v2_operating"])
    fpr_rows = _read_csv(inputs["day13_v2_fpr"])
    gross_rows = _read_csv(inputs["day13_v2_gross"])
    geometry_rows = _read_csv(inputs["day13_v1_geometry_effects"])
    causal_rows = _read_csv(inputs["day13_v1_causal"])
    _verify_day13_values(v2_manifest, v2_summary, auroc_rows, operating_rows, fpr_rows, gross_rows)

    primary_auroc = {
        row["sweep"]: row for row in auroc_rows
        if row["statistic_name"] == "huber_cusum_max"
    }
    operating = {row["sweep"]: row for row in operating_rows}
    evaluation_fpr = {
        row["population"]: row for row in fpr_rows if row["role"] == "evaluation"
    }
    separability = evaluate_separability(
        float(primary_auroc["geometry"]["auroc"]),
        float(primary_auroc["observation"]["auroc"]),
        float(evaluation_fpr["weak_clean"]["fpr"]),
        tuple(float(operating[sweep]["matched_clean_false_positive_rate"])
              for sweep in ("geometry", "observation")),
        float(config["gates"]["separability"]["auroc_min"]),
        float(config["gates"]["separability"]["clean_fpr_max"]),
    )
    separability = replace(
        separability,
        observed=(
            f"Geometry AUROC={primary_auroc['geometry']['auroc']} CI="
            f"[{primary_auroc['geometry']['ci95_lower']},"
            f"{primary_auroc['geometry']['ci95_upper']}], TPR="
            f"{operating['geometry']['true_positive_rate']}, matched-clean FPR="
            f"{operating['geometry']['matched_clean_false_positive_rate']}; "
            f"Observation AUROC={primary_auroc['observation']['auroc']} CI="
            f"[{primary_auroc['observation']['ci95_lower']},"
            f"{primary_auroc['observation']['ci95_upper']}], TPR="
            f"{operating['observation']['true_positive_rate']}, matched-clean FPR="
            f"{operating['observation']['matched_clean_false_positive_rate']}; "
            f"weak_clean FPR={evaluation_fpr['weak_clean']['fpr']}, combined clean FPR="
            f"{evaluation_fpr['clean_all']['fpr']}, open_control FPR="
            f"{evaluation_fpr['open_control']['fpr']}"
        ),
        evidence_paths=tuple(_relative(root, path) for path in (
            inputs["day13_v2_auroc"], inputs["day13_v2_operating"],
            inputs["day13_v2_fpr"],
        )),
    )
    cross_geometry = replace(
        evaluate_cross_geometry_stability(
            geometry_rows,
            float(config["gates"]["cross_geometry"][
                "same_direction_geometry_ratio_min"
            ]),
        ),
        evidence_paths=(_relative(root, inputs["day13_v1_geometry_effects"]),),
    )
    causal, harmful_supported, gross_conclusion = evaluate_causal_consistency(
        causal_rows, gross_rows
    )
    causal = replace(
        causal,
        evidence_paths=(
            _relative(root, inputs["day13_v1_causal"]),
            _relative(root, inputs["day13_v2_gross"]),
        ),
    )
    no_gt_evidence = _build_no_gt_evidence(inputs)
    no_gt = replace(
        evaluate_no_gt_path(no_gt_evidence),
        evidence_paths=tuple(_relative(root, inputs[name]) for name in (
            "day10_manifest", "day10_static", "day10_online_equivalence",
            "day10_window_equivalence", "day11_no_gt", "day13_v1_no_gt",
        )),
    )
    decision = make_stage2_decision(
        separability, cross_geometry, causal, no_gt, harmful_supported
    )
    if decision.overall_gate != GateStatus.FAIL or decision.transition != "PIVOT":
        raise RuntimeError("Day 14 frozen evidence did not produce the required FAIL/PIVOT")

    evidence_rows = _build_evidence_index(root, inputs)
    metric_rows = _build_metric_summary(
        root, inputs, primary_auroc, operating, evaluation_fpr,
        geometry_rows, causal_rows, gross_rows, config,
    )
    gate_summary = _build_gate_summary(decision, gross_conclusion)
    validate_gate_summary(gate_summary)
    report = _final_report(gate_summary, primary_auroc, operating, evaluation_fpr)
    transition_report = _transition_report()

    output_dir.mkdir(parents=True, exist_ok=False)
    _write_json(output_dir / "stage2_gate_summary.json", gate_summary)
    _write_fixed_csv(
        output_dir / "stage2_metric_summary.csv", metric_rows, METRIC_SUMMARY_FIELDS
    )
    _write_fixed_csv(
        output_dir / "stage2_evidence_index.csv", evidence_rows,
        EVIDENCE_INDEX_FIELDS,
    )
    (output_dir / "stage2_final_decision.md").write_text(report, encoding="utf-8")
    (output_dir / "stage2_transition_plan.md").write_text(
        transition_report, encoding="utf-8"
    )

    after = _frozen_hashes(inputs)
    unchanged = {name: before[name] == after[name] for name in before}
    missing_count = sum(row["status"] == "MISSING" for row in evidence_rows)
    invalid_count = sum(row["status"] == "EVIDENCE_INVALID" for row in evidence_rows)
    manifest: Dict[str, Any] = {
        "schema_version": DAY14_SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_branch": _git_branch(root),
        "git_commit": _git_commit(root),
        "worktree_clean": clean_at_start,
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "config_path": _relative(root, config_path),
        "config_sha256": sha256_file(config_path),
        "source_tree_sha256": _day14_source_tree_hash(root),
        "decision_code_sha256": sha256_file(
            root / "src/eval/stage2_day14_decision.py"
        ),
        "statistics_code_sha256": sha256_file(
            root / "src/eval/stage2_failure_day13_correction_v2.py"
        ),
        "day13_v1_design_lock_sha256": before["day13_v1_design_lock"],
        "day13_v1_calibration_lock_sha256": before["day13_v1_calibration_lock"],
        "day13_v1_summary_sha256": before["day13_v1_summary"],
        "day13_v2_manifest_sha256": sha256_file(inputs["day13_v2_manifest"]),
        "day13_v2_summary_sha256": sha256_file(inputs["day13_v2_summary"]),
        "day13_v2_artifact_sha256": before["day13_v2_artifact"],
        "stage2b_artifact_sha256": before["stage2b_artifact"],
        "stage2c_artifact_sha256": before["stage2c_artifact"],
        "stage2b_archive_commit": _git_rev_parse(
            root, "archive/weak-update-stage2b-no-go^{}"
        ),
        "stage2c_archive_commit": _git_rev_parse(
            root, "archive/stage2c-projected-gain-no-go^{}"
        ),
        "evidence_file_count": len(evidence_rows),
        "missing_evidence_count": missing_count,
        "invalid_evidence_count": invalid_count,
        "calibration_rerun": False,
        "evaluation_rerun": False,
        "reserved_test_rerun": False,
        "estimator_invoked": False,
        "retuning_performed": False,
        "new_statistic_added": False,
        "threshold_changed": False,
        "seed_changed": False,
        "stress_changed": False,
        "day13_v1_unchanged": all(unchanged[name] for name in (
            "day13_v1_design_lock", "day13_v1_calibration_lock", "day13_v1_summary"
        )),
        "day13_v2_artifact_unchanged": unchanged["day13_v2_artifact"],
        "stage2b_artifact_unchanged": unchanged["stage2b_artifact"],
        "stage2c_artifact_unchanged": unchanged["stage2c_artifact"],
        "frozen_hashes_before": before,
        "frozen_hashes_after": after,
        "output_schema_pass": True,
        "SEPARABILITY_GATE": decision.separability.status.value,
        "CROSS_GEOMETRY_GATE": decision.cross_geometry.status.value,
        "CAUSAL_CONSISTENCY_GATE": decision.causal_consistency.status.value,
        "NO_GT_GATE": decision.no_gt.status.value,
        "STAGE2_GATE": decision.overall_gate.value,
        "DAY14_ENGINEERING_PASS": False,
        "DAY14_PROTOCOL_PASS": False,
        "DAY14_DECISION_PASS": False,
    }
    engineering = evaluate_day14_completion(manifest)
    protocol = all((
        not manifest["calibration_rerun"], not manifest["evaluation_rerun"],
        not manifest["reserved_test_rerun"], not manifest["estimator_invoked"],
        not manifest["retuning_performed"], not manifest["new_statistic_added"],
        not manifest["threshold_changed"], not manifest["seed_changed"],
        not manifest["stress_changed"], manifest["day13_v1_unchanged"],
        manifest["day13_v2_artifact_unchanged"],
        manifest["stage2b_artifact_unchanged"],
        manifest["stage2c_artifact_unchanged"], clean_at_start,
    ))
    manifest["DAY14_ENGINEERING_PASS"] = engineering
    manifest["DAY14_PROTOCOL_PASS"] = protocol
    manifest["DAY14_DECISION_PASS"] = bool(engineering and protocol)
    validate_decision_manifest(manifest)
    if not manifest["DAY14_DECISION_PASS"]:
        raise RuntimeError("Day 14 decision audit did not complete")
    _write_json(output_dir / "stage2_decision_manifest.json", manifest)
    _write_sha256s(output_dir)
    _validate_output_directory(output_dir)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    return {
        "gate_summary": gate_summary,
        "manifest": manifest,
        "output_dir": str(output_dir),
        "report_path": str(report_path),
    }


def _resolve_inputs(root: Path, day13_v2_dir: Path) -> Mapping[str, Path]:
    v1 = root / V1_RUN_RELATIVE
    paths = {
        "day13_v1_design_lock": v1 / "design/design_lock.json",
        "day13_v1_calibration_lock": v1 / "calibration/calibration_threshold_lock.json",
        "day13_v1_summary": v1 / "day13_summary.json",
        "day13_v1_manifest": v1 / "run_manifest.json",
        "day13_v1_geometry_effects": v1 / "evaluation/geometry_effects.csv",
        "day13_v1_causal": v1 / "evaluation/causal_consistency.csv",
        "day13_v1_no_gt": v1 / "evaluation/no_gt_audit.json",
        "day13_v1_case_summary": v1 / "evaluation/case_summary.csv",
        "day13_v2_artifact": day13_v2_dir,
        "day13_v2_manifest": day13_v2_dir / "analysis_correction_manifest.json",
        "day13_v2_summary": day13_v2_dir / "day13_correction_summary.json",
        "day13_v2_preliminary": day13_v2_dir / "preliminary_criteria_summary_v2.json",
        "day13_v2_auroc": day13_v2_dir / "auroc_summary_v2.csv",
        "day13_v2_matching": day13_v2_dir / "matched_population_audit.csv",
        "day13_v2_operating": day13_v2_dir / "locked_threshold_operating_points_v2.csv",
        "day13_v2_fpr": day13_v2_dir / "fpr_breakdown_v2.csv",
        "day13_v2_gross": day13_v2_dir / "gross_control_interpretation_v2.csv",
        "stage2b_artifact": root / STAGE2B_RELATIVE,
        "stage2b_manifest": root / STAGE2B_RELATIVE / "test_manifest.json",
        "stage2c_artifact": root / STAGE2C_RELATIVE,
        "stage2c_manifest": root / STAGE2C_RELATIVE / "test_manifest.json",
        "day8_manifest": root / DAY8_MANIFEST_RELATIVE,
        "day9_manifest": root / DAY9_MANIFEST_RELATIVE,
        "day10_manifest": root / DAY10_RELATIVE / "run_manifest.json",
        "day10_static": root / DAY10_RELATIVE / "static_dependency_audit.json",
        "day10_online_equivalence": root / DAY10_RELATIVE / "online_equivalence_audit.csv",
        "day10_window_equivalence": root / DAY10_RELATIVE / "window_equivalence_audit.csv",
        "day11_manifest": root / DAY11_RELATIVE / "run_manifest.json",
        "day11_no_gt": root / DAY11_RELATIVE / "no_gt_audit.json",
        "day12_manifest": root / DAY12_MANIFEST_RELATIVE,
    }
    missing = [name for name, path in paths.items() if not path.exists()]
    if missing:
        raise FileNotFoundError("Day 14 evidence missing: " + ", ".join(sorted(missing)))
    if any(not (day13_v2_dir / name).is_file() for name in DAY13_V2_REQUIRED):
        raise FileNotFoundError("Day 13 V2 artifact is incomplete")
    return paths


def _frozen_hashes(inputs: Mapping[str, Path]) -> Mapping[str, str]:
    return {
        "day13_v1_design_lock": sha256_file(inputs["day13_v1_design_lock"]),
        "day13_v1_calibration_lock": sha256_file(inputs["day13_v1_calibration_lock"]),
        "day13_v1_summary": sha256_file(inputs["day13_v1_summary"]),
        "day13_v2_artifact": compute_directory_hash(inputs["day13_v2_artifact"]),
        "stage2b_artifact": compute_directory_hash(inputs["stage2b_artifact"]),
        "stage2c_artifact": compute_directory_hash(inputs["stage2c_artifact"]),
    }


def _verify_frozen_chain(
    root: Path, inputs: Mapping[str, Path], hashes: Mapping[str, str]
) -> None:
    v2 = _read_json(inputs["day13_v2_manifest"])
    if not all(v2.get(field) is True for field in (
        "DAY13_CORRECTION_ENGINEERING_PASS", "DAY13_CORRECTION_PROTOCOL_PASS",
        "DAY13_CORRECTION_PASS", "DAY14_STAGE2_DECISION_AUTHORIZED",
        "input_immutability_pass", "threshold_unchanged",
    )):
        raise ValueError("Day 13 V2 correction Gate is not complete")
    if v2.get("STAGE2_GATE") != "INCOMPLETE" or v2.get("STAGE3_GATE") != "NOT_STARTED":
        raise ValueError("Day 13 V2 source contains a premature decision")
    if hashes["day13_v1_design_lock"] != v2["source_design_lock_sha256"]:
        raise ValueError("Day 13 V1 design lock differs from V2 provenance")
    if hashes["day13_v1_calibration_lock"] != v2["source_calibration_lock_sha256"]:
        raise ValueError("Day 13 V1 calibration lock differs from V2 provenance")
    if hashes["day13_v1_summary"] != v2["source_v1_summary_sha256"]:
        raise ValueError("Day 13 V1 summary differs from V2 provenance")
    design = _read_json(inputs["day13_v1_design_lock"])
    expected_historical = design["historical_artifact_hashes_at_design"]
    if hashes["stage2b_artifact"] != expected_historical[str(STAGE2B_RELATIVE)]:
        raise ValueError("Stage 2B artifact changed after the Day 13 design lock")
    if hashes["stage2c_artifact"] != expected_historical[str(STAGE2C_RELATIVE)]:
        raise ValueError("Stage 2C artifact changed after the Day 13 design lock")
    result = subprocess.run(
        ["git", "diff", "--quiet", BASE_CHECKPOINT, "--",
         "artifacts/current/stage2_day13_analysis_correction_v2"],
        cwd=str(root), check=False,
    )
    if result.returncode != 0:
        raise ValueError("Day 13 V2 tracked artifact differs from the frozen checkpoint")
    stage2b = _read_json(inputs["stage2b_manifest"])
    stage2c = _read_json(inputs["stage2c_manifest"])
    if stage2b.get("gates", {}).get("selective_update") != "SELECTIVE_UPDATE_FAIL":
        raise ValueError("Stage 2B historical Gate changed")
    if stage2c.get("gates", {}).get("PROJECTED_GAIN_UPDATE") != "PROJECTED_GAIN_UPDATE_FAIL":
        raise ValueError("Stage 2C historical Gate changed")


def _verify_day13_values(
    manifest: Mapping[str, Any], summary: Mapping[str, Any],
    auroc_rows: Sequence[Mapping[str, Any]],
    operating_rows: Sequence[Mapping[str, Any]],
    fpr_rows: Sequence[Mapping[str, Any]],
    gross_rows: Sequence[Mapping[str, Any]],
) -> None:
    if manifest.get("locked_threshold") != 13.745952939169019:
        raise ValueError("Day 13 V2 locked threshold differs from the frozen evidence")
    if summary.get("schema_version") != "stage2_failure_day13_analysis_correction_v2":
        raise ValueError("Day 13 V2 summary schema changed")
    primary = {row["sweep"]: row for row in auroc_rows if row["statistic_name"] == "huber_cusum_max"}
    operating = {row["sweep"]: row for row in operating_rows}
    evaluation_fpr = {row["population"]: row for row in fpr_rows if row["role"] == "evaluation"}
    if set(primary) != {"geometry", "observation"} or set(operating) != {"geometry", "observation"}:
        raise ValueError("Day 13 V2 primary evidence is incomplete")
    comparisons = {
        "corrected_geometry_auroc": float(primary["geometry"]["auroc"]),
        "corrected_geometry_ci95_lower": float(primary["geometry"]["ci95_lower"]),
        "corrected_geometry_ci95_upper": float(primary["geometry"]["ci95_upper"]),
        "corrected_observation_auroc": float(primary["observation"]["auroc"]),
        "corrected_observation_ci95_lower": float(primary["observation"]["ci95_lower"]),
        "corrected_observation_ci95_upper": float(primary["observation"]["ci95_upper"]),
        "geometry_locked_threshold_tpr": float(operating["geometry"]["true_positive_rate"]),
        "geometry_matched_clean_fpr": float(operating["geometry"]["matched_clean_false_positive_rate"]),
        "observation_locked_threshold_tpr": float(operating["observation"]["true_positive_rate"]),
        "observation_matched_clean_fpr": float(operating["observation"]["matched_clean_false_positive_rate"]),
    }
    if any(float(manifest.get(field, float("nan"))) != value for field, value in comparisons.items()):
        raise ValueError("Day 13 V2 manifest disagrees with its metric tables")
    if set(evaluation_fpr) != {"clean_all", "weak_clean", "open_control"}:
        raise ValueError("Day 13 V2 FPR populations are incomplete")
    if manifest.get("clean_fpr_target_status") != "MIXED_POPULATION_DEPENDENT":
        raise ValueError("Day 13 V2 clean FPR interpretation changed")
    l4 = [row for row in gross_rows if row["sweep"] == "geometry" and row["level"] == "L4"]
    if len(l4) != 1 or float(l4[0]["zero_downweight_case_ratio"]) != float(
        manifest["geometry_l4_zero_downweight_case_ratio"]
    ):
        raise ValueError("Day 13 V2 Geometry L4 gross evidence changed")


def _build_no_gt_evidence(inputs: Mapping[str, Path]) -> Mapping[str, bool]:
    day10 = _read_json(inputs["day10_manifest"])
    static = _read_json(inputs["day10_static"])
    day11 = _read_json(inputs["day11_no_gt"])
    day13 = _read_json(inputs["day13_v1_no_gt"])
    online = _read_csv(inputs["day10_online_equivalence"])
    window = _read_csv(inputs["day10_window_equivalence"])
    gt_removed_online = [row for row in online if row.get("variant") == "gt_removed"]
    return {
        "online_statistics_no_gt": bool(
            day10.get("DAY10_NO_GT_AUDIT_PASS")
            and int(day10.get("gt_field_access_attempt_count", -1)) == 0
            and day11.get("online_estimator_received_gt") is False
            and day13.get("online_estimator_received_gt") is False
            and int(day13.get("gt_field_access_attempt_count", -1)) == 0
        ),
        "gt_removal_trajectory_equivalent": bool(
            gt_removed_online and all(_as_bool(row["pass"]) for row in gt_removed_online)
        ),
        "gt_removal_detector_equivalent": bool(
            window and all(_as_bool(row["pass"]) for row in window)
        ),
        "gt_removal_primary_statistic_equivalent": bool(
            window and all(_as_bool(row["records_equal"]) for row in window)
        ),
        "forbidden_gt_fields_absent": bool(
            static.get("audit_pass")
            and not static.get("forbidden_imports")
            and not static.get("forbidden_online_schema_fields")
            and not static.get("forbidden_signature_parameters")
        ),
        "gt_offline_only": bool(
            day11.get("gt_evaluator_called_after_online_estimation")
            and day13.get("gt_evaluator_called_after_online_estimation")
            and day13.get("gt_used_for_threshold_or_score") is False
        ),
    }


def _build_evidence_index(
    root: Path, inputs: Mapping[str, Path]
) -> Sequence[Mapping[str, Any]]:
    v1_manifest = _read_json(inputs["day13_v1_manifest"])
    records = [
        ("day8_logging", "8", "per-frame logging Gate", "day8_manifest", "PASS", "NO_GT_GATE"),
        ("day9_window", "9", "causal window-statistics Gate", "day9_manifest", "PASS", "CAUSAL_CONSISTENCY_GATE"),
        ("day10_no_gt", "10", "no-GT audit manifest", "day10_manifest", "PASS", "NO_GT_GATE"),
        ("day10_static", "10", "online static no-GT dependency audit", "day10_static", "PASS", "NO_GT_GATE"),
        ("day10_online_equivalence", "10", "GT-removal trajectory equivalence", "day10_online_equivalence", "PASS", "NO_GT_GATE"),
        ("day10_window_equivalence", "10", "GT-removal detector/statistic equivalence", "day10_window_equivalence", "PASS", "NO_GT_GATE"),
        ("day11_replay", "11", "representative locked diagnostic replay", "day11_manifest", "PASS", "CAUSAL_CONSISTENCY_GATE;NO_GT_GATE"),
        ("day11_no_gt", "11", "replay no-GT audit", "day11_no_gt", "PASS", "NO_GT_GATE"),
        ("day12_diagnostics", "12", "diagnostic figure/input-lock manifest", "day12_manifest", "PASS", "CAUSAL_CONSISTENCY_GATE"),
        ("day13_v1_geometry", "13", "locked per-geometry primary-score effects", "day13_v1_geometry_effects", "VALID", "CROSS_GEOMETRY_GATE"),
        ("day13_v1_causal", "13", "paired harmful-update causal evidence", "day13_v1_causal", "VALID", "CAUSAL_CONSISTENCY_GATE"),
        ("day13_v1_no_gt", "13", "evaluation no-GT audit", "day13_v1_no_gt", "PASS", "NO_GT_GATE"),
        ("day13_v2_manifest", "13V2", "analysis-correction manifest", "day13_v2_manifest", "PASS", "ALL"),
        ("day13_v2_auroc", "13V2", "corrected matched AUROC", "day13_v2_auroc", "VALID", "SEPARABILITY_GATE"),
        ("day13_v2_operating", "13V2", "locked-threshold operating points", "day13_v2_operating", "VALID", "SEPARABILITY_GATE"),
        ("day13_v2_fpr", "13V2", "population-separated FPR", "day13_v2_fpr", "VALID", "SEPARABILITY_GATE"),
        ("day13_v2_gross", "13V2", "gross Huber handling by level", "day13_v2_gross", "VALID", "CAUSAL_CONSISTENCY_GATE"),
        ("day13_v2_matching", "13V2", "one-to-one population audit", "day13_v2_matching", "PASS", "SEPARABILITY_GATE"),
        ("stage2b_no_go", "2B", "column-scaling historical NO-GO", "stage2b_artifact", "SELECTIVE_UPDATE_FAIL", "TRANSITION"),
        ("stage2c_no_go", "2C", "projected-gain historical NO-GO", "stage2c_artifact", "PROJECTED_GAIN_UPDATE_FAIL", "TRANSITION"),
    ]
    json_metadata = {
        name: _metadata(inputs[name]) for name in (
            "day8_manifest", "day9_manifest", "day10_manifest", "day10_static",
            "day11_manifest", "day11_no_gt", "day12_manifest", "day13_v1_no_gt",
            "day13_v2_manifest", "stage2b_manifest", "stage2c_manifest",
        )
    }
    source_commits = {
        "day13_v1_geometry_effects": str(v1_manifest["git_commit"]),
        "day13_v1_causal": str(v1_manifest["git_commit"]),
        "day13_v2_auroc": str(_read_json(inputs["day13_v2_manifest"])["current_git_commit"]),
        "day13_v2_operating": str(_read_json(inputs["day13_v2_manifest"])["current_git_commit"]),
        "day13_v2_fpr": str(_read_json(inputs["day13_v2_manifest"])["current_git_commit"]),
        "day13_v2_gross": str(_read_json(inputs["day13_v2_manifest"])["current_git_commit"]),
        "day13_v2_matching": str(_read_json(inputs["day13_v2_manifest"])["current_git_commit"]),
        "day10_online_equivalence": str(_read_json(inputs["day10_manifest"])["git_commit"]),
        "day10_window_equivalence": str(_read_json(inputs["day10_manifest"])["git_commit"]),
        "stage2b_artifact": str(_read_json(inputs["stage2b_manifest"])["git_commit"]),
        "stage2c_artifact": str(_read_json(inputs["stage2c_manifest"])["git_commit"]),
    }
    output = []
    for evidence_id, day, description, name, status, gate in records:
        path = inputs[name]
        metadata_name = name
        if name == "stage2b_artifact":
            metadata_name = "stage2b_manifest"
        elif name == "stage2c_artifact":
            metadata_name = "stage2c_manifest"
        meta = json_metadata.get(metadata_name, {})
        output.append({
            "evidence_id": evidence_id,
            "stage_day": day,
            "description": description,
            "path": _relative(root, path),
            "sha256": compute_directory_hash(path) if path.is_dir() else sha256_file(path),
            "schema_version": meta.get("schema_version", "NOT_EMBEDDED"),
            "source_commit": source_commits.get(name, meta.get("source_commit", "NOT_EMBEDDED")),
            "status": status,
            "used_by_gate": gate,
        })
    return output


def _build_metric_summary(
    root: Path, inputs: Mapping[str, Path],
    primary: Mapping[str, Mapping[str, Any]],
    operating: Mapping[str, Mapping[str, Any]],
    fpr: Mapping[str, Mapping[str, Any]],
    geometry_rows: Sequence[Mapping[str, Any]],
    causal_rows: Sequence[Mapping[str, Any]],
    gross_rows: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
) -> Sequence[Mapping[str, Any]]:
    rows: List[Mapping[str, Any]] = []
    auroc_target = float(config["gates"]["separability"]["auroc_min"])
    fpr_target = float(config["gates"]["separability"]["clean_fpr_max"])
    geometry_target = float(
        config["gates"]["cross_geometry"]["same_direction_geometry_ratio_min"]
    )
    for sweep in ("geometry", "observation"):
        row = primary[sweep]
        rows.append(_metric(
            "primary_auroc", sweep, "matched_clean_vs_coherent_active",
            float(row["auroc"]), row["ci95_lower"], row["ci95_upper"],
            auroc_target, float(row["auroc"]) >= auroc_target,
            root, inputs["day13_v2_auroc"],
        ))
        point = operating[sweep]
        rows.append(_metric(
            "locked_threshold_tpr", sweep, "coherent_active",
            point["true_positive_rate"], "", "", "descriptive", "descriptive",
            root, inputs["day13_v2_operating"],
        ))
        rows.append(_metric(
            "matched_clean_fpr", sweep, "matched_clean",
            point["matched_clean_false_positive_rate"], "", "", fpr_target,
            float(point["matched_clean_false_positive_rate"]) <= fpr_target,
            root, inputs["day13_v2_operating"],
        ))
    for population in ("clean_all", "weak_clean", "open_control"):
        row = fpr[population]
        rows.append(_metric(
            "evaluation_fpr", "all", population, row["fpr"], "", "", fpr_target,
            _as_bool(row["target_met"]), root, inputs["day13_v2_fpr"],
        ))
    for sweep in ("geometry", "observation"):
        selected = [row for row in geometry_rows if row["sweep"] == sweep]
        positive = sum(_as_bool(row["positive_effect"]) for row in selected)
        ratio = float(positive / len(selected))
        rows.append(_metric(
            "same_direction_geometry_ratio", sweep, "independent_geometry",
            ratio, "", "", geometry_target, ratio >= geometry_target,
            root, inputs["day13_v1_geometry_effects"],
        ))
        causal = [row for row in causal_rows if row["sweep"] == sweep]
        rows.extend((
            _metric(
                "clean_harmful_update_fraction", sweep, "matched_clean",
                float(np.mean([float(row["clean_harmful_fraction"]) for row in causal])),
                "", "", "descriptive", "descriptive", root, inputs["day13_v1_causal"],
            ),
            _metric(
                "coherent_harmful_update_fraction", sweep, "coherent_active",
                float(np.mean([float(row["coherent_harmful_fraction"]) for row in causal])),
                "", "", "descriptive", "descriptive", root, inputs["day13_v1_causal"],
            ),
            _metric(
                "paired_harmful_fraction_difference", sweep, "independent_geometry",
                float(np.mean([float(row["paired_harmful_fraction_difference"]) for row in causal])),
                "", "", ">0 in every geometry", all(
                    float(row["paired_harmful_fraction_difference"]) > 0 for row in causal
                ), root, inputs["day13_v1_causal"],
            ),
        ))
    for row in gross_rows:
        rows.append(_metric(
            "gross_median_huber_downweighted_ratio", row["sweep"], row["level"],
            row["median_contaminated_huber_downweighted_ratio"], "", "",
            "stable across all levels", float(row["median_contaminated_huber_downweighted_ratio"]) > 0,
            root, inputs["day13_v2_gross"],
        ))
        if row["sweep"] == "geometry" and row["level"] == "L4":
            rows.append(_metric(
                "gross_zero_downweight_case_ratio", "geometry", "L4",
                row["zero_downweight_case_ratio"], "", "", "descriptive",
                False, root, inputs["day13_v2_gross"],
            ))
    return rows


def _metric(
    metric: str, sweep: str, population: str, observed: Any,
    lower: Any, upper: Any, threshold: Any, target_met: Any,
    root: Path, source: Path,
) -> Mapping[str, Any]:
    return {
        "metric": metric, "sweep": sweep, "population": population,
        "observed": observed, "ci95_lower": lower, "ci95_upper": upper,
        "threshold": threshold, "target_met": target_met,
        "source_path": _relative(root, source), "source_sha256": sha256_file(source),
    }


def _build_gate_summary(
    decision: Stage2Decision, gross_conclusion: str
) -> Mapping[str, Any]:
    return {
        "schema_version": DAY14_SCHEMA_VERSION,
        "SEPARABILITY_GATE": decision.separability.status.value,
        "CROSS_GEOMETRY_GATE": decision.cross_geometry.status.value,
        "CAUSAL_CONSISTENCY_GATE": decision.causal_consistency.status.value,
        "NO_GT_GATE": decision.no_gt.status.value,
        "STAGE2_GATE": decision.overall_gate.value,
        "HARMFUL_UPDATE_ASSOCIATION": (
            "SUPPORTED" if decision.coherent_bias_harmful_mechanism_supported
            else "NOT_SUPPORTED" if decision.coherent_bias_harmful_mechanism_supported is False
            else "UNDETERMINED"
        ),
        "GROSS_OUTLIER_HUBER_HANDLING": gross_conclusion,
        "COHERENT_BIAS_HARMFUL_MECHANISM_SUPPORTED": (
            decision.coherent_bias_harmful_mechanism_supported
        ),
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
        "transition": decision.transition,
        "stop_actions": list(STOP_ACTIONS),
        "continue_actions": list(CONTINUE_ACTIONS),
        "gate_details": {
            "separability": gate_result_dict(decision.separability),
            "cross_geometry": gate_result_dict(decision.cross_geometry),
            "causal_consistency": gate_result_dict(decision.causal_consistency),
            "no_gt": gate_result_dict(decision.no_gt),
        },
    }


def _final_report(
    summary: Mapping[str, Any], primary: Mapping[str, Mapping[str, Any]],
    operating: Mapping[str, Mapping[str, Any]],
    fpr: Mapping[str, Mapping[str, Any]],
) -> str:
    return f"""# Stage 2 Final Decision: FAIL

The controlled coherent-slip mechanism can increase harmful weak-direction
updates, but the locked no-GT `huber_cusum_max` statistic does not stably
separate coherent bias from clean weak-observability fluctuations.

Corrected AUROC is {float(primary['geometry']['auroc']):.4f} for Geometry and
{float(primary['observation']['auroc']):.4f} for Observation, both substantially
below the preregistered 0.80 threshold.

At approximately 8%-9% matched-clean FPR, the locked operating point detects
only approximately {100*float(operating['geometry']['true_positive_rate']):.1f}%
to {100*float(operating['observation']['true_positive_rate']):.1f}% of coherent
active frames. Evaluation weak-clean FPR is {fpr['weak_clean']['fpr']}, so the
clean-FPR result remains population-dependent.

Therefore, stable online coherent-bias detectability is not established.
Stage 3, Stage 4, Patent 2, and the complete robust Degen-LIO T-RO route are not
authorized. The formal transition is **{summary['transition']}**.

## 中文摘要

受控相干偏差会增加有害弱方向更新，但当前锁定的无GT统计量
`huber_cusum_max` 无法稳定地区分“相干有害偏差”和“正常弱可观波动”。

因此，H2 中“可稳定在线检测”的部分未成立。Stage 2 判定失败，项目转向
专利一和退化检测＋弱方向识别论文路线。

有害机制得到支持不等于在线检测器得到支持。本报告不授权 Stage 3、
FAST-LIO2 完整集成、风险预警主张或公开披露。
"""


def _transition_report() -> str:
    stopped = "\n".join(f"- {item}" for item in STOP_ACTIONS)
    continued = "\n".join(f"- {item}" for item in CONTINUE_ACTIONS)
    return f"""# Stage 2 Day 14 Transition Plan

## Stop

{stopped}

## Preserve

- Stage 2A degeneration detector, translation Schur information spectrum, and ODI
- weak direction, eigengap, and direction reliability
- minibench and pairing/lock/bootstrap/no-GT audit framework
- Stage 2B/2C negative results and Stage 2 failure-mechanism evidence

## Authorized pivot

{continued}

`DETECTOR_ONLY_REAL_LIO_ADAPTER_PRIVATE_WORK = AUTHORIZED`

`FULL_DEGEN_LIO_FASTLIO2_INTEGRATION = NOT_AUTHORIZED`

The detector-only real-LIO adapter is private read-only research. It is not a
complete Degen-LIO or formal FAST-LIO2 estimator integration. Public disclosure
remains unauthorized until Patent 1 has been formally filed and filing materials
have been received.
"""


def _validate_output_directory(path: Path) -> None:
    actual = {item.name for item in path.iterdir() if item.is_file()}
    if actual != OUTPUT_FILES:
        raise ValueError("Day 14 output file set changed")
    gate = _read_json(path / "stage2_gate_summary.json")
    manifest = _read_json(path / "stage2_decision_manifest.json")
    validate_gate_summary(gate)
    validate_decision_manifest(manifest)
    if not manifest.get("DAY14_DECISION_PASS") or manifest.get("STAGE2_GATE") != "FAIL":
        raise ValueError("Day 14 engineering decision and scientific Gate were conflated")
    for csv_path, fields in (
        (path / "stage2_metric_summary.csv", METRIC_SUMMARY_FIELDS),
        (path / "stage2_evidence_index.csv", EVIDENCE_INDEX_FIELDS),
    ):
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            if tuple(next(reader)) != tuple(fields) or not list(reader):
                raise ValueError(f"Day 14 CSV is empty or changed: {csv_path.name}")
    expected = {}
    for line in (path / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        expected[name] = digest
    for name in OUTPUT_FILES - {"SHA256SUMS"}:
        if expected.get(name) != sha256_file(path / name):
            raise ValueError(f"Day 14 SHA256SUMS mismatch: {name}")


def _write_sha256s(path: Path) -> None:
    lines = [
        f"{sha256_file(path / name)}  {name}"
        for name in sorted(OUTPUT_FILES - {"SHA256SUMS"})
    ]
    (path / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _day14_source_tree_hash(root: Path) -> str:
    paths = [
        root / "src/eval/stage2_day14_schema.py",
        root / "src/eval/stage2_day14_decision.py",
        root / "scripts/40_finalize_stage2_day14.py",
        root / "configs/stage2/day14_decision.yaml",
        root / "docs/stage2_day14_decision_contract.md",
        root / "docs/stage2_day14_transition_plan.md",
    ] + sorted((root / "tests").glob("test_stage2_day14_*.py"))
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(_relative(root, path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(path).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _metadata(path: Path) -> Mapping[str, str]:
    if path.suffix != ".json":
        return {}
    value = _read_json(path)
    return {
        "schema_version": str(value.get("schema_version", "NOT_EMBEDDED")),
        "source_commit": str(
            value.get("git_commit", value.get("current_git_commit", "NOT_EMBEDDED"))
        ),
    }


def _read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON mapping: {path}")
    return value


def _read_csv(path: Path) -> Sequence[Mapping[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _write_fixed_csv(
    path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _as_bool(value: Any) -> bool:
    if type(value) is bool:
        return value
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise ValueError(f"invalid boolean: {value}")


def _relative(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root))
    except ValueError:
        return str(path.resolve())


def _git_worktree_clean(root: Path) -> bool:
    return not subprocess.run(
        ["git", "status", "--porcelain"], cwd=str(root), check=True,
        stdout=subprocess.PIPE, text=True,
    ).stdout.strip()


def _git_branch(root: Path) -> str:
    return subprocess.run(
        ["git", "branch", "--show-current"], cwd=str(root), check=True,
        stdout=subprocess.PIPE, text=True,
    ).stdout.strip()


def _git_commit(root: Path) -> str:
    return _git_rev_parse(root, "HEAD")


def _git_rev_parse(root: Path, ref: str) -> str:
    return subprocess.run(
        ["git", "rev-parse", ref], cwd=str(root), check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    ).stdout.strip()
