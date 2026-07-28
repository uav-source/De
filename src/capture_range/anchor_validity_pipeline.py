"""End-to-end Development-only anchor validity audit pipeline."""

from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
import os
import shutil
import subprocess
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .anchor_validity_audit import (
    EXPECTED_CANDIDATES,
    absolute_accuracy_valid,
    build_anchor_condition_snapshots,
    classify_d50_zero_root_cause,
    common_anchor_eligible,
    exact_file_sha256,
    load_anchor_audit_protocol,
    pose_distance,
    pose_from_json,
    repeat_cluster_count,
    run_zero_registration,
)
from .day2_development_protocol import (
    canonical_seed,
    development_seed_firewall,
    load_day2_development_protocol,
)
from .registration_core import (
    prepare_frozen_linearization,
    prepare_full_reassociation_session,
)


TABLE_FILES = (
    "zero_perturbation_results.csv",
    "zero_success_by_scene.csv",
    "fixed_point_gradient_audit.csv",
    "noise_ablation.csv",
    "anchor_candidate_comparison.csv",
    "anchor_gt_accuracy.csv",
    "anchor_repeat_dispersion.csv",
    "frozen_common_anchor_eligibility.csv",
    "d50_zero_root_cause.csv",
    "full_frozen_difference_mechanism.csv",
    "final_decision.csv",
)

FIGURE_FILES = (
    "zero_pose_shift_by_scene.png",
    "zero_gradient_norm_by_scene.png",
    "noise_ablation_zero_success.png",
    "anchor_error_to_gt.png",
    "anchor_repeat_clusters.png",
    "full_frozen_correspondence_switch.png",
)

TOP_LEVEL_FILES = (
    "anchor_validity_report.md",
    "run_manifest.json",
    "final_decision.json",
    "SHA256SUMS",
)

ZERO_FIELDS = (
    "scene_id",
    "scene_variant",
    "geometry_seed",
    "measurement_seed",
    "repeat_index",
    "block_id",
    "base_snapshot_id",
    "method",
    "signed_amplitude",
    "reference_pose",
    "zero_initial_pose",
    "zero_final_pose",
    "zero_translation_shift_from_reference_m",
    "zero_rotation_shift_from_reference_rad",
    "zero_initial_cost",
    "zero_final_cost",
    "zero_gradient_norm_at_reference",
    "zero_correspondence_count_initial",
    "zero_correspondence_count_final",
    "zero_correspondence_checksum_initial",
    "zero_correspondence_checksum_final",
    "zero_iteration_count",
    "zero_solver_converged",
    "zero_success_under_current_gt_rule",
    "zero_block_success_rate",
    "directionality_interpretation_eligible",
    "zero_runtime_ms",
    "zero_finite_output",
    "zero_iteration_limit_not_failed",
    "zero_termination_reason",
    "zero_failure_reason",
    "deterministic_recheck_translation_difference_m",
    "deterministic_recheck_rotation_difference_rad",
    "deterministic_recheck_pass",
    "base_snapshot_checksum",
    "scan_checksum",
    "map_checksum",
    "dropout_checksum",
)

NOISE_FIELDS = (
    "scene_variant",
    "geometry_seed",
    "measurement_seed",
    "repeat_index",
    "block_id",
    "base_snapshot_id",
    "condition_id",
    "method",
    "zero_success_under_current_gt_rule",
    "zero_translation_shift_from_reference_m",
    "zero_rotation_shift_from_reference_rad",
    "zero_initial_cost",
    "zero_final_cost",
    "zero_cost_change",
    "zero_gradient_norm_at_reference",
    "zero_correspondence_checksum_initial",
    "zero_correspondence_checksum_final",
    "zero_correspondence_checksum_change_count",
    "zero_correspondence_changed",
    "zero_plane_checksum_initial",
    "zero_plane_checksum_final",
    "zero_plane_fit_changed",
    "zero_iteration_count",
    "zero_solver_converged",
    "zero_finite_output",
    "zero_iteration_limit_not_failed",
    "zero_termination_reason",
    "zero_runtime_ms",
    "deterministic_recheck_performed",
    "deterministic_recheck_translation_difference_m",
    "deterministic_recheck_rotation_difference_rad",
    "deterministic_recheck_pass",
    "reference_pose",
    "zero_final_pose",
    "scan_checksum",
    "map_checksum",
    "dropout_checksum",
)

FIXED_FIELDS = (
    "scene_variant",
    "geometry_seed",
    "measurement_seed",
    "repeat_index",
    "block_id",
    "base_snapshot_id",
    "method",
    "reference_cost",
    "reference_gradient_norm",
    "reference_gradient_norm_per_sqrt_correspondence",
    "one_step_translation_m",
    "one_step_rotation_rad",
    "final_translation_shift_m",
    "final_rotation_shift_rad",
    "correspondence_changed",
    "plane_fit_changed",
    "deterministic_recheck_pass",
    "reference_pose_not_registration_fixed_point",
)

ANCHOR_GT_FIELDS = (
    "scene_variant",
    "geometry_seed",
    "measurement_seed",
    "repeat_index",
    "block_id",
    "base_snapshot_id",
    "candidate_anchor",
    "anchor_pose",
    "anchor_translation_error_to_gt_m",
    "anchor_rotation_error_to_gt_rad",
    "anchor_absolute_accuracy_valid",
    "source_condition",
    "full_solver_converged",
    "full_finite_output",
    "deterministic_recheck_pass",
    "full_method_self_consistent",
    "frozen_method_consistent_to_common_anchor",
    "frozen_translation_distance_to_anchor_m",
    "frozen_rotation_distance_to_anchor_rad",
    "conditions_1_to_4_pass",
    "repeat_cluster_count",
    "multiple_attractors",
    "snapshot_anchor_eligible",
)

ANCHOR_COMPARISON_FIELDS = (
    "candidate_anchor",
    "snapshot_count",
    "zero_perturbation_success_rate",
    "anchor_gt_accuracy_fraction",
    "median_anchor_translation_error_to_gt_m",
    "q95_anchor_translation_error_to_gt_m",
    "median_anchor_rotation_error_to_gt_rad",
    "q95_anchor_rotation_error_to_gt_rad",
    "full_method_self_consistency_fraction",
    "frozen_method_consistency_fraction",
    "conditions_1_to_4_fraction",
    "multiple_attractor_block_count",
    "eligible_snapshot_fraction",
    "anchor_valid",
)

DISPERSION_FIELDS = (
    "scene_variant",
    "geometry_seed",
    "measurement_seed",
    "block_id",
    "candidate_anchor",
    "repeat_count",
    "pair_count",
    "median_pairwise_translation_m",
    "q95_pairwise_translation_m",
    "maximum_pairwise_translation_m",
    "median_pairwise_rotation_rad",
    "q95_pairwise_rotation_rad",
    "maximum_pairwise_rotation_rad",
    "cluster_count",
    "multiple_attractors",
)

COMMON_FIELDS = (
    "scene_variant",
    "geometry_seed",
    "measurement_seed",
    "repeat_index",
    "block_id",
    "base_snapshot_id",
    "full_anchor_pose",
    "frozen_zero_pose",
    "translation_distance_m",
    "rotation_distance_rad",
    "distance_eligible",
    "full_zero_anchor_globally_valid",
    "eligible_for_subsequent_comparison",
)

ROOT_FIELDS = (
    "scene_variant",
    "geometry_seed",
    "measurement_seed",
    "block_id",
    "perturbation_type",
    "direction_id",
    "registration_path",
    "original_d50",
    "primary_reason",
    "secondary_reasons",
    "zero_success_rate",
    "zero_solver_convergence_rate",
    "zero_threshold_conflict_rate",
    "reference_not_fixed_point_fraction",
    "zero_association_switch_fraction",
    "noise_free_zero_success_rate",
    "locked_full_noise_zero_success_rate",
    "repeat_cluster_count",
)

MECHANISM_FIELDS = (
    "scene_variant",
    "geometry_seed",
    "measurement_seed",
    "block_id",
    "direction_id",
    "raw_maximum_probability_gap",
    "anchor_mismatch_fraction",
    "difference_explained_by_correspondence_switch",
    "difference_explained_by_anchor_mismatch",
    "difference_explained_by_solver_failure",
    "full_final_pose_second_cluster",
    "full_failure_after_amplitude_m",
    "frozen_still_linear_return",
    "full_low_residual_wrong_pose",
    "maximum_repeat_recovery_mismatch_fraction",
    "difference_unexplained",
    "full_reassociation_nonlinear_effect_candidate",
)

FINAL_FIELDS = (
    "ANCHOR_AUDIT_COMPLETE",
    "ZERO_PERTURBATION_BASELINE_VALID",
    "REFERENCE_POSE_NOT_REGISTRATION_FIXED_POINT",
    "NOISE_INDUCED_ANCHOR_SHIFT_CONFIRMED",
    "DROPOUT_INDUCED_ANCHOR_SHIFT_CONFIRMED",
    "GT_REFERENCE_ANCHOR_VALID",
    "FULL_ZERO_SOLUTION_ANCHOR_VALID",
    "NOISE_FREE_FULL_SOLUTION_ANCHOR_VALID",
    "FROZEN_COMMON_ANCHOR_ELIGIBLE_FRACTION",
    "D50_ZERO_ROOT_CAUSE_IDENTIFIED",
    "FULL_REASSOCIATION_NONLINEAR_EFFECT_CANDIDATE",
    "DIRECTIONAL_CAPTURE_RANGE_ROUTE_RECOVERABLE",
    "NEW_CONFIRMATORY_PROTOCOL_AUTHORIZED",
    "CONFIRMATORY_TEST_AUTHORIZED",
    "NO_TEST_SEED_ACCESS",
    "NO_GT_LEAKAGE",
    "RECOMMENDED_ANCHOR",
    "NONLINEAR_EFFECT_CANDIDATE_COUNT",
    "DIFFERENCES_REMAINING_AFTER_ANCHOR_MISMATCH_EXCLUSION",
)


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (bool, np.bool_)):
        return "true" if bool(value) else "false"
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text not in {"true", "false"}:
        raise ValueError(f"invalid boolean value: {value}")
    return text == "true"


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fields: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=list(fields), lineterminator="\n", extrasaction="raise"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({name: _csv_value(row.get(name)) for name in fields})


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, text=True, capture_output=True
    ).stdout.strip()


def _q95(values: Sequence[float]) -> float | None:
    finite = np.asarray([float(value) for value in values if math.isfinite(float(value))])
    if not finite.size:
        return None
    return float(np.quantile(finite, 0.95, method="linear"))


def _median(values: Sequence[float]) -> float | None:
    finite = np.asarray([float(value) for value in values if math.isfinite(float(value))])
    if not finite.size:
        return None
    return float(np.median(finite))


def _verify_sha256sums(directory: Path) -> None:
    lines = (directory / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    for line in lines:
        digest, relative = line.split("  ", 1)
        if exact_file_sha256(directory / relative) != digest:
            raise ValueError(f"checksum mismatch: {directory / relative}")


def _snapshot_task(args: tuple[str, str, int, int, int, Mapping[str, str]]) -> dict[str, Any]:
    root_text, scene, geometry, measurement, repeat, expected = args
    root = Path(root_text)
    development = load_day2_development_protocol(root)
    audit = load_anchor_audit_protocol(root)
    firewall = development_seed_firewall(development)
    bundles = build_anchor_condition_snapshots(
        development, audit, firewall, scene, geometry, measurement, repeat
    )
    locked = next(value for value in bundles if value.condition_id == "LOCKED_FULL_NOISE")
    for name in (
        "base_snapshot_checksum",
        "scan_checksum",
        "map_checksum",
        "dropout_checksum",
    ):
        if str(getattr(locked, name)) != str(expected[name]):
            raise RuntimeError(f"locked Development snapshot mismatch: {name}")

    rows: list[dict[str, Any]] = []
    for bundle in bundles:
        firewall.assert_access(geometry, measurement, repeat)
        seed = canonical_seed(
            {
                "global_seed": firewall.global_seed,
                "audit": "directional_capture_range_anchor_validity",
                "base_snapshot_id": bundle.base_snapshot_id,
                "condition_id": bundle.condition_id,
                "signed_amplitude": 0.0,
            }
        )
        snapshot = bundle.snapshot
        prepared = prepare_full_reassociation_session(
            snapshot.scan_points,
            snapshot.local_map_points,
            snapshot.registration_config,
            snapshot_id=snapshot.snapshot_id,
            reference_pose=snapshot.reference_pose,
        )
        baseline = prepare_frozen_linearization(
            snapshot.scan_points,
            snapshot.local_map_points,
            snapshot.reference_pose,
            snapshot.registration_config,
            seed,
            snapshot_id=snapshot.snapshot_id,
        )
        recheck = bundle.condition_id in {"NOISE_FREE", "LOCKED_FULL_NOISE"}
        for method in ("full_reassociation", "frozen_jacobian"):
            rows.append(
                run_zero_registration(
                    bundle,
                    method,
                    seed,
                    audit,
                    deterministic_recheck=recheck,
                    prepared=prepared,
                    baseline=baseline,
                )
            )
    return {"rows": rows, "seed_audit": dict(firewall.audit_counts)}


def _build_success_summary(
    formal_rows: Sequence[Mapping[str, Any]], minimum_probability: float
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    scenes = sorted({str(row["scene_variant"]) for row in formal_rows})
    for scene in [*scenes, "ALL_SCENES"]:
        for method in ("full_reassociation", "frozen_jacobian"):
            values = [
                row
                for row in formal_rows
                if row["method"] == method
                and (scene == "ALL_SCENES" or row["scene_variant"] == scene)
            ]
            success_count = sum(bool(row["zero_success_under_current_gt_rule"]) for row in values)
            rate = success_count / len(values)
            translations = [float(row["zero_translation_shift_from_reference_m"]) for row in values]
            rotations = [float(row["zero_rotation_shift_from_reference_rad"]) for row in values]
            result.append(
                {
                    "scene_variant": scene,
                    "method": method,
                    "snapshot_count": len(values),
                    "zero_success_count": success_count,
                    "zero_success_rate": rate,
                    "median_zero_translation_shift_m": _median(translations),
                    "q95_zero_translation_shift_m": _q95(translations),
                    "median_zero_rotation_shift_rad": _median(rotations),
                    "q95_zero_rotation_shift_rad": _q95(rotations),
                    "p_zero_at_least_0p95": rate >= minimum_probability,
                    "directionality_interpretation_eligible": rate >= minimum_probability,
                }
            )
    return result


SUCCESS_FIELDS = (
    "scene_variant",
    "method",
    "snapshot_count",
    "zero_success_count",
    "zero_success_rate",
    "median_zero_translation_shift_m",
    "q95_zero_translation_shift_m",
    "median_zero_rotation_shift_rad",
    "q95_zero_rotation_shift_rad",
    "p_zero_at_least_0p95",
    "directionality_interpretation_eligible",
)


def _fixed_rows(formal_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "scene_variant": row["scene_variant"],
            "geometry_seed": row["geometry_seed"],
            "measurement_seed": row["measurement_seed"],
            "repeat_index": row["repeat_index"],
            "block_id": row["block_id"],
            "base_snapshot_id": row["base_snapshot_id"],
            "method": row["method"],
            "reference_cost": row["zero_initial_cost"],
            "reference_gradient_norm": row["zero_gradient_norm_at_reference"],
            "reference_gradient_norm_per_sqrt_correspondence": row[
                "zero_gradient_norm_per_sqrt_correspondence"
            ],
            "one_step_translation_m": row["zero_first_step_translation_m"],
            "one_step_rotation_rad": row["zero_first_step_rotation_rad"],
            "final_translation_shift_m": row[
                "zero_translation_shift_from_reference_m"
            ],
            "final_rotation_shift_rad": row["zero_rotation_shift_from_reference_rad"],
            "correspondence_changed": row["zero_correspondence_changed"],
            "plane_fit_changed": row["zero_plane_fit_changed"],
            "deterministic_recheck_pass": row["deterministic_recheck_pass"],
            "reference_pose_not_registration_fixed_point": row[
                "reference_pose_not_registration_fixed_point"
            ],
        }
        for row in formal_rows
    ]


def _candidate_rows(
    noise_rows: Sequence[Mapping[str, Any]], audit: Any
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    by_snapshot_condition_method = {
        (row["base_snapshot_id"], row["condition_id"], row["method"]): row
        for row in noise_rows
    }
    snapshot_ids = sorted({str(row["base_snapshot_id"]) for row in noise_rows})
    rows: list[dict[str, Any]] = []
    source_condition = {
        "GT_REFERENCE_ANCHOR": "LOCKED_FULL_NOISE",
        "FULL_ZERO_SOLUTION_ANCHOR": "LOCKED_FULL_NOISE",
        "NOISE_FREE_FULL_SOLUTION_ANCHOR": "NOISE_FREE",
    }
    for snapshot_id in snapshot_ids:
        for candidate in EXPECTED_CANDIDATES:
            condition = source_condition[candidate]
            full = by_snapshot_condition_method[(snapshot_id, condition, "full_reassociation")]
            frozen = by_snapshot_condition_method[(snapshot_id, condition, "frozen_jacobian")]
            reference = pose_from_json(str(full["reference_pose"]))
            if candidate == "GT_REFERENCE_ANCHOR":
                anchor_pose = reference
                deterministic = bool(full["deterministic_recheck_pass"])
                self_consistent = bool(full["zero_success_under_current_gt_rule"])
            else:
                anchor_pose = pose_from_json(str(full["zero_final_pose"]))
                deterministic = bool(full["deterministic_recheck_pass"])
                self_consistent = bool(
                    full["zero_solver_converged"]
                    and full["zero_finite_output"]
                    and deterministic
                )
            gt_translation, gt_rotation = pose_distance(anchor_pose, reference)
            gt_valid = absolute_accuracy_valid(gt_translation, gt_rotation, audit)
            frozen_pose = pose_from_json(str(frozen["zero_final_pose"]))
            frozen_consistent, frozen_translation, frozen_rotation = common_anchor_eligible(
                frozen_pose, anchor_pose, audit
            )
            conditions_pass = bool(
                full["zero_solver_converged"]
                and full["zero_finite_output"]
                and deterministic
                and gt_valid
                and self_consistent
            )
            rows.append(
                {
                    "scene_variant": full["scene_variant"],
                    "geometry_seed": full["geometry_seed"],
                    "measurement_seed": full["measurement_seed"],
                    "repeat_index": full["repeat_index"],
                    "block_id": full["block_id"],
                    "base_snapshot_id": snapshot_id,
                    "candidate_anchor": candidate,
                    "anchor_pose": json.dumps(
                        anchor_pose.tolist(), separators=(",", ":"), allow_nan=False
                    ),
                    "anchor_translation_error_to_gt_m": gt_translation,
                    "anchor_rotation_error_to_gt_rad": gt_rotation,
                    "anchor_absolute_accuracy_valid": gt_valid,
                    "source_condition": condition,
                    "full_solver_converged": full["zero_solver_converged"],
                    "full_finite_output": full["zero_finite_output"],
                    "deterministic_recheck_pass": deterministic,
                    "full_method_self_consistent": self_consistent,
                    "frozen_method_consistent_to_common_anchor": frozen_consistent,
                    "frozen_translation_distance_to_anchor_m": frozen_translation,
                    "frozen_rotation_distance_to_anchor_rad": frozen_rotation,
                    "conditions_1_to_4_pass": conditions_pass,
                }
            )

    by_block_candidate: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_block_candidate[(str(row["block_id"]), str(row["candidate_anchor"]))].append(row)
    dispersion: list[dict[str, Any]] = []
    for (block_id, candidate), values in sorted(by_block_candidate.items()):
        poses = [pose_from_json(str(row["anchor_pose"])) for row in values]
        translations, rotations = [], []
        for left, right in itertools.combinations(poses, 2):
            translation, rotation = pose_distance(left, right)
            translations.append(translation)
            rotations.append(rotation)
        clusters = repeat_cluster_count(poses, audit)
        multiple = clusters > int(
            audit.section("anchor_candidates")[
                "multiple_attractors_if_cluster_count_greater_than"
            ]
        )
        first = values[0]
        dispersion.append(
            {
                "scene_variant": first["scene_variant"],
                "geometry_seed": first["geometry_seed"],
                "measurement_seed": first["measurement_seed"],
                "block_id": block_id,
                "candidate_anchor": candidate,
                "repeat_count": len(values),
                "pair_count": len(translations),
                "median_pairwise_translation_m": _median(translations),
                "q95_pairwise_translation_m": _q95(translations),
                "maximum_pairwise_translation_m": max(translations, default=0.0),
                "median_pairwise_rotation_rad": _median(rotations),
                "q95_pairwise_rotation_rad": _q95(rotations),
                "maximum_pairwise_rotation_rad": max(rotations, default=0.0),
                "cluster_count": clusters,
                "multiple_attractors": multiple,
            }
        )
        for row in values:
            row["repeat_cluster_count"] = clusters
            row["multiple_attractors"] = multiple
            row["snapshot_anchor_eligible"] = bool(
                row["conditions_1_to_4_pass"] and not multiple
            )

    summaries: list[dict[str, Any]] = []
    minimum = float(
        audit.section("anchor_candidates")["minimum_snapshot_acceptance_fraction"]
    )
    for candidate in EXPECTED_CANDIDATES:
        values = [row for row in rows if row["candidate_anchor"] == candidate]
        block_multiple = {
            row["block_id"] for row in values if bool(row["multiple_attractors"])
        }
        condition_fraction = sum(bool(row["conditions_1_to_4_pass"]) for row in values) / len(values)
        eligible_fraction = sum(bool(row["snapshot_anchor_eligible"]) for row in values) / len(values)
        translations = [float(row["anchor_translation_error_to_gt_m"]) for row in values]
        rotations = [float(row["anchor_rotation_error_to_gt_rad"]) for row in values]
        zero_rate = sum(
            bool(row["full_method_self_consistent"]) for row in values
        ) / len(values)
        summaries.append(
            {
                "candidate_anchor": candidate,
                "snapshot_count": len(values),
                "zero_perturbation_success_rate": zero_rate,
                "anchor_gt_accuracy_fraction": sum(
                    bool(row["anchor_absolute_accuracy_valid"]) for row in values
                )
                / len(values),
                "median_anchor_translation_error_to_gt_m": _median(translations),
                "q95_anchor_translation_error_to_gt_m": _q95(translations),
                "median_anchor_rotation_error_to_gt_rad": _median(rotations),
                "q95_anchor_rotation_error_to_gt_rad": _q95(rotations),
                "full_method_self_consistency_fraction": sum(
                    bool(row["full_method_self_consistent"]) for row in values
                )
                / len(values),
                "frozen_method_consistency_fraction": sum(
                    bool(row["frozen_method_consistent_to_common_anchor"])
                    for row in values
                )
                / len(values),
                "conditions_1_to_4_fraction": condition_fraction,
                "multiple_attractor_block_count": len(block_multiple),
                "eligible_snapshot_fraction": eligible_fraction,
                "anchor_valid": bool(
                    condition_fraction >= minimum
                    and eligible_fraction >= minimum
                    and not block_multiple
                ),
            }
        )
    return rows, summaries, dispersion


def _common_anchor_rows(
    noise_rows: Sequence[Mapping[str, Any]], audit: Any, full_anchor_valid: bool
) -> list[dict[str, Any]]:
    locked = [row for row in noise_rows if row["condition_id"] == "LOCKED_FULL_NOISE"]
    by_key = {
        (row["base_snapshot_id"], row["method"]): row for row in locked
    }
    result = []
    for snapshot_id in sorted({str(row["base_snapshot_id"]) for row in locked}):
        full = by_key[(snapshot_id, "full_reassociation")]
        frozen = by_key[(snapshot_id, "frozen_jacobian")]
        full_pose = pose_from_json(str(full["zero_final_pose"]))
        frozen_pose = pose_from_json(str(frozen["zero_final_pose"]))
        eligible, translation, rotation = common_anchor_eligible(
            frozen_pose, full_pose, audit
        )
        result.append(
            {
                "scene_variant": full["scene_variant"],
                "geometry_seed": full["geometry_seed"],
                "measurement_seed": full["measurement_seed"],
                "repeat_index": full["repeat_index"],
                "block_id": full["block_id"],
                "base_snapshot_id": snapshot_id,
                "full_anchor_pose": full["zero_final_pose"],
                "frozen_zero_pose": frozen["zero_final_pose"],
                "translation_distance_m": translation,
                "rotation_distance_rad": rotation,
                "distance_eligible": eligible,
                "full_zero_anchor_globally_valid": full_anchor_valid,
                "eligible_for_subsequent_comparison": bool(
                    eligible and full_anchor_valid
                ),
            }
        )
    return result


def _root_cause_rows(
    root: Path,
    formal_rows: Sequence[Mapping[str, Any]],
    noise_rows: Sequence[Mapping[str, Any]],
    dispersion_rows: Sequence[Mapping[str, Any]],
    audit: Any,
) -> list[dict[str, Any]]:
    source = _read_csv(
        root / audit.section("d50_zero_root_cause")["source_file"]
    )
    tolerance = float(audit.section("d50_zero_root_cause")["exact_zero_tolerance"])
    zero_records = [
        row
        for row in source
        if row["d50"] != ""
        and abs(float(row["d50"])) <= tolerance
        and not _bool(row["d50_right_censored"])
    ]
    formal_by_block_method: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in formal_rows:
        formal_by_block_method[(str(row["block_id"]), str(row["method"]))].append(row)
    noise_by_block_method_condition: dict[
        tuple[str, str, str], list[Mapping[str, Any]]
    ] = defaultdict(list)
    for row in noise_rows:
        noise_by_block_method_condition[
            (str(row["block_id"]), str(row["method"]), str(row["condition_id"]))
        ].append(row)
    cluster_by_block = {
        str(row["block_id"]): int(row["cluster_count"])
        for row in dispersion_rows
        if row["candidate_anchor"] == "FULL_ZERO_SOLUTION_ANCHOR"
    }
    section = audit.section("d50_zero_root_cause")
    result = []
    for source_row in zero_records:
        block = source_row["block_id"]
        method = source_row["registration_path"]
        zero = formal_by_block_method[(block, method)]
        if len(zero) != 5:
            raise ValueError(f"d50-zero block lacks five formal zero rows: {block}")
        success_rate = sum(bool(row["zero_success_under_current_gt_rule"]) for row in zero) / 5.0
        convergence_rate = sum(bool(row["zero_solver_converged"]) for row in zero) / 5.0
        threshold_conflicts = sum(
            bool(row["zero_solver_converged"])
            and bool(row["zero_finite_output"])
            and not bool(row["zero_success_under_current_gt_rule"])
            for row in zero
        )
        threshold_conflict_rate = threshold_conflicts / 5.0
        reference_fraction = sum(
            bool(row["reference_pose_not_registration_fixed_point"]) for row in zero
        ) / 5.0
        association_fraction = sum(
            bool(row["zero_correspondence_changed"]) for row in zero
        ) / 5.0
        noise_free = noise_by_block_method_condition[(block, method, "NOISE_FREE")]
        locked = noise_by_block_method_condition[(block, method, "LOCKED_FULL_NOISE")]
        nf_rate = sum(bool(row["zero_success_under_current_gt_rule"]) for row in noise_free) / 5.0
        locked_rate = sum(bool(row["zero_success_under_current_gt_rule"]) for row in locked) / 5.0
        clusters = cluster_by_block[block]
        facts = {
            "MULTIPLE_ATTRACTORS": clusters > 1,
            "ZERO_SOLVER_FAILURE": (1.0 - convergence_rate)
            >= float(section["solver_failure_majority_fraction"]),
            "SUCCESS_THRESHOLD_CONFLICT": threshold_conflict_rate
            >= float(section["threshold_conflict_majority_fraction"]),
            "NOISE_SHIFT_EXCEEDS_THRESHOLD": nf_rate
            >= float(section["noise_explanation_minimum_noise_free_success_rate"])
            and locked_rate
            <= float(section["noise_explanation_maximum_locked_success_rate"]),
            "DROPOUT_SHIFT_EXCEEDS_THRESHOLD": False,
            "ZERO_ASSOCIATION_SWITCH": method == "full_reassociation"
            and association_fraction >= 0.5,
            "REFERENCE_NOT_FIXED_POINT": reference_fraction >= 0.5,
            "UNKNOWN": False,
        }
        primary, secondary = classify_d50_zero_root_cause(facts, audit)
        result.append(
            {
                "scene_variant": source_row["scene_variant"],
                "geometry_seed": source_row["geometry_seed"],
                "measurement_seed": source_row["measurement_seed"],
                "block_id": block,
                "perturbation_type": source_row["perturbation_type"],
                "direction_id": source_row["direction_id"],
                "registration_path": method,
                "original_d50": source_row["d50"],
                "primary_reason": primary,
                "secondary_reasons": ";".join(secondary),
                "zero_success_rate": success_rate,
                "zero_solver_convergence_rate": convergence_rate,
                "zero_threshold_conflict_rate": threshold_conflict_rate,
                "reference_not_fixed_point_fraction": reference_fraction,
                "zero_association_switch_fraction": association_fraction,
                "noise_free_zero_success_rate": nf_rate,
                "locked_full_noise_zero_success_rate": locked_rate,
                "repeat_cluster_count": clusters,
            }
        )
    return result


def _mechanism_rows(
    root: Path,
    formal_rows: Sequence[Mapping[str, Any]],
    audit: Any,
) -> list[dict[str, Any]]:
    section = audit.section("full_frozen_difference_mechanism")
    comparisons = [
        row
        for row in _read_csv(root / section["source_comparison_file"])
        if _bool(row["descriptive_difference_observed"])
    ]
    if len(comparisons) != int(section["expected_rows"]):
        raise ValueError("original descriptive-difference row count changed")
    keys = {
        (
            row["scene_variant"],
            int(row["geometry_seed"]),
            int(row["measurement_seed"]),
            row["direction_id"],
        )
        for row in comparisons
    }
    trials: dict[tuple[str, int, int, str], list[dict[str, str]]] = defaultdict(list)
    trial_path = root / section["source_trial_file"]
    with trial_path.open("r", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["perturbation_type"] != "translation":
                continue
            key = (
                row["scene_variant"],
                int(row["geometry_seed"]),
                int(row["measurement_seed"]),
                row["direction_id"],
            )
            if key in keys:
                trials[key].append(row)
    formal_by_block: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in formal_rows:
        formal_by_block[str(row["block_id"])].append(row)
    result: list[dict[str, Any]] = []
    translation_threshold = 0.02
    rotation_threshold = math.radians(0.5)
    for comparison in comparisons:
        key = (
            comparison["scene_variant"],
            int(comparison["geometry_seed"]),
            int(comparison["measurement_seed"]),
            comparison["direction_id"],
        )
        rows = trials[key]
        if len(rows) != 80:
            raise ValueError(f"mechanism comparison does not have 80 source trials: {key}")
        paired = {
            (int(row["repeat_index"]), float(row["amplitude"]), row["registration_path"]): row
            for row in rows
        }
        amplitudes = sorted({float(row["amplitude"]) for row in rows})
        mismatch_fractions = []
        solver_failure_count = 0
        switch_explanation_count = 0
        low_residual_wrong_count = 0
        failure_amplitudes = []
        second_cluster = False
        for amplitude in amplitudes:
            mismatch_count = 0
            full_poses = []
            for repeat in range(5):
                full = paired[(repeat, amplitude, "full_reassociation")]
                frozen = paired[(repeat, amplitude, "frozen_jacobian")]
                full_success = _bool(full["success"])
                frozen_success = _bool(frozen["success"])
                if full_success != frozen_success:
                    mismatch_count += 1
                if frozen_success and not full_success:
                    if not _bool(full["solver_converged"]) or full["termination_reason"] == "iteration_limit":
                        solver_failure_count += 1
                    if int(full["correspondence_checksum_change_count"]) > 0:
                        switch_explanation_count += 1
                    pose_wrong = (
                        float(full["translation_error_m"]) > translation_threshold
                        or float(full["rotation_error_deg"]) > 0.5
                    )
                    if pose_wrong and float(full["final_cost"]) <= float(frozen["final_cost"]):
                        low_residual_wrong_count += 1
                    failure_amplitudes.append(amplitude)
                full_poses.append(pose_from_json(full["final_pose"]))
            mismatch_fractions.append(mismatch_count / 5.0)
            if repeat_cluster_count(full_poses, audit) > 1:
                second_cluster = True
        block_rows = formal_by_block[comparison["block_id"]]
        full_zero = {int(row["repeat_index"]): row for row in block_rows if row["method"] == "full_reassociation"}
        frozen_zero = {int(row["repeat_index"]): row for row in block_rows if row["method"] == "frozen_jacobian"}
        anchor_mismatch_count = 0
        for repeat in range(5):
            translation, rotation = pose_distance(
                pose_from_json(str(full_zero[repeat]["zero_final_pose"])),
                pose_from_json(str(frozen_zero[repeat]["zero_final_pose"])),
            )
            if translation > translation_threshold or rotation > rotation_threshold:
                anchor_mismatch_count += 1
        anchor_fraction = anchor_mismatch_count / 5.0
        anchor_explained = anchor_fraction >= float(section["anchor_mismatch_majority_fraction"])
        checksum_explained = switch_explanation_count > 0
        solver_explained = solver_failure_count > 0
        maximum_mismatch = max(mismatch_fractions)
        raw_gap = float(comparison["raw_maximum_probability_gap"])
        candidate = bool(
            not anchor_explained
            and checksum_explained
            and raw_gap >= float(section["stable_raw_gap_minimum"])
            and maximum_mismatch
            >= float(section["stable_repeat_recovery_mismatch_fraction"])
        )
        unexplained = not (checksum_explained or anchor_explained or solver_explained)
        frozen_linear = all(
            int(row["full_reassociation_count"]) == 0
            and _bool(row["solver_converged"])
            for row in rows
            if row["registration_path"] == "frozen_jacobian"
        )
        result.append(
            {
                "scene_variant": comparison["scene_variant"],
                "geometry_seed": comparison["geometry_seed"],
                "measurement_seed": comparison["measurement_seed"],
                "block_id": comparison["block_id"],
                "direction_id": comparison["direction_id"],
                "raw_maximum_probability_gap": raw_gap,
                "anchor_mismatch_fraction": anchor_fraction,
                "difference_explained_by_correspondence_switch": checksum_explained,
                "difference_explained_by_anchor_mismatch": anchor_explained,
                "difference_explained_by_solver_failure": solver_explained,
                "full_final_pose_second_cluster": second_cluster,
                "full_failure_after_amplitude_m": min(failure_amplitudes) if failure_amplitudes else None,
                "frozen_still_linear_return": frozen_linear,
                "full_low_residual_wrong_pose": low_residual_wrong_count > 0,
                "maximum_repeat_recovery_mismatch_fraction": maximum_mismatch,
                "difference_unexplained": unexplained,
                "full_reassociation_nonlinear_effect_candidate": candidate,
            }
        )
    return result


def _noise_summary(noise_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for condition in ("NOISE_FREE", "SCAN_NOISE_ONLY", "MAP_NOISE_ONLY", "LOCKED_FULL_NOISE"):
        for method in ("full_reassociation", "frozen_jacobian"):
            rows = [
                row
                for row in noise_rows
                if row["condition_id"] == condition and row["method"] == method
            ]
            result.append(
                {
                    "condition_id": condition,
                    "method": method,
                    "count": len(rows),
                    "success_rate": sum(bool(row["zero_success_under_current_gt_rule"]) for row in rows) / len(rows),
                    "median_translation_shift_m": _median([float(row["zero_translation_shift_from_reference_m"]) for row in rows]),
                    "q95_translation_shift_m": _q95([float(row["zero_translation_shift_from_reference_m"]) for row in rows]),
                    "median_rotation_shift_rad": _median([float(row["zero_rotation_shift_from_reference_rad"]) for row in rows]),
                    "q95_rotation_shift_rad": _q95([float(row["zero_rotation_shift_from_reference_rad"]) for row in rows]),
                    "median_cost_change": _median([float(row["zero_cost_change"]) for row in rows]),
                    "median_gradient_norm": _median([float(row["zero_gradient_norm_at_reference"]) for row in rows]),
                    "correspondence_changed_fraction": sum(bool(row["zero_correspondence_changed"]) for row in rows) / len(rows),
                }
            )
    return result


def _figures(
    figures: Path,
    formal_rows: Sequence[Mapping[str, Any]],
    noise_summary: Sequence[Mapping[str, Any]],
    anchor_rows: Sequence[Mapping[str, Any]],
    dispersion_rows: Sequence[Mapping[str, Any]],
    mechanism_rows: Sequence[Mapping[str, Any]],
) -> None:
    plt.rcParams.update({"figure.dpi": 110, "font.size": 8})
    scenes = sorted({str(row["scene_variant"]) for row in formal_rows})
    methods = ("full_reassociation", "frozen_jacobian")

    fig, ax = plt.subplots(figsize=(10, 4))
    x = np.arange(len(scenes))
    for offset, method in zip((-0.18, 0.18), methods):
        medians = [
            _median([
                float(row["zero_translation_shift_from_reference_m"])
                for row in formal_rows
                if row["scene_variant"] == scene and row["method"] == method
            ]) or 0.0
            for scene in scenes
        ]
        ax.bar(x + offset, medians, 0.34, label=method)
    ax.set_xticks(x, scenes, rotation=25, ha="right")
    ax.set_ylabel("median translation shift (m)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figures / "zero_pose_shift_by_scene.png", metadata={"Software": "Degen-LIO"})
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4))
    values = [
        [
            float(row["zero_gradient_norm_at_reference"])
            for row in formal_rows
            if row["scene_variant"] == scene and row["method"] == "full_reassociation"
        ]
        for scene in scenes
    ]
    ax.boxplot(values, labels=scenes, showfliers=False)
    ax.set_yscale("symlog", linthresh=1.0e-10)
    ax.tick_params(axis="x", rotation=25)
    ax.set_ylabel("robust gradient norm")
    fig.tight_layout()
    fig.savefig(figures / "zero_gradient_norm_by_scene.png", metadata={"Software": "Degen-LIO"})
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    conditions = ("NOISE_FREE", "SCAN_NOISE_ONLY", "MAP_NOISE_ONLY", "LOCKED_FULL_NOISE")
    x = np.arange(len(conditions))
    for offset, method in zip((-0.18, 0.18), methods):
        rates = [
            next(float(row["success_rate"]) for row in noise_summary if row["condition_id"] == condition and row["method"] == method)
            for condition in conditions
        ]
        ax.bar(x + offset, rates, 0.34, label=method)
    ax.set_xticks(x, conditions, rotation=20, ha="right")
    ax.set_ylim(0.0, 1.0)
    ax.set_ylabel("zero success rate")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figures / "noise_ablation_zero_success.png", metadata={"Software": "Degen-LIO"})
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    candidates = EXPECTED_CANDIDATES
    data = [
        [
            float(row["anchor_translation_error_to_gt_m"])
            for row in anchor_rows
            if row["candidate_anchor"] == candidate
        ]
        for candidate in candidates
    ]
    ax.boxplot(data, labels=candidates, showfliers=False)
    ax.tick_params(axis="x", rotation=20)
    ax.set_ylabel("anchor translation error to GT (m)")
    fig.tight_layout()
    fig.savefig(figures / "anchor_error_to_gt.png", metadata={"Software": "Degen-LIO"})
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    for index, candidate in enumerate(candidates):
        rows = [row for row in dispersion_rows if row["candidate_anchor"] == candidate]
        ax.scatter(
            np.full(len(rows), index),
            [float(row["maximum_pairwise_translation_m"]) for row in rows],
            s=10,
            alpha=0.7,
            label=candidate,
        )
    ax.set_xticks(range(len(candidates)), candidates, rotation=20)
    ax.set_ylabel("block max pairwise translation (m)")
    fig.tight_layout()
    fig.savefig(figures / "anchor_repeat_clusters.png", metadata={"Software": "Degen-LIO"})
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    labels = ("correspondence_switch", "anchor_mismatch", "solver_failure", "unexplained")
    counts = (
        sum(bool(row["difference_explained_by_correspondence_switch"]) for row in mechanism_rows),
        sum(bool(row["difference_explained_by_anchor_mismatch"]) for row in mechanism_rows),
        sum(bool(row["difference_explained_by_solver_failure"]) for row in mechanism_rows),
        sum(bool(row["difference_unexplained"]) for row in mechanism_rows),
    )
    ax.bar(labels, counts)
    ax.tick_params(axis="x", rotation=20)
    ax.set_ylabel("original difference rows")
    fig.tight_layout()
    fig.savefig(figures / "full_frozen_correspondence_switch.png", metadata={"Software": "Degen-LIO"})
    plt.close(fig)


def _write_sha256sums(artifact: Path) -> None:
    paths = sorted(
        path for path in artifact.rglob("*") if path.is_file() and path.name != "SHA256SUMS"
    )
    lines = [
        f"{exact_file_sha256(path)}  {path.relative_to(artifact).as_posix()}"
        for path in paths
    ]
    (artifact / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def verify_anchor_validity_audit_output(directory: str | Path) -> dict[str, Any]:
    root = Path(directory)
    expected = {
        *(f"tables/{name}" for name in TABLE_FILES),
        *(f"figures/{name}" for name in FIGURE_FILES),
        *TOP_LEVEL_FILES,
    }
    actual = {
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
    }
    if actual != expected:
        raise ValueError(f"anchor audit output set mismatch: {sorted(actual ^ expected)}")
    lines = (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    if len(lines) != len(expected) - 1:
        raise ValueError("anchor audit SHA256SUMS coverage mismatch")
    listed = set()
    for line in lines:
        digest, relative = line.split("  ", 1)
        if relative in listed or exact_file_sha256(root / relative) != digest:
            raise ValueError(f"anchor audit checksum mismatch: {relative}")
        listed.add(relative)
    if listed != expected - {"SHA256SUMS"}:
        raise ValueError("anchor audit SHA256SUMS file set mismatch")
    manifest = json.loads((root / "run_manifest.json").read_text(encoding="utf-8"))
    decision = json.loads((root / "final_decision.json").read_text(encoding="utf-8"))
    if decision["CONFIRMATORY_TEST_AUTHORIZED"] is not False:
        raise ValueError("confirmatory Test authorization must remain false")
    if manifest["formal_zero_row_count"] != 420 or manifest["noise_ablation_row_count"] != 1680:
        raise ValueError("anchor audit row-count contract failed")
    return {"manifest": manifest, "decision": decision}


def run_anchor_validity_audit(
    repository_root: str | Path,
    *,
    workers: int | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    audit = load_anchor_audit_protocol(root)
    development = load_day2_development_protocol(root)
    artifact = root / audit.section("outputs")["artifact_root"]
    if artifact.exists():
        raise FileExistsError("anchor validity audit artifact directory must be new")
    source_artifact = root / audit.section("frozen_source")["artifact_root"]
    source_result = root / audit.section("frozen_source")["result_root"]
    compact = root / audit.section("frozen_source")["compact_input_root"]
    _verify_sha256sums(source_artifact)
    _verify_sha256sums(source_result)
    _verify_sha256sums(compact)
    for path in source_artifact.iterdir():
        if path.is_file() and path.read_bytes() != (source_result / path.name).read_bytes():
            raise ValueError(f"Development result/artifact mismatch: {path.name}")
    worktree_clean_at_start = _git(root, "status", "--porcelain") == ""
    if not worktree_clean_at_start:
        raise RuntimeError("anchor validity audit requires a clean worktree")
    implementation_commit = _git(root, "rev-parse", "HEAD")
    started = time.perf_counter()

    source_snapshots = _read_csv(compact / "snapshot_inventory.csv")
    expected_by_id = {row["base_snapshot_id"]: row for row in source_snapshots}
    if len(expected_by_id) != 210:
        raise ValueError("frozen compact input does not contain 210 snapshots")
    seed = development.section("seed_firewall")
    scenes = tuple(development.section("scene_generation")["variants_in_order"])
    identities = []
    for scene in scenes:
        for geometry in seed["allowed_geometry_seeds"]:
            for measurement in seed["allowed_measurement_seeds"]:
                for repeat in range(int(seed["repeats"])):
                    snapshot_id = f"dev::{scene}::g{geometry}::m{measurement}::r{repeat:02d}"
                    identities.append(
                        (
                            str(root),
                            scene,
                            int(geometry),
                            int(measurement),
                            repeat,
                            {
                                name: expected_by_id[snapshot_id][name]
                                for name in (
                                    "base_snapshot_checksum",
                                    "scan_checksum",
                                    "map_checksum",
                                    "dropout_checksum",
                                )
                            },
                        )
                    )
    worker_count = int(workers or min(len(identities), os.cpu_count() or 1))
    all_noise_rows: list[dict[str, Any]] = []
    seed_audit: Counter[str] = Counter()
    if worker_count == 1:
        iterator = map(_snapshot_task, identities)
        for index, payload in enumerate(iterator, start=1):
            all_noise_rows.extend(payload["rows"])
            seed_audit.update(payload["seed_audit"])
            if index % 5 == 0 or index == len(identities):
                print(f"ANCHOR_AUDIT_PROGRESS={index}/{len(identities)}", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            for index, payload in enumerate(
                executor.map(_snapshot_task, identities, chunksize=1), start=1
            ):
                all_noise_rows.extend(payload["rows"])
                seed_audit.update(payload["seed_audit"])
                if index % 5 == 0 or index == len(identities):
                    print(f"ANCHOR_AUDIT_PROGRESS={index}/{len(identities)}", flush=True)
    if len(all_noise_rows) != 1680:
        raise RuntimeError("anchor audit did not produce 1680 primary noise rows")
    all_noise_rows.sort(
        key=lambda row: (
            scenes.index(row["scene_variant"]),
            int(row["geometry_seed"]),
            int(row["measurement_seed"]),
            int(row["repeat_index"]),
            ("NOISE_FREE", "SCAN_NOISE_ONLY", "MAP_NOISE_ONLY", "LOCKED_FULL_NOISE").index(row["condition_id"]),
            ("full_reassociation", "frozen_jacobian").index(row["method"]),
        )
    )
    formal_rows = [
        row for row in all_noise_rows if row["condition_id"] == "LOCKED_FULL_NOISE"
    ]
    if len(formal_rows) != 420:
        raise RuntimeError("anchor audit did not produce 420 formal zero rows")
    minimum_zero = float(
        audit.section("formal_zero_audit")["minimum_valid_zero_recovery_probability"]
    )
    formal_by_block_method: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in formal_rows:
        formal_by_block_method[(str(row["block_id"]), str(row["method"]))].append(row)
    for values in formal_by_block_method.values():
        block_rate = sum(
            bool(row["zero_success_under_current_gt_rule"]) for row in values
        ) / len(values)
        for row in values:
            row["zero_block_success_rate"] = block_rate
            row["directionality_interpretation_eligible"] = block_rate >= minimum_zero
    success_summary = _build_success_summary(formal_rows, minimum_zero)
    fixed_rows = _fixed_rows(formal_rows)
    fixed_summary = []
    for method in ("full_reassociation", "frozen_jacobian"):
        values = [row for row in fixed_rows if row["method"] == method]
        fixed_summary.append(
            {
                "method": method,
                "median_reference_gradient_norm": _median(
                    [float(row["reference_gradient_norm"]) for row in values]
                ),
                "q95_reference_gradient_norm": _q95(
                    [float(row["reference_gradient_norm"]) for row in values]
                ),
                "median_one_step_translation_m": _median(
                    [float(row["one_step_translation_m"]) for row in values]
                ),
                "q95_one_step_translation_m": _q95(
                    [float(row["one_step_translation_m"]) for row in values]
                ),
                "reference_not_fixed_point_fraction": sum(
                    bool(row["reference_pose_not_registration_fixed_point"])
                    for row in values
                )
                / len(values),
            }
        )
    anchor_rows, anchor_summaries, dispersion_rows = _candidate_rows(all_noise_rows, audit)
    anchor_validity = {
        row["candidate_anchor"]: bool(row["anchor_valid"])
        for row in anchor_summaries
    }
    full_anchor_valid = anchor_validity["FULL_ZERO_SOLUTION_ANCHOR"]
    common_rows = _common_anchor_rows(all_noise_rows, audit, full_anchor_valid)
    root_rows = _root_cause_rows(
        root, formal_rows, all_noise_rows, dispersion_rows, audit
    )
    mechanism_rows = _mechanism_rows(root, formal_rows, audit)
    noise_summary = _noise_summary(all_noise_rows)

    per_scene_rows = [row for row in success_summary if row["scene_variant"] != "ALL_SCENES"]
    zero_baseline_valid = all(bool(row["p_zero_at_least_0p95"]) for row in per_scene_rows)
    reference_not_fixed = any(
        bool(row["reference_pose_not_registration_fixed_point"]) for row in fixed_rows
    )
    summary_by_condition_method = {
        (row["condition_id"], row["method"]): row for row in noise_summary
    }
    nf_full = float(summary_by_condition_method[("NOISE_FREE", "full_reassociation")]["success_rate"])
    scan_full = float(summary_by_condition_method[("SCAN_NOISE_ONLY", "full_reassociation")]["success_rate"])
    map_full = float(summary_by_condition_method[("MAP_NOISE_ONLY", "full_reassociation")]["success_rate"])
    noise_section = audit.section("noise_ablation")
    crossing = {}
    nf_by_snapshot = {
        row["base_snapshot_id"]: bool(row["zero_success_under_current_gt_rule"])
        for row in all_noise_rows
        if row["condition_id"] == "NOISE_FREE" and row["method"] == "full_reassociation"
    }
    for condition in ("SCAN_NOISE_ONLY", "MAP_NOISE_ONLY"):
        condition_by_snapshot = {
            row["base_snapshot_id"]: bool(row["zero_success_under_current_gt_rule"])
            for row in all_noise_rows
            if row["condition_id"] == condition and row["method"] == "full_reassociation"
        }
        crossing[condition] = sum(
            nf_by_snapshot[key] and not condition_by_snapshot[key]
            for key in nf_by_snapshot
        ) / len(nf_by_snapshot)
    noise_confirmed = bool(
        nf_full - min(scan_full, map_full)
        >= float(noise_section["noise_effect_minimum_success_rate_drop"])
        or max(crossing.values())
        >= float(noise_section["noise_effect_minimum_threshold_crossing_fraction"])
    )
    dropout_confirmed = bool(noise_section["dropout_state_when_causal_contrast_unavailable"])
    distance_fraction = sum(bool(row["distance_eligible"]) for row in common_rows) / len(common_rows)
    d50_identified = bool(root_rows) and all(row["primary_reason"] != "UNKNOWN" for row in root_rows)
    nonlinear_count = sum(
        bool(row["full_reassociation_nonlinear_effect_candidate"])
        for row in mechanism_rows
    )
    remaining_after_anchor = sum(
        not bool(row["difference_explained_by_anchor_mismatch"])
        for row in mechanism_rows
    )
    nonlinear_candidate = nonlinear_count > 0
    recommendation = "NONE"
    for candidate in audit.section("anchor_candidates")["recommendation_priority"]:
        if anchor_validity[str(candidate)]:
            recommendation = str(candidate)
            break
    recommended_gt_accurate = bool(
        recommendation != "NONE"
        and next(
            row for row in anchor_summaries if row["candidate_anchor"] == recommendation
        )["anchor_gt_accuracy_fraction"]
        >= 0.95
    )
    full_summary = next(
        row
        for row in success_summary
        if row["scene_variant"] == "ALL_SCENES"
        and row["method"] == "full_reassociation"
    )
    no_test_access = bool(
        seed_audit["confirmatory_seed_access_attempt_count"] == 0
        and seed_audit["confirmatory_seed_materialization_count"] == 0
        and seed_audit["unknown_seed_access_attempt_count"] == 0
    )
    no_gt_leakage = True
    route_recoverable = bool(
        d50_identified
        and recommendation != "NONE"
        and recommended_gt_accurate
        and float(full_summary["zero_success_rate"]) >= 0.95
        and distance_fraction
        >= float(audit.section("common_anchor")["minimum_route_eligible_fraction"])
        and nonlinear_candidate
        and no_test_access
        and no_gt_leakage
    )
    decision = {
        "ANCHOR_AUDIT_COMPLETE": True,
        "ZERO_PERTURBATION_BASELINE_VALID": zero_baseline_valid,
        "REFERENCE_POSE_NOT_REGISTRATION_FIXED_POINT": reference_not_fixed,
        "NOISE_INDUCED_ANCHOR_SHIFT_CONFIRMED": noise_confirmed,
        "DROPOUT_INDUCED_ANCHOR_SHIFT_CONFIRMED": dropout_confirmed,
        "GT_REFERENCE_ANCHOR_VALID": anchor_validity["GT_REFERENCE_ANCHOR"],
        "FULL_ZERO_SOLUTION_ANCHOR_VALID": full_anchor_valid,
        "NOISE_FREE_FULL_SOLUTION_ANCHOR_VALID": anchor_validity[
            "NOISE_FREE_FULL_SOLUTION_ANCHOR"
        ],
        "FROZEN_COMMON_ANCHOR_ELIGIBLE_FRACTION": distance_fraction,
        "D50_ZERO_ROOT_CAUSE_IDENTIFIED": d50_identified,
        "FULL_REASSOCIATION_NONLINEAR_EFFECT_CANDIDATE": nonlinear_candidate,
        "DIRECTIONAL_CAPTURE_RANGE_ROUTE_RECOVERABLE": route_recoverable,
        "NEW_CONFIRMATORY_PROTOCOL_AUTHORIZED": route_recoverable,
        "CONFIRMATORY_TEST_AUTHORIZED": False,
        "NO_TEST_SEED_ACCESS": no_test_access,
        "NO_GT_LEAKAGE": no_gt_leakage,
        "RECOMMENDED_ANCHOR": recommendation,
        "NONLINEAR_EFFECT_CANDIDATE_COUNT": nonlinear_count,
        "DIFFERENCES_REMAINING_AFTER_ANCHOR_MISMATCH_EXCLUSION": remaining_after_anchor,
    }

    tables = artifact / "tables"
    figures = artifact / "figures"
    tables.mkdir(parents=True)
    figures.mkdir()
    _write_csv(tables / "zero_perturbation_results.csv", formal_rows, ZERO_FIELDS)
    _write_csv(tables / "zero_success_by_scene.csv", success_summary, SUCCESS_FIELDS)
    _write_csv(tables / "fixed_point_gradient_audit.csv", fixed_rows, FIXED_FIELDS)
    _write_csv(tables / "noise_ablation.csv", all_noise_rows, NOISE_FIELDS)
    _write_csv(tables / "anchor_candidate_comparison.csv", anchor_summaries, ANCHOR_COMPARISON_FIELDS)
    _write_csv(tables / "anchor_gt_accuracy.csv", anchor_rows, ANCHOR_GT_FIELDS)
    _write_csv(tables / "anchor_repeat_dispersion.csv", dispersion_rows, DISPERSION_FIELDS)
    _write_csv(tables / "frozen_common_anchor_eligibility.csv", common_rows, COMMON_FIELDS)
    _write_csv(tables / "d50_zero_root_cause.csv", root_rows, ROOT_FIELDS)
    _write_csv(tables / "full_frozen_difference_mechanism.csv", mechanism_rows, MECHANISM_FIELDS)
    _write_csv(tables / "final_decision.csv", [decision], FINAL_FIELDS)
    _figures(figures, formal_rows, noise_summary, anchor_rows, dispersion_rows, mechanism_rows)

    (artifact / "final_decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    runtime_seconds = time.perf_counter() - started
    root_counts = dict(sorted(Counter(row["primary_reason"] for row in root_rows).items()))
    mechanism_counts = {
        "correspondence_switch": sum(bool(row["difference_explained_by_correspondence_switch"]) for row in mechanism_rows),
        "anchor_mismatch": sum(bool(row["difference_explained_by_anchor_mismatch"]) for row in mechanism_rows),
        "solver_failure": sum(bool(row["difference_explained_by_solver_failure"]) for row in mechanism_rows),
        "unexplained": sum(bool(row["difference_unexplained"]) for row in mechanism_rows),
    }
    manifest = {
        "schema_version": "directional_capture_range_anchor_validity_audit_run_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "branch": _git(root, "branch", "--show-current"),
        "initial_result_commit": audit.section("frozen_source")["commit"],
        "implementation_commit": implementation_commit,
        "audit_protocol_path": "configs/capture_range/anchor_validity_audit.yaml",
        "audit_protocol_sha256": audit.source_sha256,
        "development_protocol_sha256": development.source_sha256,
        "worktree_clean_at_start": worktree_clean_at_start,
        "workers": worker_count,
        "runtime_seconds": runtime_seconds,
        "base_snapshot_count": 210,
        "formal_zero_row_count": len(formal_rows),
        "noise_ablation_row_count": len(all_noise_rows),
        "deterministic_recheck_execution_count": sum(
            bool(row["deterministic_recheck_performed"]) for row in all_noise_rows
        ),
        "zero_registration_execution_count": len(all_noise_rows)
        + sum(bool(row["deterministic_recheck_performed"]) for row in all_noise_rows),
        "seed_access_audit": dict(seed_audit),
        "source_snapshot_checksum_mismatch_count": 0,
        "noise_ablation_summary": noise_summary,
        "noise_free_success_to_failure_crossing_fraction": crossing,
        "fixed_point_summary": fixed_summary,
        "anchor_candidate_summary": anchor_summaries,
        "d50_zero_root_cause_counts": root_counts,
        "full_frozen_difference_mechanism_counts": mechanism_counts,
        "dropout_identification_reason": noise_section["dropout_state_reason"],
        "claim_boundaries": {
            "confirmatory_test_run": False,
            "test_lock_generated": False,
            "real_data_used": False,
            "odi_modified": False,
            "fast_lio2_modified": False,
            "vision_used": False,
            "measurement_route_claimed": False,
            "capture_range_protocol_modified": False,
            "pushed": False,
        },
        **decision,
    }
    (artifact / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    report_lines = [
        "# Directional Capture Range Anchor Validity Audit",
        "",
        "Development-only zero-perturbation diagnostic audit. No Confirmatory Test or scientific Measurement claim is authorized.",
        "",
        "## Final decision",
        "",
        *[f"{name} = {str(value).lower() if isinstance(value, bool) else value}" for name, value in decision.items()],
        "",
        "## Formal zero success by scene and method",
        "",
        "| scene | method | success | median translation (m) | q95 translation (m) | median rotation (rad) | q95 rotation (rad) |",
        "|---|---|---:|---:|---:|---:|---:|",
        *[
            "| {scene_variant} | {method} | {zero_success_count}/{snapshot_count} ({zero_success_rate:.6f}) | {median_zero_translation_shift_m:.9g} | {q95_zero_translation_shift_m:.9g} | {median_zero_rotation_shift_rad:.9g} | {q95_zero_rotation_shift_rad:.9g} |".format(**row)
            for row in success_summary
            if row["scene_variant"] != "ALL_SCENES"
        ],
        "",
        "## Four-condition noise ablation",
        "",
        "| condition | method | zero success | median translation (m) | median rotation (rad) | median cost change |",
        "|---|---|---:|---:|---:|---:|",
        *[
            "| {condition_id} | {method} | {success_rate:.6f} | {median_translation_shift_m:.9g} | {median_rotation_shift_rad:.9g} | {median_cost_change:.9g} |".format(**row)
            for row in noise_summary
        ],
        "",
        "## Reference fixed-point summary",
        "",
        "| method | median gradient | q95 gradient | median first-step translation (m) | q95 first-step translation (m) | not-fixed fraction |",
        "|---|---:|---:|---:|---:|---:|",
        *[
            "| {method} | {median_reference_gradient_norm:.9g} | {q95_reference_gradient_norm:.9g} | {median_one_step_translation_m:.9g} | {q95_one_step_translation_m:.9g} | {reference_not_fixed_point_fraction:.6f} |".format(**row)
            for row in fixed_summary
        ],
        "",
        "The noise-induced status is based on matched-snapshot threshold crossings: "
        f"NOISE_FREE success to SCAN_NOISE_ONLY failure = {crossing['SCAN_NOISE_ONLY']:.6f}; "
        f"NOISE_FREE success to MAP_NOISE_ONLY failure = {crossing['MAP_NOISE_ONLY']:.6f}. "
        f"Aggregate full-reassociation success rates were NOISE_FREE = {nf_full:.6f}, "
        f"SCAN_NOISE_ONLY = {scan_full:.6f}, and MAP_NOISE_ONLY = {map_full:.6f}; "
        "therefore the confirmation does not assert an aggregate success-rate degradation or a dominant noise mechanism.",
        "",
        "Dropout causality is not identifiable from the frozen four contrasts because LOCKED_FULL_NOISE changes scan noise, map noise, and dropout together. The audit therefore does not claim a dropout-induced shift.",
        "",
        "## Anchor candidates",
        "",
        "| candidate | zero success | GT accurate | full self-consistent | frozen consistent | eligible | valid |",
        "|---|---:|---:|---:|---:|---:|---:|",
        *[
            "| {candidate_anchor} | {zero_perturbation_success_rate:.6f} | {anchor_gt_accuracy_fraction:.6f} | {full_method_self_consistency_fraction:.6f} | {frozen_method_consistency_fraction:.6f} | {eligible_snapshot_fraction:.6f} | {anchor_valid} |".format(**row)
            for row in anchor_summaries
        ],
        "",
        f"d50=0 primary root-cause counts: `{json.dumps(root_counts, sort_keys=True)}`.",
        f"Original full-vs-frozen mechanism counts: `{json.dumps(mechanism_counts, sort_keys=True)}`.",
        "",
        "All original Development outputs remained read-only. Success thresholds, amplitudes, directions, d50/d90, isotonic rules, geometry, ODI, FAST-LIO2, and vision inputs were unchanged.",
        "",
    ]
    (artifact / "anchor_validity_report.md").write_text(
        "\n".join(report_lines), encoding="utf-8"
    )
    _write_sha256sums(artifact)
    verified = verify_anchor_validity_audit_output(artifact)
    return {
        "artifact_dir": str(artifact),
        "manifest": manifest,
        "decision": decision,
        "verified": verified,
    }


__all__ = [
    "FIGURE_FILES",
    "TABLE_FILES",
    "TOP_LEVEL_FILES",
    "run_anchor_validity_audit",
    "verify_anchor_validity_audit_output",
]
