"""Day 1 directional capture-range smoke orchestration and artifacts."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import shutil
import subprocess
from dataclasses import fields
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from eval.directional_capture_contract import (
    PROTECTED_ARTIFACT_PATHS,
    load_capture_range_protocol,
    protocol_semantic_sha256,
)

from .capture_radius import build_direction_recovery_curve
from .frozen_jacobian_runner import (
    prepare_frozen_jacobian_baseline,
    run_frozen_jacobian_trial,
)
from .full_reassociation_runner import run_full_reassociation_trial
from .randomness import derive_trial_seed, noise_checksum, perturbation_checksum
from .snapshot import SMOKE_SCENES, build_smoke_snapshots, snapshot_checksums
from .types import (
    DirectionRecoveryCurve,
    PerturbationSpec,
    RecoveryTrialResult,
    RegistrationSnapshot,
)


REQUIRED_OUTPUT_FILES = (
    "protocol_lock.json",
    "trial_results.csv",
    "direction_curves.csv",
    "capture_radius_summary.csv",
    "runtime_summary.csv",
    "smoke_report.md",
    "run_manifest.json",
    "SHA256SUMS",
)
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def run_capture_range_smoke(
    config_path: str | Path,
    run_id: str,
    *,
    repository_root: str | Path,
    output_root: str | Path | None = None,
    artifact_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Run the frozen, intentionally small Day 1 engineering smoke matrix."""

    root = Path(repository_root).resolve()
    config_file = Path(config_path).resolve()
    if not RUN_ID_PATTERN.fullmatch(str(run_id)):
        raise ValueError("run_id must contain only letters, digits, dot, underscore, and dash")
    protocol = load_capture_range_protocol(config_file)
    result_parent = (
        Path(output_root).resolve()
        if output_root is not None
        else root / "results" / "capture_range" / "day1"
    )
    result_dir = result_parent / str(run_id)
    current_artifact = (
        Path(artifact_dir).resolve()
        if artifact_dir is not None
        else root / "artifacts" / "current" / "directional_capture_range_day1"
    )
    _assert_output_not_protected(root, result_dir)
    _assert_output_not_protected(root, current_artifact)
    if _is_same_or_descendant(result_dir, current_artifact) or _is_same_or_descendant(
        current_artifact, result_dir
    ):
        raise ValueError("result and artifact directories must not overlap")
    _require_new_output_directory(result_dir, label="result")
    _require_new_output_directory(current_artifact, label="artifact")
    result_dir.mkdir(parents=True)

    worktree_clean_at_start = _git_worktree_clean(root)
    config_bytes_sha256 = _sha256_file(config_file)
    semantic_sha256 = protocol_semantic_sha256(protocol)
    protocol_lock = {
        "schema_version": "directional_capture_range_protocol_lock_v1",
        "protocol_locked": True,
        "formal_measurement_name": protocol["protocol"]["formal_measurement_name"],
        "source_path": _relative_or_absolute(config_file, root),
        "source_sha256": config_bytes_sha256,
        "semantic_sha256": semantic_sha256,
        "complete_frozen_protocol": protocol,
        "frozen_scientific_state": dict(protocol["frozen_scientific_state"]),
        "measurement_object": dict(protocol["measurement_object"]),
        "pose_perturbation": dict(protocol["pose_perturbation"]),
        "success": dict(protocol["success"]),
        "recovery_probability": dict(protocol["recovery_probability"]),
        "capture_radius": dict(protocol["capture_radius"]),
        "sampling": dict(protocol["sampling"]),
        "registration": dict(protocol["registration"]),
        "randomness": dict(protocol["randomness"]),
        "ground_truth_boundary": dict(protocol["ground_truth_boundary"]),
    }
    _write_json(result_dir / "protocol_lock.json", protocol_lock)

    trial_records: list[tuple[RecoveryTrialResult, PerturbationSpec, dict[str, str]]] = []
    seed_derivation_mismatch_count = 0
    global_seed = int(protocol["randomness"]["global_seed"])
    empty_noise_checksum = noise_checksum(np.empty(0, dtype=np.float64))
    snapshots = build_smoke_snapshots(protocol)
    snapshot_manifest: list[dict[str, Any]] = []
    for snapshot in snapshots:
        checksums = snapshot_checksums(snapshot)
        snapshot_manifest.append(
            {
                "snapshot_id": snapshot.snapshot_id,
                "scene_name": snapshot.metadata["scene_name"],
                "scan_point_count": int(snapshot.scan_points.shape[0]),
                "map_point_count": int(snapshot.local_map_points.shape[0]),
                **checksums,
            }
        )
        frozen_model = prepare_frozen_jacobian_baseline(snapshot)
        for perturbation in _perturbation_specs(snapshot.snapshot_id, protocol):
            expected_seed = derive_trial_seed(
                snapshot.snapshot_id,
                perturbation.perturbation_type,
                perturbation.direction_id,
                perturbation.signed_amplitude,
                perturbation.repeat_index,
                global_seed,
            )
            seed_derivation_mismatch_count += int(expected_seed != perturbation.seed)
            provenance = {
                **checksums,
                "perturbation_checksum": perturbation_checksum(perturbation),
                "noise_checksum": empty_noise_checksum,
            }
            formal = run_full_reassociation_trial(snapshot, perturbation)
            baseline = run_frozen_jacobian_trial(
                snapshot,
                perturbation,
                baseline=frozen_model,
            )
            trial_records.append((formal, perturbation, provenance))
            trial_records.append((baseline, perturbation, provenance))

    reproducibility_audit = _run_reproducibility_and_gt_audit(
        snapshots, trial_records
    )

    trial_rows = [
        _trial_row(result, perturbation, provenance)
        for result, perturbation, provenance in trial_records
    ]
    _write_csv(result_dir / "trial_results.csv", trial_rows)
    curves, curve_counts = _build_curves(trial_records, protocol)
    _write_csv(result_dir / "direction_curves.csv", _direction_curve_rows(curves, curve_counts))
    _write_csv(result_dir / "capture_radius_summary.csv", _capture_radius_rows(curves))
    runtime_rows = _runtime_rows(trial_records)
    _write_csv(result_dir / "runtime_summary.csv", runtime_rows)

    smoke = _evaluate_smoke(
        trial_records,
        seed_derivation_mismatch_count,
        reproducibility_audit,
    )
    gates = {
        "ENGINEERING_PASS": bool(smoke["engineering_pass"]),
        "PROTOCOL_LOCKED": True,
        "FULL_REASSOCIATION_VERIFIED": bool(smoke["full_reassociation_verified"]),
        "FROZEN_JACOBIAN_BASELINE_ISOLATED": bool(smoke["frozen_baseline_isolated"]),
        "NO_GT_LEAKAGE": bool(
            smoke["optimizer_gt_access_count"] == 0
            and smoke["gt_result_mismatch_count"] == 0
        ),
        "SEED_DETERMINISM_PASS": bool(
            seed_derivation_mismatch_count == 0
            and smoke["deterministic_output_mismatch_count"] == 0
        ),
        "SMOKE_PIPELINE_PASS": bool(smoke["smoke_pipeline_pass"]),
        "WORKTREE_CLEAN": bool(worktree_clean_at_start),
    }
    day2_authorized = all(gates.values())
    _write_text(result_dir / "smoke_report.md", _smoke_report(run_id, smoke, gates, day2_authorized))

    manifest = {
        "schema_version": "directional_capture_range_day1_run_manifest_v1",
        "run_id": str(run_id),
        "formal_measurement_name": "Algorithm-Conditioned Empirical Directional Capture Range",
        "phase": "engineering_smoke_test_only",
        "protocol_semantic_sha256": semantic_sha256,
        "protocol_source_sha256": config_bytes_sha256,
        "git": {
            "branch": _git_output(root, "branch", "--show-current"),
            "commit": _git_output(root, "rev-parse", "HEAD"),
            "worktree_clean_at_run_start": worktree_clean_at_start,
        },
        "frozen_scientific_state": dict(protocol["frozen_scientific_state"]),
        "snapshots": snapshot_manifest,
        "randomness": {
            "frozen_configuration": dict(protocol["randomness"]),
            "global_seed": global_seed,
            "method_name_in_seed": False,
            "seed_derivation_mismatch_count": seed_derivation_mismatch_count,
            "determinism_rerun_count": reproducibility_audit["determinism_rerun_count"],
            "deterministic_output_mismatch_count": reproducibility_audit[
                "deterministic_output_mismatch_count"
            ],
            "runtime_excluded_from_deterministic_output_comparison": True,
            "noise_enabled": False,
            "noise_checksum": empty_noise_checksum,
        },
        "trial_counts": {
            "total": len(trial_records),
            "full_reassociation": sum(result.full_reassociation for result, _, _ in trial_records),
            "frozen_jacobian": sum(result.baseline_only for result, _, _ in trial_records),
        },
        "instrumentation": {
            "full_reassociation_execution_count": sum(
                result.full_reassociation_count for result, _, _ in trial_records
            ),
            "transform_execution_count": sum(
                result.transform_count for result, _, _ in trial_records if result.full_reassociation
            ),
            "nearest_neighbor_search_count": sum(
                result.nearest_neighbor_search_count
                for result, _, _ in trial_records
                if result.full_reassociation
            ),
            "correspondence_recomputation_count": sum(
                result.correspondence_build_count
                for result, _, _ in trial_records
                if result.full_reassociation
            ),
            "plane_recomputation_count": sum(
                result.plane_fit_count
                for result, _, _ in trial_records
                if result.full_reassociation
            ),
            "jacobian_recomputation_count": sum(
                result.jacobian_recomputation_count
                for result, _, _ in trial_records
                if result.full_reassociation
            ),
            "optimizer_gt_access_count": smoke["optimizer_gt_access_count"],
            "gt_result_mismatch_count": smoke["gt_result_mismatch_count"],
        },
        "smoke_scenes": smoke["scenes"],
        "gates": gates,
        "DAY1_ENGINEERING_GATE": "PASS" if day2_authorized else "FAIL",
        "DAY2_AUTHORIZED": day2_authorized,
        "claim_boundaries": {
            "odi_modified": False,
            "fast_lio2_modified": False,
            "second_dataset_used": False,
            "vision_used": False,
            "new_measurement_paper_claimed_complete": False,
        },
        "output_files": list(REQUIRED_OUTPUT_FILES),
    }
    _write_json(result_dir / "run_manifest.json", manifest)
    _write_sha256sums(result_dir)
    _copy_summary_artifact(result_dir, current_artifact)
    return {
        "result_dir": str(result_dir),
        "artifact_dir": str(current_artifact),
        "manifest": manifest,
    }


def _perturbation_specs(
    snapshot_id: str, protocol: Mapping[str, Any]
) -> Iterable[PerturbationSpec]:
    global_seed = int(protocol["randomness"]["global_seed"])
    repeats = int(protocol["sampling"]["repeats_per_direction_amplitude"])
    for perturbation_type in ("translation", "rotation"):
        family = protocol["sampling"][perturbation_type]
        if perturbation_type == "translation":
            amplitudes = [float(value) for value in family["amplitudes"]]
        else:
            amplitudes = [float(value) for value in family["amplitudes_rad"]]
        for direction in family["directions"]:
            direction_id = str(direction["direction_id"])
            signed_side = int(direction["signed_side"])
            # The basis is canonical; signed_amplitude is the only numerical sign.
            canonical_direction = np.abs(np.asarray(direction["vector"], dtype=np.float64))
            for amplitude in amplitudes:
                signed_amplitude = float(signed_side * amplitude)
                for repeat_index in range(repeats):
                    seed = derive_trial_seed(
                        snapshot_id,
                        perturbation_type,
                        direction_id,
                        signed_amplitude,
                        repeat_index,
                        global_seed,
                    )
                    yield PerturbationSpec(
                        perturbation_type=perturbation_type,
                        direction=canonical_direction,
                        signed_amplitude=signed_amplitude,
                        repeat_index=repeat_index,
                        seed=seed,
                        direction_id=direction_id,
                        signed_side=signed_side,
                    )


def _trial_row(
    result: RecoveryTrialResult,
    perturbation: PerturbationSpec,
    provenance: Mapping[str, str],
) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for field in fields(RecoveryTrialResult):
        value = getattr(result, field.name)
        if isinstance(value, np.ndarray):
            row[field.name] = json.dumps(value.tolist(), separators=(",", ":"), allow_nan=True)
        elif isinstance(value, tuple):
            row[field.name] = json.dumps(list(value), separators=(",", ":"))
        else:
            row[field.name] = value
    row.update(
        {
            "registration_path": "full_reassociation"
            if result.full_reassociation
            else "frozen_jacobian",
            "measurement_role": "formal" if result.full_reassociation else "baseline_only",
            "amplitude": perturbation.amplitude,
            "seed": perturbation.seed,
            "direction_x": perturbation.signed_side * perturbation.direction[0],
            "direction_y": perturbation.signed_side * perturbation.direction[1],
            "direction_z": perturbation.signed_side * perturbation.direction[2],
            **dict(provenance),
        }
    )
    return row


def _build_curves(
    records: Sequence[tuple[RecoveryTrialResult, PerturbationSpec, dict[str, str]]],
    protocol: Mapping[str, Any],
) -> tuple[list[DirectionRecoveryCurve], dict[tuple[Any, ...], tuple[np.ndarray, np.ndarray]]]:
    grouped: dict[tuple[Any, ...], list[tuple[RecoveryTrialResult, PerturbationSpec]]] = {}
    for result, perturbation, _ in records:
        path = "full_reassociation" if result.full_reassociation else "frozen_jacobian"
        key = (
            result.snapshot_id,
            result.perturbation_type,
            result.direction_id,
            int(perturbation.signed_side),
            path,
        )
        grouped.setdefault(key, []).append((result, perturbation))
    curves: list[DirectionRecoveryCurve] = []
    counts: dict[tuple[Any, ...], tuple[np.ndarray, np.ndarray]] = {}
    confidence = float(
        protocol["recovery_probability"]["confidence_interval"]["confidence_level"]
    )
    for key in sorted(grouped):
        values = grouped[key]
        amplitudes = np.asarray(sorted({spec.amplitude for _, spec in values}), dtype=float)
        successes = np.asarray(
            [sum(result.success for result, spec in values if spec.amplitude == amplitude) for amplitude in amplitudes],
            dtype=int,
        )
        totals = np.asarray(
            [sum(spec.amplitude == amplitude for _, spec in values) for amplitude in amplitudes],
            dtype=int,
        )
        sample_spec = values[0][1]
        full = key[4] == "full_reassociation"
        curve = build_direction_recovery_curve(
            direction_id=key[2],
            direction=sample_spec.direction * sample_spec.signed_side,
            signed_side=sample_spec.signed_side,
            amplitudes=amplitudes,
            successful_trials=successes,
            total_trials=totals,
            confidence_level=confidence,
            snapshot_id=key[0],
            perturbation_type=key[1],
            registration_path=key[4],
            full_reassociation=full,
            baseline_only=not full,
        )
        curves.append(curve)
        counts[curve.direction_group_key] = (successes, totals)
    return curves, counts


def _direction_curve_rows(
    curves: Sequence[DirectionRecoveryCurve],
    counts: Mapping[tuple[Any, ...], tuple[np.ndarray, np.ndarray]],
) -> list[dict[str, Any]]:
    rows = []
    for curve in curves:
        successes, totals = counts[curve.direction_group_key]
        for index, amplitude in enumerate(curve.amplitudes):
            rows.append(
                {
                    "snapshot_id": curve.snapshot_id,
                    "perturbation_type": curve.perturbation_type,
                    "registration_path": curve.registration_path,
                    "measurement_role": "formal" if curve.full_reassociation else "baseline_only",
                    "direction_id": curve.direction_id,
                    "signed_side": curve.signed_side,
                    "direction_x": curve.direction[0],
                    "direction_y": curve.direction[1],
                    "direction_z": curve.direction[2],
                    "amplitude": amplitude,
                    "successful_trials": int(successes[index]),
                    "total_trials": int(totals[index]),
                    "raw_probability": curve.raw_probabilities[index],
                    "fitted_probability": curve.fitted_probabilities[index],
                    "wilson_lower": curve.wilson_lower[index],
                    "wilson_upper": curve.wilson_upper[index],
                    "raw_preserved": True,
                }
            )
    return rows


def _capture_radius_rows(curves: Sequence[DirectionRecoveryCurve]) -> list[dict[str, Any]]:
    rows = []
    for curve in curves:
        rows.append(
            {
                "snapshot_id": curve.snapshot_id,
                "perturbation_type": curve.perturbation_type,
                "registration_path": curve.registration_path,
                "measurement_role": "formal" if curve.full_reassociation else "baseline_only",
                "direction_id": curve.direction_id,
                "signed_side": curve.signed_side,
                "direction_x": curve.direction[0],
                "direction_y": curve.direction[1],
                "direction_z": curve.direction[2],
                "amplitude_unit": "meter" if curve.perturbation_type == "translation" else "radian",
                "d50": curve.d50,
                "d90": curve.d90,
                "d50_right_censored": curve.d50_right_censored,
                "d90_right_censored": curve.d90_right_censored,
                "raw_nonmonotonic": bool(np.any(np.diff(curve.raw_probabilities) > 0.0)),
                "interpolation": "none",
                "extrapolated": False,
            }
        )
    return rows


def _runtime_rows(
    records: Sequence[tuple[RecoveryTrialResult, PerturbationSpec, dict[str, str]]]
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[RecoveryTrialResult]] = {}
    for result, _, _ in records:
        path = "full_reassociation" if result.full_reassociation else "frozen_jacobian"
        grouped.setdefault((result.snapshot_id, result.perturbation_type, path), []).append(result)
    rows = []
    for key in sorted(grouped):
        values = grouped[key]
        runtimes = np.asarray([value.runtime_ms for value in values], dtype=float)
        rows.append(
            {
                "snapshot_id": key[0],
                "perturbation_type": key[1],
                "registration_path": key[2],
                "trial_count": len(values),
                "runtime_mean_ms": float(np.mean(runtimes)),
                "runtime_median_ms": float(np.median(runtimes)),
                "runtime_total_ms": float(np.sum(runtimes)),
                "iteration_total": sum(value.iteration_count for value in values),
                "full_reassociation_count": sum(value.full_reassociation_count for value in values),
                "transform_count": sum(value.transform_count for value in values),
                "nearest_neighbor_search_count": sum(
                    value.nearest_neighbor_search_count for value in values
                ),
                "correspondence_build_count": sum(
                    value.correspondence_build_count for value in values
                ),
                "plane_fit_count": sum(value.plane_fit_count for value in values),
                "jacobian_recomputation_count": sum(
                    value.jacobian_recomputation_count for value in values
                ),
            }
        )
    return rows


class _GTAccessAuditDict(dict):
    """Count attempts to read fields forbidden to the registration path."""

    forbidden = frozenset({"ground_truth_weak_direction", "pose_gt", "axis_gt"})

    def __init__(self, value: Mapping[str, Any]):
        super().__init__(value)
        self.access_count = 0

    def _record(self, key: Any) -> None:
        if key in self.forbidden:
            self.access_count += 1

    def __getitem__(self, key: str) -> Any:
        self._record(key)
        return super().__getitem__(key)

    def get(self, key: str, default: Any = None) -> Any:
        self._record(key)
        return super().get(key, default)

    def items(self):
        self.access_count += len(self.forbidden.intersection(self.keys()))
        return super().items()

    def values(self):
        self.access_count += len(self.forbidden.intersection(self.keys()))
        return super().values()


def _run_reproducibility_and_gt_audit(
    snapshots: Sequence[RegistrationSnapshot],
    records: Sequence[tuple[RecoveryTrialResult, PerturbationSpec, dict[str, str]]],
) -> dict[str, int]:
    if not snapshots or not records:
        raise ValueError("reproducibility audit requires completed smoke trials")
    snapshot = snapshots[0]
    formal_result, perturbation, _ = next(
        record
        for record in records
        if record[0].full_reassociation
        and record[0].snapshot_id == snapshot.snapshot_id
        and record[1].perturbation_type == "translation"
        and record[1].direction_id == "+x"
        and math.isclose(record[1].amplitude, 0.10, rel_tol=0.0, abs_tol=1.0e-15)
        and record[1].repeat_index == 0
    )
    baseline_result, _, _ = next(
        record
        for record in records
        if record[0].baseline_only
        and record[0].snapshot_id == snapshot.snapshot_id
        and record[1].direction_group_key == perturbation.direction_group_key
        and record[1].signed_amplitude == perturbation.signed_amplitude
        and record[1].repeat_index == perturbation.repeat_index
    )

    repeated_formal = run_full_reassociation_trial(snapshot, perturbation)
    repeated_baseline = run_frozen_jacobian_trial(
        snapshot,
        perturbation,
        baseline=prepare_frozen_jacobian_baseline(snapshot),
    )
    deterministic_mismatches = int(
        not _scientific_trial_results_equal(formal_result, repeated_formal)
    ) + int(not _scientific_trial_results_equal(baseline_result, repeated_baseline))

    poisoned = RegistrationSnapshot(
        snapshot_id=snapshot.snapshot_id,
        scan_points=snapshot.scan_points,
        local_map_points=snapshot.local_map_points,
        reference_pose=snapshot.reference_pose,
        registration_config=snapshot.registration_config,
        metadata=dict(snapshot.metadata),
    )
    audited_metadata = _GTAccessAuditDict(
        {
            **dict(snapshot.metadata),
            "ground_truth_weak_direction": [9.0e99, -9.0e99, 3.0e99],
            "pose_gt": [[-7.0e88]],
            "axis_gt": [5.0e77, 4.0e77, -6.0e77],
        }
    )
    # This mapping exists only for the runtime access audit.  RegistrationSnapshot
    # remains frozen for all measurement data used by actual trials.
    object.__setattr__(poisoned, "metadata", audited_metadata)
    poisoned_result = run_full_reassociation_trial(poisoned, perturbation)
    return {
        "determinism_rerun_count": 2,
        "deterministic_output_mismatch_count": deterministic_mismatches,
        "optimizer_gt_access_count": audited_metadata.access_count,
        "gt_result_mismatch_count": int(
            not _scientific_trial_results_equal(formal_result, poisoned_result)
        ),
    }


def _scientific_trial_results_equal(
    left: RecoveryTrialResult, right: RecoveryTrialResult
) -> bool:
    for field in fields(RecoveryTrialResult):
        if field.name == "runtime_ms":
            continue
        a = getattr(left, field.name)
        b = getattr(right, field.name)
        if isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
            if not np.array_equal(np.asarray(a), np.asarray(b), equal_nan=True):
                return False
        elif isinstance(a, float) or isinstance(b, float):
            if not (
                (math.isnan(float(a)) and math.isnan(float(b)))
                or float(a) == float(b)
            ):
                return False
        elif a != b:
            return False
    return True


def _evaluate_smoke(
    records: Sequence[tuple[RecoveryTrialResult, PerturbationSpec, dict[str, str]]],
    seed_derivation_mismatch_count: int,
    reproducibility_audit: Mapping[str, int],
) -> dict[str, Any]:
    formal = [(result, spec) for result, spec, _ in records if result.full_reassociation]
    baseline = [(result, spec) for result, spec, _ in records if result.baseline_only]
    box_small = [
        result
        for result, spec in formal
        if result.snapshot_id == "day1_geometry_rich_box"
        and (
            (spec.perturbation_type == "translation" and spec.amplitude <= 0.05 + 1.0e-12)
            or (
                spec.perturbation_type == "rotation"
                and spec.amplitude <= math.radians(1.0) + 1.0e-12
            )
        )
    ]
    corridor_axial = [
        result
        for result, spec in formal
        if result.snapshot_id == "day1_long_corridor"
        and spec.perturbation_type == "translation"
        and spec.direction_id in {"+x", "-x"}
        and spec.amplitude >= 0.05 - 1.0e-12
    ]
    corridor_transverse = [
        result
        for result, spec in formal
        if result.snapshot_id == "day1_long_corridor"
        and spec.perturbation_type == "translation"
        and spec.direction_id in {"+y", "-y", "+z", "-z"}
        and spec.amplitude >= 0.05 - 1.0e-12
    ]
    box_rate = _success_rate(box_small)
    axial_rate = _success_rate(corridor_axial)
    transverse_rate = _success_rate(corridor_transverse)
    full_verified = bool(
        formal
        and all(
            result.full_reassociation_count >= 1
            and result.transform_count == result.full_reassociation_count
            and result.nearest_neighbor_search_count == result.full_reassociation_count
            and result.correspondence_build_count == result.full_reassociation_count
            and result.plane_fit_count == result.full_reassociation_count
            and result.jacobian_recomputation_count == result.full_reassociation_count
            and not result.baseline_only
            for result, _ in formal
        )
    )
    baseline_isolated = bool(
        baseline
        and all(
            not result.full_reassociation
            and result.baseline_only
            and result.full_reassociation_count == 0
            and result.transform_count == 0
            and result.nearest_neighbor_search_count == 0
            and result.correspondence_build_count == 0
            and result.plane_fit_count == 0
            and result.jacobian_recomputation_count == 0
            for result, _ in baseline
        )
    )
    expected_per_path = len(SMOKE_SCENES) * 2 * 6 * 5 * 3
    counts_complete = len(formal) == expected_per_path and len(baseline) == expected_per_path
    box_pass = bool(box_rate > 0.5)
    corridor_pass = bool(axial_rate < transverse_rate)
    scenes = {}
    for scene in SMOKE_SCENES:
        scene_results = [result for result, _ in formal if result.snapshot_id == f"day1_{scene}"]
        scenes[scene] = {
            "formal_trial_count": len(scene_results),
            "formal_success_rate": _success_rate(scene_results),
        }
    scenes["geometry_rich_box"]["small_perturbation_success_rate"] = box_rate
    scenes["geometry_rich_box"]["small_perturbation_majority_pass"] = box_pass
    scenes["long_corridor"]["axial_translation_success_rate"] = axial_rate
    scenes["long_corridor"]["transverse_translation_success_rate"] = transverse_rate
    scenes["long_corridor"]["axial_weaker_trend_pass"] = corridor_pass
    engineering_pass = bool(
        box_pass
        and corridor_pass
        and full_verified
        and baseline_isolated
        and counts_complete
        and seed_derivation_mismatch_count == 0
        and reproducibility_audit["deterministic_output_mismatch_count"] == 0
        and reproducibility_audit["optimizer_gt_access_count"] == 0
        and reproducibility_audit["gt_result_mismatch_count"] == 0
    )
    return {
        "engineering_pass": engineering_pass,
        "smoke_pipeline_pass": engineering_pass,
        "full_reassociation_verified": full_verified,
        "frozen_baseline_isolated": baseline_isolated,
        "optimizer_gt_access_count": reproducibility_audit["optimizer_gt_access_count"],
        "gt_result_mismatch_count": reproducibility_audit["gt_result_mismatch_count"],
        "seed_derivation_mismatch_count": seed_derivation_mismatch_count,
        "deterministic_output_mismatch_count": reproducibility_audit[
            "deterministic_output_mismatch_count"
        ],
        "counts_complete": counts_complete,
        "scenes": scenes,
    }


def _smoke_report(
    run_id: str,
    smoke: Mapping[str, Any],
    gates: Mapping[str, bool],
    day2_authorized: bool,
) -> str:
    box = smoke["scenes"]["geometry_rich_box"]
    corridor = smoke["scenes"]["long_corridor"]
    parallel = smoke["scenes"]["parallel_walls"]
    gate_lines = "\n".join(
        f"- {name}: {'true' if value else 'false'}" for name, value in gates.items()
    )
    return f"""# Directional Capture Range Day 1 Smoke Report

Run: `{run_id}`

This is an engineering smoke test of the Algorithm-Conditioned Empirical
Directional Capture Range engine.  It does not establish an algorithm-independent
property of a scene and does not complete a new Measurement paper.

## Frozen prior state

- STAGE2_GATE: FAIL
- TRANSITION: PIVOT

## Smoke scenes

- geometry_rich_box formal success rate: {box['formal_success_rate']:.6f}
- geometry_rich_box small-perturbation success rate: {box['small_perturbation_success_rate']:.6f}
- parallel_walls formal success rate: {parallel['formal_success_rate']:.6f}
- long_corridor formal success rate: {corridor['formal_success_rate']:.6f}
- long_corridor axial translation success rate: {corridor['axial_translation_success_rate']:.6f}
- long_corridor transverse translation success rate: {corridor['transverse_translation_success_rate']:.6f}
- long_corridor axial-weaker trend visible: {str(corridor['axial_weaker_trend_pass']).lower()}

## Engineering gate

{gate_lines}

- DAY1_ENGINEERING_GATE: {'PASS' if day2_authorized else 'FAIL'}
- DAY2_AUTHORIZED: {str(day2_authorized).lower()}
- optimizer GT access count: {smoke['optimizer_gt_access_count']}
- seed derivation mismatch count: {smoke['seed_derivation_mismatch_count']}
- deterministic output mismatch count: {smoke['deterministic_output_mismatch_count']}
- GT-result mismatch count: {smoke['gt_result_mismatch_count']}

No ODI formula, FAST-LIO2 estimator, second dataset, or visual input was modified or used.
"""


def _success_rate(results: Sequence[RecoveryTrialResult]) -> float:
    if not results:
        return float("nan")
    return float(np.mean([result.success for result in results]))


def _copy_summary_artifact(result_dir: Path, artifact_dir: Path) -> None:
    artifact_dir.mkdir(parents=True)
    for name in REQUIRED_OUTPUT_FILES:
        shutil.copy2(result_dir / name, artifact_dir / name)


def _write_sha256sums(output_dir: Path) -> None:
    names = [name for name in REQUIRED_OUTPUT_FILES if name != "SHA256SUMS"]
    lines = [f"{_sha256_file(output_dir / name)}  {name}" for name in names]
    _write_text(output_dir / "SHA256SUMS", "\n".join(lines))


def _require_new_output_directory(path: Path, *, label: str) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing {label} path: {path}")


def _assert_output_not_protected(root: Path, candidate: Path) -> None:
    resolved = candidate.resolve()
    for relative in PROTECTED_ARTIFACT_PATHS:
        protected = (root / relative).resolve()
        if _is_same_or_descendant(resolved, protected):
            raise ValueError(f"output path is inside protected artifact tree: {candidate}")


def _is_same_or_descendant(candidate: Path, parent: Path) -> bool:
    try:
        candidate.relative_to(parent)
    except ValueError:
        return False
    return True


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty required table: {path.name}")
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_output(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-c", f"safe.directory={root}", *arguments],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def _git_worktree_clean(root: Path) -> bool:
    return _git_output(root, "status", "--porcelain") == ""


def _relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


__all__ = ["REQUIRED_OUTPUT_FILES", "run_capture_range_smoke"]
