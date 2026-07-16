"""Offline-only one-to-one matched-population correction for Day 13 V1."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import numpy as np

from eval.stage2_failure_day13_correction_schema import (
    ANALYSIS_POPULATION,
    AUROC_SUMMARY_V2_FIELDS,
    CORRECTION_ID,
    CORRECTION_SCHEMA_VERSION,
    FPR_BREAKDOWN_V2_FIELDS,
    GROSS_CONTROL_INTERPRETATION_V2_FIELDS,
    LOCKED_OPERATING_POINT_FIELDS,
    MATCHED_POPULATION_AUDIT_FIELDS,
    MATCHING_KEY_DESCRIPTION,
    PRIMARY_ROC_POINTS_V2_FIELDS,
    evaluate_correction_gate,
    validate_correction_manifest,
    validate_fixed_rows,
    validate_output_directory,
)
from eval.stage2_failure_day13_schema import FRAME_SCORE_FIELDS
from eval.stage2_failure_day13_statistics import (
    PRIMARY_STATISTIC,
    SECONDARY_STATISTICS,
    block_bootstrap_auroc,
    primary_score_eligible,
    statistic_score,
    threshold_false_positive_rate,
)


MATCH_KEY_FIELDS = (
    "sweep",
    "level",
    "geometry_seed",
    "sensor_seed",
    "process_seed",
    "method",
    "frame_index",
)
LOCKED_THRESHOLD = 13.745952939169019
THRESHOLD_OPERATOR = ">"
BOOTSTRAP_REPETITIONS = 5000
BOOTSTRAP_SEED = 23131
BOOTSTRAP_BLOCK = "geometry_seed"
ALL_STATISTICS = (PRIMARY_STATISTIC,) + SECONDARY_STATISTICS


def build_matched_analysis_population(
    frame_scores: Sequence[Mapping[str, Any]],
    sweep: str,
    statistic: str,
) -> Mapping[str, Any]:
    """Pair every eligible active coherent row with its unique clean twin."""

    if sweep not in {"geometry", "observation"}:
        raise ValueError("Day 13 correction sweep must be geometry or observation")
    if statistic not in ALL_STATISTICS:
        raise ValueError(f"unregistered Day 13 correction statistic: {statistic}")

    relevant = [
        row for row in frame_scores
        if str(row.get("role")) == "evaluation" and str(row.get("sweep")) == sweep
    ]
    positives = [
        row for row in relevant
        if str(row.get("stress")) == "coherent_subhuber_slip"
        and bool(row.get("stress_active"))
        and primary_score_eligible(row)
    ]
    clean = [
        row for row in relevant
        if str(row.get("stress")) == "clean" and primary_score_eligible(row)
    ]

    positive_counts = Counter(_match_key(row) for row in positives)
    clean_counts = Counter(_match_key(row) for row in clean)
    duplicate_positive = sum(count - 1 for count in positive_counts.values() if count > 1)
    duplicate_clean = sum(count - 1 for count in clean_counts.values() if count > 1)
    if duplicate_positive:
        raise ValueError("Day 13 correction found duplicate coherent matching keys")
    if duplicate_clean:
        raise ValueError("Day 13 correction found duplicate clean matching keys")

    clean_index = {_match_key(row): row for row in clean}
    selected: List[Mapping[str, Any]] = []
    used_clean_keys = set()
    pair_records: List[Mapping[str, Any]] = []
    invalid_pair_count = 0
    for positive in positives:
        key = _match_key(positive)
        negative = clean_index.get(key)
        if negative is None:
            raise ValueError("Day 13 correction coherent row has no matched clean row")
        if float(positive["timestamp"]) != float(negative["timestamp"]):
            raise ValueError("Day 13 correction matched timestamps differ")
        positive_score = statistic_score(positive, statistic)
        negative_score = statistic_score(negative, statistic)
        pair_id = _pair_id(positive)
        finite = math.isfinite(positive_score) and math.isfinite(negative_score)
        pair_records.append({
            "pair_id": pair_id,
            "match_key": key,
            "timestamp": float(positive["timestamp"]),
            "pair_valid": finite,
        })
        used_clean_keys.add(key)
        if not finite:
            invalid_pair_count += 1
            continue
        selected.extend((
            {
                **positive,
                "pair_id": pair_id,
                "analysis_score": float(positive_score),
                "analysis_label": 1,
                "analysis_pair_role": "coherent_positive",
            },
            {
                **negative,
                "pair_id": pair_id,
                "analysis_score": float(negative_score),
                "analysis_label": 0,
                "analysis_pair_role": "matched_clean_negative",
            },
        ))

    finite_clean_keys = {
        _match_key(row) for row in clean
        if math.isfinite(statistic_score(row, statistic))
    }
    positive_count = sum(int(row["analysis_label"] == 1) for row in selected)
    negative_count = sum(int(row["analysis_label"] == 0) for row in selected)
    unpaired_selected = abs(positive_count - negative_count)
    audit = {
        "schema_version": CORRECTION_SCHEMA_VERSION,
        "statistic_name": statistic,
        "statistic_role": (
            "primary" if statistic == PRIMARY_STATISTIC else "secondary_descriptive"
        ),
        "sweep": sweep,
        "matched_pair_count": positive_count,
        "positive_frame_count": positive_count,
        "negative_frame_count": negative_count,
        "unmatched_positive_count": 0,
        "duplicate_positive_key_count": duplicate_positive,
        "duplicate_clean_key_count": duplicate_clean,
        "invalid_pair_count": invalid_pair_count,
        "unpaired_selected_row_count": unpaired_selected,
        "excluded_unmatched_clean_count": len(finite_clean_keys - used_clean_keys),
        "analysis_population": ANALYSIS_POPULATION,
        "matching_key": MATCHING_KEY_DESCRIPTION,
        "correction_version": "v2",
    }
    if not selected or positive_count != negative_count:
        raise ValueError(f"Day 13 correction {sweep} population is incomplete")
    return {"rows": selected, "pairs": pair_records, "audit": audit}


def build_corrected_auroc_summary_v2(
    frame_scores: Sequence[Mapping[str, Any]],
) -> Tuple[Sequence[Mapping[str, Any]], Sequence[Mapping[str, Any]]]:
    output = []
    audits = []
    for statistic in ALL_STATISTICS:
        for sweep in ("geometry", "observation"):
            matched = build_matched_analysis_population(frame_scores, sweep, statistic)
            population = matched["rows"]
            audit = matched["audit"]
            bootstrap = block_bootstrap_auroc(
                population,
                repetitions=BOOTSTRAP_REPETITIONS,
                seed=BOOTSTRAP_SEED,
                block_field=BOOTSTRAP_BLOCK,
            )
            audits.append(audit)
            output.append({
                **{field: audit[field] for field in (
                    "schema_version", "statistic_name", "statistic_role", "sweep",
                    "matched_pair_count", "positive_frame_count",
                    "negative_frame_count", "unmatched_positive_count",
                    "duplicate_positive_key_count", "duplicate_clean_key_count",
                    "excluded_unmatched_clean_count",
                )},
                "auroc": bootstrap["point_estimate"],
                "bootstrap_median": bootstrap["bootstrap_median"],
                "ci95_lower": bootstrap["ci95_lower"],
                "ci95_upper": bootstrap["ci95_upper"],
                "valid_bootstrap_count": bootstrap["valid_bootstrap_count"],
                "invalid_bootstrap_count": bootstrap["invalid_bootstrap_count"],
                "analysis_population": ANALYSIS_POPULATION,
                "matching_key": MATCHING_KEY_DESCRIPTION,
                "correction_version": "v2",
            })
    return output, audits


def build_corrected_primary_roc_points_v2(
    frame_scores: Sequence[Mapping[str, Any]],
) -> Sequence[Mapping[str, Any]]:
    output = []
    for sweep in ("geometry", "observation"):
        matched = build_matched_analysis_population(
            frame_scores, sweep, PRIMARY_STATISTIC
        )
        rows = matched["rows"]
        scores = np.asarray([float(row["analysis_score"]) for row in rows])
        labels = np.asarray([int(row["analysis_label"]) for row in rows])
        positives = int(np.count_nonzero(labels == 1))
        negatives = int(np.count_nonzero(labels == 0))
        for threshold in sorted(set(scores.tolist()), reverse=True):
            predicted = scores > float(threshold)
            output.append({
                "schema_version": CORRECTION_SCHEMA_VERSION,
                "statistic_name": PRIMARY_STATISTIC,
                "sweep": sweep,
                "threshold": float(threshold),
                "comparison_operator": THRESHOLD_OPERATOR,
                "true_positive_rate": float(
                    np.count_nonzero(predicted & (labels == 1)) / positives
                ),
                "false_positive_rate": float(
                    np.count_nonzero(predicted & (labels == 0)) / negatives
                ),
                "positive_frame_count": positives,
                "negative_frame_count": negatives,
                "matched_pair_count": positives,
                "analysis_population": ANALYSIS_POPULATION,
                "correction_version": "v2",
            })
    return output


def build_locked_threshold_operating_points_v2(
    frame_scores: Sequence[Mapping[str, Any]],
    threshold: float = LOCKED_THRESHOLD,
) -> Sequence[Mapping[str, Any]]:
    if float(threshold) != LOCKED_THRESHOLD:
        raise ValueError("Day 13 correction threshold changed")
    output = []
    for sweep in ("geometry", "observation"):
        rows = build_matched_analysis_population(
            frame_scores, sweep, PRIMARY_STATISTIC
        )["rows"]
        positives = [row for row in rows if int(row["analysis_label"]) == 1]
        negatives = [row for row in rows if int(row["analysis_label"]) == 0]
        true_positive_count = sum(
            int(float(row["analysis_score"]) > threshold) for row in positives
        )
        false_positive_count = sum(
            int(float(row["analysis_score"]) > threshold) for row in negatives
        )
        output.append({
            "schema_version": CORRECTION_SCHEMA_VERSION,
            "statistic_name": PRIMARY_STATISTIC,
            "sweep": sweep,
            "matched_positive_count": len(positives),
            "matched_negative_count": len(negatives),
            "true_positive_count": true_positive_count,
            "false_positive_count": false_positive_count,
            "true_positive_rate": float(true_positive_count / len(positives)),
            "matched_clean_false_positive_rate": float(
                false_positive_count / len(negatives)
            ),
            "threshold": float(threshold),
            "operator": THRESHOLD_OPERATOR,
            "analysis_population": ANALYSIS_POPULATION,
            "correction_version": "v2",
        })
    return output


def build_fpr_breakdown_v2(
    calibration_scores: Sequence[Mapping[str, Any]],
    evaluation_scores: Sequence[Mapping[str, Any]],
    threshold: float = LOCKED_THRESHOLD,
    target: float = 0.10,
) -> Sequence[Mapping[str, Any]]:
    if float(threshold) != LOCKED_THRESHOLD:
        raise ValueError("Day 13 correction threshold changed")
    output = []
    for role, rows in (
        ("calibration", calibration_scores), ("evaluation", evaluation_scores)
    ):
        clean = [
            row for row in rows
            if str(row.get("role")) == role
            and str(row.get("stress")) == "clean"
            and primary_score_eligible(row)
        ]
        populations = {
            "clean_all": clean,
            "weak_clean": [
                row for row in clean
                if str(row.get("sweep")) in {"geometry", "observation"}
            ],
            "open_control": [
                row for row in clean if str(row.get("sweep")) == "open_control"
            ],
        }
        for name, values in populations.items():
            point = threshold_false_positive_rate(
                [float(row["primary_score"]) for row in values], threshold
            )
            output.append({
                "schema_version": CORRECTION_SCHEMA_VERSION,
                "role": role,
                "population": name,
                "eligible_frame_count": point["eligible_frame_count"],
                "false_positive_frame_count": point["false_positive_frame_count"],
                "fpr": point["fpr"],
                "threshold": float(threshold),
                "comparison_operator": THRESHOLD_OPERATOR,
                "target": float(target),
                "target_met": bool(float(point["fpr"]) <= float(target)),
                "correction_version": "v2",
            })
    return output


def build_gross_control_interpretation_v2(
    case_summaries: Sequence[Mapping[str, Any]],
) -> Sequence[Mapping[str, Any]]:
    groups: Dict[Tuple[str, str], List[Mapping[str, Any]]] = defaultdict(list)
    for row in case_summaries:
        if str(row.get("stress")) == "gross_outlier_control":
            groups[(str(row["sweep"]), str(row["level"]))].append(row)
    output = []
    for sweep, level in (
        ("geometry", "L3"), ("geometry", "L4"),
        ("observation", "O3"), ("observation", "O4"),
    ):
        rows = groups.get((sweep, level), [])
        if not rows:
            raise ValueError(f"Day 13 correction gross control missing {sweep}/{level}")
        downweighted = np.asarray([
            float(row["median_contaminated_huber_downweighted_ratio"])
            for row in rows
        ])
        subhuber = np.asarray([
            float(row["median_contaminated_subhuber_ratio"]) for row in rows
        ])
        outlier = np.asarray([
            float(row["median_huber_outlier_ratio"]) for row in rows
        ])
        if not (
            np.all(np.isfinite(downweighted))
            and np.all(np.isfinite(subhuber))
            and np.all(np.isfinite(outlier))
        ):
            raise ValueError("Day 13 correction gross control contains nonfinite data")
        zero_count = int(np.count_nonzero(downweighted == 0.0))
        output.append({
            "schema_version": CORRECTION_SCHEMA_VERSION,
            "sweep": sweep,
            "level": level,
            "gross_case_count": len(rows),
            "median_contaminated_huber_downweighted_ratio": float(
                np.median(downweighted)
            ),
            "zero_downweight_case_count": zero_count,
            "zero_downweight_case_ratio": float(zero_count / len(rows)),
            "median_contaminated_subhuber_ratio": float(np.median(subhuber)),
            "median_huber_outlier_ratio": float(np.median(outlier)),
            "interpretation": (
                "Huber downweighting is level-dependent; Geometry L4 is not stable"
            ),
            "correction_version": "v2",
        })
    return output


def run_day13_analysis_correction_v2(
    root: Path,
    source_run_dir: Path,
    output_dir: Path,
    overwrite: bool = False,
) -> Mapping[str, Any]:
    """Read frozen V1 tables and write only independent V2 analysis products."""

    root = Path(root).resolve()
    source = Path(source_run_dir).resolve()
    output = Path(output_dir).resolve()
    _validate_output_location(source, output)
    if not source.is_dir():
        raise FileNotFoundError(f"Day 13 V1 source run is missing: {source}")
    if output.exists():
        if not overwrite:
            raise FileExistsError(f"Day 13 correction output exists: {output}")
        shutil.rmtree(output)

    paths = _source_paths(source)
    before = {name: _sha256_file(path) for name, path in paths.items()}
    calibration_scores = read_v1_frame_scores(paths["calibration_frame_scores"])
    evaluation_scores = read_v1_frame_scores(paths["evaluation_frame_scores"])
    case_summaries = _read_case_summaries(paths["evaluation_case_summary"])
    calibration_lock = _read_json(paths["calibration_lock"])
    if float(calibration_lock.get("threshold_value", float("nan"))) != LOCKED_THRESHOLD:
        raise ValueError("Day 13 V1 locked threshold does not match the correction contract")
    if calibration_lock.get("primary_statistic") != PRIMARY_STATISTIC:
        raise ValueError("Day 13 V1 primary statistic changed")

    auroc_rows, audit_rows = build_corrected_auroc_summary_v2(evaluation_scores)
    roc_rows = build_corrected_primary_roc_points_v2(evaluation_scores)
    operating_rows = build_locked_threshold_operating_points_v2(evaluation_scores)
    fpr_rows = build_fpr_breakdown_v2(calibration_scores, evaluation_scores)
    gross_rows = build_gross_control_interpretation_v2(case_summaries)
    primary = {
        str(row["sweep"]): row for row in auroc_rows
        if row["statistic_name"] == PRIMARY_STATISTIC
    }
    primary_audits = {
        str(row["sweep"]): row for row in audit_rows
        if row["statistic_name"] == PRIMARY_STATISTIC
    }
    operating = {str(row["sweep"]): row for row in operating_rows}
    fpr = {(str(row["role"]), str(row["population"])): row for row in fpr_rows}
    gross = {(str(row["sweep"]), str(row["level"])): row for row in gross_rows}
    original = _read_original_primary_auroc(paths["v1_auroc_summary"])

    validate_fixed_rows(audit_rows, MATCHED_POPULATION_AUDIT_FIELDS, "population audit")
    validate_fixed_rows(auroc_rows, AUROC_SUMMARY_V2_FIELDS, "AUROC summary")
    validate_fixed_rows(roc_rows, PRIMARY_ROC_POINTS_V2_FIELDS, "ROC points")
    validate_fixed_rows(
        operating_rows, LOCKED_OPERATING_POINT_FIELDS, "operating points"
    )
    validate_fixed_rows(fpr_rows, FPR_BREAKDOWN_V2_FIELDS, "FPR breakdown")
    validate_fixed_rows(
        gross_rows, GROSS_CONTROL_INTERPRETATION_V2_FIELDS, "gross interpretation"
    )

    output.mkdir(parents=True, exist_ok=False)
    _write_fixed_csv(
        output / "matched_population_audit.csv", audit_rows,
        MATCHED_POPULATION_AUDIT_FIELDS,
    )
    _write_fixed_csv(output / "auroc_summary_v2.csv", auroc_rows, AUROC_SUMMARY_V2_FIELDS)
    _write_fixed_csv(
        output / "primary_roc_points_v2.csv", roc_rows, PRIMARY_ROC_POINTS_V2_FIELDS
    )
    _write_fixed_csv(
        output / "locked_threshold_operating_points_v2.csv", operating_rows,
        LOCKED_OPERATING_POINT_FIELDS,
    )
    _write_fixed_csv(output / "fpr_breakdown_v2.csv", fpr_rows, FPR_BREAKDOWN_V2_FIELDS)
    _write_fixed_csv(
        output / "gross_control_interpretation_v2.csv", gross_rows,
        GROSS_CONTROL_INTERPRETATION_V2_FIELDS,
    )

    after = {name: _sha256_file(path) for name, path in paths.items()}
    v1_raw_unchanged = all(before[name] == after[name] for name in (
        "calibration_frame_scores", "evaluation_frame_scores", "frames_merged",
    ))
    v1_outputs_unchanged = all(before[name] == after[name] for name in (
        "v1_auroc_summary", "v1_roc_points", "v1_fpr_summary",
        "v1_preliminary_summary", "v1_day13_summary",
    ))
    v1_locks_unchanged = all(before[name] == after[name] for name in (
        "design_lock", "calibration_lock",
    ))
    all_primary_audits_pass = all(
        int(row["unmatched_positive_count"]) == 0
        and int(row["duplicate_positive_key_count"]) == 0
        and int(row["duplicate_clean_key_count"]) == 0
        and int(row["invalid_pair_count"]) == 0
        and int(row["unpaired_selected_row_count"]) == 0
        for row in primary_audits.values()
    )
    bootstrap_pass = all(
        int(row["valid_bootstrap_count"]) == BOOTSTRAP_REPETITIONS
        and int(row["invalid_bootstrap_count"]) == 0
        for row in primary.values()
    )
    fpr_breakdown_pass = (
        len(fpr_rows) == 6
        and fpr[("evaluation", "clean_all")]["target_met"] is True
        and fpr[("evaluation", "weak_clean")]["target_met"] is False
        and fpr[("evaluation", "open_control")]["target_met"] is True
    )
    operating_pass = (
        len(operating_rows) == 2
        and all(int(row["matched_positive_count"]) > 0 for row in operating_rows)
    )
    gross_pass = (
        len(gross_rows) == 4
        and math.isclose(
            float(gross[("geometry", "L4")]["zero_downweight_case_ratio"]),
            0.625,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        )
    )
    preliminary = {
        "schema_version": CORRECTION_SCHEMA_VERSION,
        "primary_statistic": PRIMARY_STATISTIC,
        "locked_threshold": LOCKED_THRESHOLD,
        "threshold_operator": THRESHOLD_OPERATOR,
        "original_geometry_auroc": original["geometry"]["auroc"],
        "corrected_geometry_auroc": primary["geometry"]["auroc"],
        "original_observation_auroc": original["observation"]["auroc"],
        "corrected_observation_auroc": primary["observation"]["auroc"],
        "geometry_locked_threshold_tpr": operating["geometry"]["true_positive_rate"],
        "geometry_matched_clean_fpr": operating["geometry"][
            "matched_clean_false_positive_rate"
        ],
        "observation_locked_threshold_tpr": operating["observation"][
            "true_positive_rate"
        ],
        "observation_matched_clean_fpr": operating["observation"][
            "matched_clean_false_positive_rate"
        ],
        "combined_clean_fpr_target_met": fpr[("evaluation", "clean_all")][
            "target_met"
        ],
        "weak_clean_fpr_target_met": fpr[("evaluation", "weak_clean")][
            "target_met"
        ],
        "open_control_fpr_target_met": fpr[("evaluation", "open_control")][
            "target_met"
        ],
        "clean_fpr_target_status": "MIXED_POPULATION_DEPENDENT",
        "stage2_target_auroc": 0.80,
        "geometry_auroc_target_met": float(primary["geometry"]["auroc"]) >= 0.80,
        "observation_auroc_target_met": float(primary["observation"]["auroc"]) >= 0.80,
        "locked_operating_point_interpretation": (
            "At roughly 8%-9% matched-clean FPR, only about 14.6%-22.3% of "
            "coherent active frames are detected."
        ),
        "gross_control_interpretation": (
            "Huber downweights as expected in most configurations, but Geometry "
            "L4 is not stable; gross-control behavior is level-dependent."
        ),
        "preliminary_only": True,
        "stage2_final_decision_made": False,
        "stage3_detection_threshold_created": False,
    }
    _write_json(output / "preliminary_criteria_summary_v2.json", preliminary)

    source_manifest = _read_json(paths["run_manifest"])
    manifest: Dict[str, Any] = {
        "schema_version": CORRECTION_SCHEMA_VERSION,
        "correction_id": CORRECTION_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_run_id": source.name,
        "source_run_dir": _display_path(root, source),
        "source_v1_git_commit": str(source_manifest["git_commit"]),
        "current_git_commit": _git_commit(root),
        "correction_reason": (
            "V1 used all eligible clean rows instead of one-to-one matched clean rows"
        ),
        "original_population_rule": str(
            _read_json(paths["design_lock"])["negative_population_rule"]
        ),
        "incorrect_v1_implementation": (
            "all eligible clean rows in the same sweep were selected as AUROC negatives"
        ),
        "corrected_population_rule": (
            "one unique clean row per coherent active row with identical frozen key "
            "and timestamp"
        ),
        "matching_key_fields": list(MATCH_KEY_FIELDS),
        "source_design_lock_path": _display_path(root, paths["design_lock"]),
        "source_design_lock_sha256": before["design_lock"],
        "source_calibration_lock_path": _display_path(root, paths["calibration_lock"]),
        "source_calibration_lock_sha256": before["calibration_lock"],
        "source_calibration_frame_scores_sha256_before": before[
            "calibration_frame_scores"
        ],
        "source_calibration_frame_scores_sha256_after": after[
            "calibration_frame_scores"
        ],
        "source_evaluation_frame_scores_sha256_before": before[
            "evaluation_frame_scores"
        ],
        "source_evaluation_frame_scores_sha256_after": after[
            "evaluation_frame_scores"
        ],
        "source_frames_merged_sha256_before": before["frames_merged"],
        "source_frames_merged_sha256_after": after["frames_merged"],
        "source_v1_auroc_summary_sha256": before["v1_auroc_summary"],
        "source_v1_roc_points_sha256": before["v1_roc_points"],
        "source_v1_fpr_summary_sha256": before["v1_fpr_summary"],
        "source_v1_summary_sha256": before["v1_day13_summary"],
        "source_v1_auroc_summary_sha256_after": after["v1_auroc_summary"],
        "source_v1_roc_points_sha256_after": after["v1_roc_points"],
        "source_v1_fpr_summary_sha256_after": after["v1_fpr_summary"],
        "source_v1_preliminary_summary_sha256": before["v1_preliminary_summary"],
        "source_v1_preliminary_summary_sha256_after": after[
            "v1_preliminary_summary"
        ],
        "source_v1_summary_sha256_after": after["v1_day13_summary"],
        "original_geometry_positive_count": original["geometry"][
            "positive_frame_count"
        ],
        "original_geometry_negative_count": original["geometry"][
            "negative_frame_count"
        ],
        "corrected_geometry_positive_count": primary["geometry"][
            "positive_frame_count"
        ],
        "corrected_geometry_negative_count": primary["geometry"][
            "negative_frame_count"
        ],
        "original_observation_positive_count": original["observation"][
            "positive_frame_count"
        ],
        "original_observation_negative_count": original["observation"][
            "negative_frame_count"
        ],
        "corrected_observation_positive_count": primary["observation"][
            "positive_frame_count"
        ],
        "corrected_observation_negative_count": primary["observation"][
            "negative_frame_count"
        ],
        "original_geometry_auroc": original["geometry"]["auroc"],
        "corrected_geometry_auroc": primary["geometry"]["auroc"],
        "corrected_geometry_ci95_lower": primary["geometry"]["ci95_lower"],
        "corrected_geometry_ci95_upper": primary["geometry"]["ci95_upper"],
        "original_observation_auroc": original["observation"]["auroc"],
        "corrected_observation_auroc": primary["observation"]["auroc"],
        "corrected_observation_ci95_lower": primary["observation"]["ci95_lower"],
        "corrected_observation_ci95_upper": primary["observation"]["ci95_upper"],
        "locked_threshold": LOCKED_THRESHOLD,
        "threshold_unchanged": True,
        "calibration_trial_rerun": False,
        "evaluation_trial_rerun": False,
        "estimator_invoked": False,
        "seed_changed": False,
        "stress_changed": False,
        "statistic_changed": False,
        "threshold_changed": False,
        "retuning_performed": False,
        "geometry_missing_match_count": primary_audits["geometry"][
            "unmatched_positive_count"
        ],
        "observation_missing_match_count": primary_audits["observation"][
            "unmatched_positive_count"
        ],
        "duplicate_positive_key_count": sum(
            int(row["duplicate_positive_key_count"])
            for row in primary_audits.values()
        ),
        "duplicate_clean_key_count": sum(
            int(row["duplicate_clean_key_count"]) for row in primary_audits.values()
        ),
        "invalid_pair_count": sum(
            int(row["invalid_pair_count"]) for row in primary_audits.values()
        ),
        "unpaired_selected_row_count": sum(
            int(row["unpaired_selected_row_count"]) for row in primary_audits.values()
        ),
        "geometry_excluded_unmatched_clean_count": primary_audits["geometry"][
            "excluded_unmatched_clean_count"
        ],
        "observation_excluded_unmatched_clean_count": primary_audits[
            "observation"
        ]["excluded_unmatched_clean_count"],
        "primary_geometry_valid_bootstrap_count": primary["geometry"][
            "valid_bootstrap_count"
        ],
        "primary_geometry_invalid_bootstrap_count": primary["geometry"][
            "invalid_bootstrap_count"
        ],
        "primary_observation_valid_bootstrap_count": primary["observation"][
            "valid_bootstrap_count"
        ],
        "primary_observation_invalid_bootstrap_count": primary["observation"][
            "invalid_bootstrap_count"
        ],
        "geometry_locked_threshold_tpr": operating["geometry"][
            "true_positive_rate"
        ],
        "geometry_matched_clean_fpr": operating["geometry"][
            "matched_clean_false_positive_rate"
        ],
        "observation_locked_threshold_tpr": operating["observation"][
            "true_positive_rate"
        ],
        "observation_matched_clean_fpr": operating["observation"][
            "matched_clean_false_positive_rate"
        ],
        "combined_clean_fpr_target_met": fpr[("evaluation", "clean_all")][
            "target_met"
        ],
        "weak_clean_fpr_target_met": fpr[("evaluation", "weak_clean")][
            "target_met"
        ],
        "open_control_fpr_target_met": fpr[("evaluation", "open_control")][
            "target_met"
        ],
        "clean_fpr_target_status": "MIXED_POPULATION_DEPENDENT",
        "geometry_l4_zero_downweight_case_ratio": gross[("geometry", "L4")][
            "zero_downweight_case_ratio"
        ],
        "v1_locked_files_unchanged": v1_locks_unchanged,
        "v1_raw_inputs_unchanged": v1_raw_unchanged,
        "v1_analysis_outputs_unchanged": v1_outputs_unchanged,
        "matched_population_audit_pass": all_primary_audits_pass,
        "input_immutability_pass": (
            v1_locks_unchanged and v1_raw_unchanged and v1_outputs_unchanged
        ),
        "bootstrap_pass": bootstrap_pass,
        "fpr_breakdown_pass": fpr_breakdown_pass,
        "operating_point_pass": operating_pass,
        "gross_control_reporting_pass": gross_pass,
        "output_schema_pass": False,
        "DAY13_CORRECTION_ENGINEERING_PASS": False,
        "DAY13_CORRECTION_PROTOCOL_PASS": False,
        "DAY13_CORRECTION_PASS": False,
        "DAY14_STAGE2_DECISION_AUTHORIZED": False,
        "STAGE2_GATE": "INCOMPLETE",
        "STAGE3_GATE": "NOT_STARTED",
        "COHERENT_BIAS_DETECTABLE": "UNDETERMINED",
        "RISK_WARNING_AUTHORIZED": False,
        "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
        "PUBLIC_DISCLOSURE_AUTHORIZED": False,
    }
    _write_json(output / "analysis_correction_manifest.json", manifest)
    _write_json(output / "day13_correction_summary.json", _summary_from_manifest(manifest))
    validate_output_directory(output)

    manifest["output_schema_pass"] = True
    engineering = all((
        all_primary_audits_pass, bootstrap_pass, fpr_breakdown_pass,
        operating_pass, gross_pass, manifest["output_schema_pass"],
    ))
    protocol = all((
        v1_locks_unchanged, v1_raw_unchanged, v1_outputs_unchanged,
        manifest["threshold_unchanged"], not manifest["calibration_trial_rerun"],
        not manifest["evaluation_trial_rerun"], not manifest["estimator_invoked"],
        not manifest["seed_changed"], not manifest["stress_changed"],
        not manifest["statistic_changed"], not manifest["threshold_changed"],
        not manifest["retuning_performed"],
    ))
    manifest["DAY13_CORRECTION_ENGINEERING_PASS"] = engineering
    manifest["DAY13_CORRECTION_PROTOCOL_PASS"] = protocol
    manifest["DAY13_CORRECTION_PASS"] = bool(engineering and protocol)
    manifest["DAY14_STAGE2_DECISION_AUTHORIZED"] = bool(
        manifest["DAY13_CORRECTION_PASS"]
    )
    if manifest["DAY13_CORRECTION_PASS"] != evaluate_correction_gate(manifest):
        raise RuntimeError("Day 13 correction Gate is internally inconsistent")
    validate_correction_manifest(manifest)
    _write_json(output / "analysis_correction_manifest.json", manifest)
    summary = _summary_from_manifest(manifest)
    _write_json(output / "day13_correction_summary.json", summary)
    validate_output_directory(output)
    if not evaluate_correction_gate(manifest):
        raise RuntimeError("Day 13 correction Gate did not pass")
    return {"manifest": manifest, "summary": summary, "output_dir": str(output)}


def read_v1_frame_scores(path: Path) -> Sequence[Mapping[str, Any]]:
    bool_fields = {
        "stress_active", "stat_input_valid", "window_ready",
        "primary_score_eligible", "offline_evaluation_only",
    }
    int_fields = {
        "geometry_seed", "sensor_seed", "process_seed", "frame_index",
        "binary_label", "huber_current_same_sign_run_length",
    }
    float_fields = {
        "timestamp", "primary_score", "abs_weak_innovation_z_huber",
        "abs_huber_window_mean", "huber_window_energy",
        "huber_dominant_sign_ratio", "abs_huber_lag1_autocorrelation",
        "abs_huber_skewness",
    }
    output = []
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != tuple(FRAME_SCORE_FIELDS):
            raise ValueError("Day 13 V1 frame-score schema changed")
        for raw in reader:
            row: Dict[str, Any] = dict(raw)
            for field in bool_fields:
                row[field] = _parse_bool(row[field])
            for field in int_fields:
                row[field] = int(row[field])
            for field in float_fields:
                row[field] = float(row[field])
            output.append(row)
    return output


def _source_paths(source: Path) -> Mapping[str, Path]:
    paths = {
        "calibration_frame_scores": source / "calibration/frame_scores.csv",
        "evaluation_frame_scores": source / "evaluation/frame_scores.csv",
        "frames_merged": source / "evaluation/frames_merged.csv",
        "evaluation_case_summary": source / "evaluation/case_summary.csv",
        "v1_auroc_summary": source / "evaluation/auroc_summary.csv",
        "v1_roc_points": source / "evaluation/primary_roc_points.csv",
        "v1_fpr_summary": source / "evaluation/fpr_summary.csv",
        "v1_preliminary_summary": source / "evaluation/preliminary_criteria_summary.json",
        "v1_day13_summary": source / "day13_summary.json",
        "design_lock": source / "design/design_lock.json",
        "calibration_lock": source / "calibration/calibration_threshold_lock.json",
        "run_manifest": source / "run_manifest.json",
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("Day 13 correction source files missing: " + ", ".join(missing))
    return paths


def _read_case_summaries(path: Path) -> Sequence[Mapping[str, Any]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for field in (
            "median_contaminated_huber_downweighted_ratio",
            "median_contaminated_subhuber_ratio", "median_huber_outlier_ratio",
        ):
            row[field] = float(row[field])
    return rows


def _read_original_primary_auroc(path: Path) -> Mapping[str, Mapping[str, Any]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    output = {}
    for row in rows:
        if row.get("statistic_name") == PRIMARY_STATISTIC:
            output[str(row["sweep"])] = {
                "positive_frame_count": int(row["positive_frame_count"]),
                "negative_frame_count": int(row["negative_frame_count"]),
                "auroc": float(row["auroc"]),
            }
    if set(output) != {"geometry", "observation"}:
        raise ValueError("Day 13 V1 primary AUROC rows are incomplete")
    return output


def _summary_from_manifest(manifest: Mapping[str, Any]) -> Mapping[str, Any]:
    fields = (
        "DAY13_CORRECTION_ENGINEERING_PASS", "DAY13_CORRECTION_PROTOCOL_PASS",
        "DAY13_CORRECTION_PASS", "DAY14_STAGE2_DECISION_AUTHORIZED",
        "STAGE2_GATE", "STAGE3_GATE", "COHERENT_BIAS_DETECTABLE",
        "RISK_WARNING_AUTHORIZED", "FAST_LIO2_INTEGRATION_AUTHORIZED",
        "PUBLIC_DISCLOSURE_AUTHORIZED", "corrected_geometry_positive_count",
        "corrected_geometry_negative_count", "corrected_observation_positive_count",
        "corrected_observation_negative_count", "corrected_geometry_auroc",
        "corrected_geometry_ci95_lower", "corrected_geometry_ci95_upper",
        "corrected_observation_auroc", "corrected_observation_ci95_lower",
        "corrected_observation_ci95_upper", "geometry_locked_threshold_tpr",
        "geometry_matched_clean_fpr", "observation_locked_threshold_tpr",
        "observation_matched_clean_fpr", "clean_fpr_target_status",
    )
    return {
        "schema_version": CORRECTION_SCHEMA_VERSION,
        **{field: manifest[field] for field in fields},
        "preliminary_only": True,
        "stage2_final_decision_made": False,
    }


def _match_key(row: Mapping[str, Any]) -> Tuple[Any, ...]:
    return tuple(row[field] for field in MATCH_KEY_FIELDS)


def _pair_id(row: Mapping[str, Any]) -> str:
    values = [row[field] for field in MATCH_KEY_FIELDS] + [float(row["timestamp"])]
    payload = json.dumps(values, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_bool(value: Any) -> bool:
    if type(value) is bool:
        return value
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise ValueError(f"invalid boolean: {value}")


def _validate_output_location(source: Path, output: Path) -> None:
    if source == output or source in output.parents:
        raise ValueError("Day 13 correction output cannot equal or be inside V1 source")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_fixed_csv(
    path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON mapping: {path}")
    return value


def _git_commit(root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(root), check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    ).stdout.strip()


def _display_path(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
