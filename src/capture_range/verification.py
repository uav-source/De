"""Fail-closed verification for Directional Capture Range Day 1 artifacts."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import subprocess
from dataclasses import fields
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from eval.directional_capture_contract import (
    DAY1_PROTOCOL_RELATIVE,
    FROZEN_AUDIT_STATUSES,
    FROZEN_PROTOCOL_SEMANTIC_SHA256,
    load_capture_range_protocol,
    protocol_semantic_sha256,
)

from .pipeline import REQUIRED_OUTPUT_FILES, _smoke_report
from .capture_radius import build_direction_recovery_curve
from .perturbation import apply_perturbation
from .randomness import derive_trial_seed, noise_checksum, perturbation_checksum
from .recovery_metrics import (
    evaluate_recovery_success,
    rotation_geodesic_error_rad,
    translation_error_m,
)
from .snapshot import SMOKE_SCENES, build_smoke_snapshots, snapshot_checksums
from .types import PerturbationSpec, RecoveryTrialResult, RegistrationSnapshot


_CAPTURE_RANGE_DESCENDANT_BRANCHES = frozenset(
    {
        "feature/directional-capture-range-mvp",
        "feature/directional-capture-range-day2-development",
        "audit/directional-capture-range-anchor-validity",
    }
)


DAY1_GATE_KEYS = frozenset(
    {
        "ENGINEERING_PASS",
        "PROTOCOL_LOCKED",
        "FULL_REASSOCIATION_VERIFIED",
        "FROZEN_JACOBIAN_BASELINE_ISOLATED",
        "NO_GT_LEAKAGE",
        "SEED_DETERMINISM_PASS",
        "SMOKE_PIPELINE_PASS",
        "WORKTREE_CLEAN",
    }
)

TRIAL_EXTRA_FIELDS = frozenset(
    {
        "registration_path",
        "measurement_role",
        "amplitude",
        "seed",
        "direction_x",
        "direction_y",
        "direction_z",
        "scan_checksum",
        "map_checksum",
        "reference_pose_checksum",
        "config_checksum",
        "perturbation_checksum",
        "noise_checksum",
    }
)
DIRECTION_CURVE_FIELDS = frozenset(
    {
        "snapshot_id",
        "perturbation_type",
        "registration_path",
        "measurement_role",
        "direction_id",
        "signed_side",
        "direction_x",
        "direction_y",
        "direction_z",
        "amplitude",
        "successful_trials",
        "total_trials",
        "raw_probability",
        "fitted_probability",
        "wilson_lower",
        "wilson_upper",
        "raw_preserved",
    }
)
CAPTURE_RADIUS_FIELDS = frozenset(
    {
        "snapshot_id",
        "perturbation_type",
        "registration_path",
        "measurement_role",
        "direction_id",
        "signed_side",
        "direction_x",
        "direction_y",
        "direction_z",
        "amplitude_unit",
        "d50",
        "d90",
        "d50_right_censored",
        "d90_right_censored",
        "raw_nonmonotonic",
        "interpolation",
        "extrapolated",
    }
)
RUNTIME_FIELDS = frozenset(
    {
        "snapshot_id",
        "perturbation_type",
        "registration_path",
        "trial_count",
        "runtime_mean_ms",
        "runtime_median_ms",
        "runtime_total_ms",
        "iteration_total",
        "full_reassociation_count",
        "transform_count",
        "nearest_neighbor_search_count",
        "correspondence_build_count",
        "plane_fit_count",
        "jacobian_recomputation_count",
    }
)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def verify_capture_range_day1(
    artifact_dir: str | Path,
    *,
    repository_root: str | Path | None = None,
    require_gate_pass: bool = True,
) -> dict[str, Any]:
    directory = Path(artifact_dir).resolve()
    actual_entries = {path.name for path in directory.iterdir()} if directory.is_dir() else set()
    if actual_entries != set(REQUIRED_OUTPUT_FILES):
        raise ValueError(
            "Day 1 artifact file set differs from the frozen contract: "
            f"expected={sorted(REQUIRED_OUTPUT_FILES)}, actual={sorted(actual_entries)}"
        )
    _verify_sha256sums(directory)
    protocol = _read_json(directory / "protocol_lock.json")
    manifest = _read_json(directory / "run_manifest.json")
    expected_protocol_lock_keys = {
        "schema_version",
        "protocol_locked",
        "formal_measurement_name",
        "source_path",
        "source_sha256",
        "semantic_sha256",
        "complete_frozen_protocol",
        "frozen_scientific_state",
        "measurement_object",
        "pose_perturbation",
        "success",
        "recovery_probability",
        "capture_radius",
        "sampling",
        "registration",
        "randomness",
        "ground_truth_boundary",
    }
    if set(protocol) != expected_protocol_lock_keys:
        raise ValueError("protocol-lock artifact schema changed")
    if protocol.get("schema_version") != "directional_capture_range_protocol_lock_v1":
        raise ValueError("protocol-lock artifact version changed")
    if protocol.get("protocol_locked") is not True:
        raise ValueError("protocol lock is not asserted")
    if protocol.get("source_path") != DAY1_PROTOCOL_RELATIVE.as_posix():
        raise ValueError("protocol lock source path changed")
    if not isinstance(protocol.get("source_sha256"), str) or not SHA256_PATTERN.fullmatch(
        protocol["source_sha256"]
    ):
        raise ValueError("protocol lock source checksum is invalid")
    if protocol.get("semantic_sha256") != FROZEN_PROTOCOL_SEMANTIC_SHA256:
        raise ValueError("protocol semantic hash does not match the frozen contract")
    complete_protocol = protocol.get("complete_frozen_protocol")
    if not isinstance(complete_protocol, dict) or protocol_semantic_sha256(
        complete_protocol
    ) != FROZEN_PROTOCOL_SEMANTIC_SHA256:
        raise ValueError("embedded complete protocol does not match the frozen semantic hash")
    if protocol.get("formal_measurement_name") != complete_protocol["protocol"][
        "formal_measurement_name"
    ]:
        raise ValueError("protocol-lock formal measurement name changed")
    for section in (
        "frozen_scientific_state",
        "measurement_object",
        "pose_perturbation",
        "success",
        "recovery_probability",
        "capture_radius",
        "sampling",
        "registration",
        "randomness",
        "ground_truth_boundary",
    ):
        if protocol.get(section) != complete_protocol.get(section):
            raise ValueError(f"protocol-lock section disagrees with embedded protocol: {section}")
    if manifest.get("protocol_semantic_sha256") != FROZEN_PROTOCOL_SEMANTIC_SHA256:
        raise ValueError("manifest protocol semantic hash changed")
    if manifest.get("protocol_source_sha256") != protocol.get("source_sha256"):
        raise ValueError("manifest and protocol-lock source hashes disagree")
    manifest_state = manifest.get("frozen_scientific_state")
    protocol_state = protocol.get("frozen_scientific_state")
    if manifest_state != protocol_state:
        raise ValueError("manifest did not retain the complete frozen scientific state")
    if not isinstance(manifest_state, dict) or any(
        manifest_state.get(name) != expected
        for name, expected in FROZEN_AUDIT_STATUSES.items()
    ):
        raise ValueError("canonical prior scientific status changed")

    trial_rows = _read_csv(directory / "trial_results.csv")
    curve_rows = _read_csv(directory / "direction_curves.csv")
    radius_rows = _read_csv(directory / "capture_radius_summary.csv")
    runtime_rows = _read_csv(directory / "runtime_summary.csv")
    if not trial_rows or not curve_rows or not radius_rows or not runtime_rows:
        raise ValueError("Day 1 required tables must be non-empty")
    snapshots = build_smoke_snapshots(complete_protocol)
    matrix = _verify_exact_trial_matrix(
        trial_rows, complete_protocol, snapshots, manifest
    )
    _verify_trial_isolation(trial_rows)
    _verify_success_contract(
        trial_rows,
        protocol["success"],
        {snapshot.snapshot_id: snapshot for snapshot in snapshots},
    )
    _verify_curve_products(
        trial_rows, curve_rows, radius_rows, complete_protocol
    )
    _verify_runtime_products(trial_rows, runtime_rows)
    smoke, gates = _verify_manifest_products(
        manifest, protocol, complete_protocol, trial_rows, matrix
    )

    computed_pass = all(gates.values())
    if require_gate_pass and not computed_pass:
        raise ValueError(f"Day 1 engineering gate failed: {gates}")
    expected_report = _smoke_report(
        str(manifest["run_id"]), smoke, gates, computed_pass
    ).rstrip() + "\n"
    if (directory / "smoke_report.md").read_text(encoding="utf-8") != expected_report:
        raise ValueError("smoke report does not match recomputed Day 1 evidence")
    worktree_clean_now = None
    if repository_root is not None:
        root = Path(repository_root).resolve()
        _verify_repository_source(root, protocol, manifest)
        worktree_clean_now = _git_clean(root)
        if require_gate_pass and not worktree_clean_now:
            raise ValueError("repository worktree is not clean")
    return {
        "verified": True,
        "artifact_dir": str(directory),
        "trial_count": len(trial_rows),
        "formal_trial_count": matrix["formal_count"],
        "baseline_trial_count": matrix["baseline_count"],
        "full_reassociation_execution_count": matrix["instrumentation"][
            "full_reassociation_execution_count"
        ],
        "optimizer_gt_access_count": 0,
        "seed_derivation_mismatch_count": matrix["seed_derivation_mismatch_count"],
        "deterministic_output_mismatch_count": 0,
        "day1_engineering_gate": manifest["DAY1_ENGINEERING_GATE"],
        "day2_authorized": bool(manifest["DAY2_AUTHORIZED"]),
        "worktree_clean_now": worktree_clean_now,
    }


def _verify_exact_trial_matrix(
    rows: list[dict[str, str]],
    protocol: Mapping[str, Any],
    snapshots: Sequence[RegistrationSnapshot],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    expected_fields = {field.name for field in fields(RecoveryTrialResult)} | set(
        TRIAL_EXTRA_FIELDS
    )
    _require_csv_schema(rows, expected_fields, "trial_results.csv")

    snapshot_by_id = {snapshot.snapshot_id: snapshot for snapshot in snapshots}
    if set(snapshot_by_id) != {f"day1_{scene}" for scene in SMOKE_SCENES}:
        raise ValueError("rebuilt Day 1 snapshot set is incomplete")
    expected_snapshot_manifest = []
    for snapshot in snapshots:
        expected_snapshot_manifest.append(
            {
                "snapshot_id": snapshot.snapshot_id,
                "scene_name": snapshot.metadata["scene_name"],
                "scan_point_count": int(snapshot.scan_points.shape[0]),
                "map_point_count": int(snapshot.local_map_points.shape[0]),
                **snapshot_checksums(snapshot),
            }
        )
    if manifest.get("snapshots") != expected_snapshot_manifest:
        raise ValueError("manifest snapshots do not match rebuilt locked smoke geometry")

    global_seed = int(protocol["randomness"]["global_seed"])
    empty_noise_checksum = noise_checksum(np.empty(0, dtype=np.float64))
    expected: dict[tuple[Any, ...], tuple[PerturbationSpec, np.ndarray]] = {}
    repeats = int(protocol["sampling"]["repeats_per_direction_amplitude"])
    for snapshot in snapshots:
        for perturbation_type in ("translation", "rotation"):
            family = protocol["sampling"][perturbation_type]
            amplitude_key = "amplitudes" if perturbation_type == "translation" else "amplitudes_rad"
            amplitudes = [float(value) for value in family[amplitude_key]]
            for direction_entry in family["directions"]:
                direction_id = str(direction_entry["direction_id"])
                side = int(direction_entry["signed_side"])
                physical_direction = np.asarray(direction_entry["vector"], dtype=np.float64)
                canonical_direction = np.abs(physical_direction)
                for amplitude in amplitudes:
                    signed_amplitude = float(side * amplitude)
                    for repeat_index in range(repeats):
                        seed = derive_trial_seed(
                            snapshot.snapshot_id,
                            perturbation_type,
                            direction_id,
                            signed_amplitude,
                            repeat_index,
                            global_seed,
                        )
                        spec = PerturbationSpec(
                            perturbation_type=perturbation_type,
                            direction=canonical_direction,
                            signed_amplitude=signed_amplitude,
                            repeat_index=repeat_index,
                            seed=seed,
                            direction_id=direction_id,
                            signed_side=side,
                        )
                        for path in ("full_reassociation", "frozen_jacobian"):
                            key = (
                                snapshot.snapshot_id,
                                perturbation_type,
                                path,
                                direction_id,
                                side,
                                signed_amplitude.hex(),
                                repeat_index,
                            )
                            if key in expected:
                                raise RuntimeError("internal duplicate in frozen Day 1 trial matrix")
                            expected[key] = (spec, physical_direction)

    observed: set[tuple[Any, ...]] = set()
    for row in rows:
        signed_amplitude = float(row["signed_amplitude"])
        key = (
            row["snapshot_id"],
            row["perturbation_type"],
            row["registration_path"],
            row["direction_id"],
            int(row["signed_side"]),
            signed_amplitude.hex(),
            int(row["repeat_index"]),
        )
        if key in observed:
            raise ValueError(f"duplicate trial identity: {key}")
        observed.add(key)
        expected_entry = expected.get(key)
        if expected_entry is None:
            raise ValueError(f"trial is outside the frozen Day 1 matrix: {key}")
        spec, physical_direction = expected_entry
        snapshot = snapshot_by_id[row["snapshot_id"]]
        expected_role = "formal" if row["registration_path"] == "full_reassociation" else "baseline_only"
        if row["measurement_role"] != expected_role:
            raise ValueError("registration path and measurement role disagree")
        _require_float_exact(row["amplitude"], spec.amplitude, "amplitude")
        if int(row["seed"]) != spec.seed:
            raise ValueError("trial seed differs from the frozen six-component derivation")
        observed_direction = np.asarray(
            [float(row["direction_x"]), float(row["direction_y"]), float(row["direction_z"])],
            dtype=np.float64,
        )
        if not np.array_equal(observed_direction, physical_direction):
            raise ValueError("trial direction vector differs from its frozen ID and side")
        checksums = snapshot_checksums(snapshot)
        for name, value in checksums.items():
            if row[name] != value:
                raise ValueError(f"trial snapshot provenance mismatch: {name}")
        if row["perturbation_checksum"] != perturbation_checksum(spec):
            raise ValueError("trial perturbation checksum mismatch")
        if row["noise_checksum"] != empty_noise_checksum:
            raise ValueError("trial noise checksum differs from the frozen no-noise input")
        runtime_ms = float(row["runtime_ms"])
        if not math.isfinite(runtime_ms) or runtime_ms < 0.0:
            raise ValueError("trial runtime must be finite and non-negative")
        expected_initial_pose = apply_perturbation(snapshot.reference_pose, spec)
        observed_initial_pose = _parse_pose(row["initial_pose"], "initial_pose")
        if not np.array_equal(observed_initial_pose, expected_initial_pose):
            raise ValueError("trial initial pose does not match the frozen perturbation")

    if observed != set(expected):
        missing = set(expected).difference(observed)
        raise ValueError(f"Day 1 trial matrix is incomplete; missing {len(missing)} trials")
    formal_count = sum(row["measurement_role"] == "formal" for row in rows)
    baseline_count = sum(row["measurement_role"] == "baseline_only" for row in rows)
    if (len(rows), formal_count, baseline_count) != (1080, 540, 540):
        raise ValueError("Day 1 trial matrix is not the exact 1080-row smoke grid")
    expected_trial_counts = {
        "total": 1080,
        "full_reassociation": 540,
        "frozen_jacobian": 540,
    }
    _require_exact_int_mapping(
        manifest.get("trial_counts"), expected_trial_counts, "manifest trial_counts"
    )

    formal_rows = [row for row in rows if row["measurement_role"] == "formal"]
    instrumentation = {
        "full_reassociation_execution_count": sum(
            int(row["full_reassociation_count"]) for row in formal_rows
        ),
        "transform_execution_count": sum(int(row["transform_count"]) for row in formal_rows),
        "nearest_neighbor_search_count": sum(
            int(row["nearest_neighbor_search_count"]) for row in formal_rows
        ),
        "correspondence_recomputation_count": sum(
            int(row["correspondence_build_count"]) for row in formal_rows
        ),
        "plane_recomputation_count": sum(int(row["plane_fit_count"]) for row in formal_rows),
        "jacobian_recomputation_count": sum(
            int(row["jacobian_recomputation_count"]) for row in formal_rows
        ),
        "optimizer_gt_access_count": 0,
        "gt_result_mismatch_count": 0,
    }
    _require_exact_int_mapping(
        manifest.get("instrumentation"), instrumentation, "manifest instrumentation"
    )
    return {
        "formal_count": formal_count,
        "baseline_count": baseline_count,
        "seed_derivation_mismatch_count": 0,
        "instrumentation": instrumentation,
    }


def _verify_trial_isolation(rows: list[dict[str, str]]) -> None:
    forbidden_headers = {"ground_truth_weak_direction", "pose_gt", "axis_gt"}
    if forbidden_headers.intersection(rows[0]):
        raise ValueError("optimizer-forbidden GT field leaked into trial table")
    for row in rows:
        formal = _csv_bool(row["full_reassociation"])
        baseline = _csv_bool(row["baseline_only"])
        reassociations = int(row["full_reassociation_count"])
        transforms = int(row["transform_count"])
        neighbor_searches = int(row["nearest_neighbor_search_count"])
        correspondence_builds = int(row["correspondence_build_count"])
        plane_fits = int(row["plane_fit_count"])
        jacobians = int(row["jacobian_recomputation_count"])
        if int(row["jacobian_recompute_count"]) != jacobians:
            raise ValueError("Jacobian counter aliases disagree")
        if int(row["correspondence_count"]) != int(row["final_correspondence_count"]):
            raise ValueError("final correspondence count aliases disagree")
        trace = _parse_checksum_trace(row["correspondence_checksum_trace"])
        for checksum_field in (
            "initial_correspondence_checksum",
            "correspondence_checksum",
        ):
            if not SHA256_PATTERN.fullmatch(row[checksum_field]):
                raise ValueError(f"invalid correspondence checksum: {checksum_field}")
        if row["measurement_role"] == "formal":
            if not formal or baseline or reassociations < 1:
                raise ValueError("formal trial is not a verified full-reassociation trial")
            if any(
                count != reassociations
                for count in (
                    transforms,
                    neighbor_searches,
                    correspondence_builds,
                    plane_fits,
                    jacobians,
                )
            ):
                raise ValueError("formal trial has incomplete reassociation pass counters")
            if not row["initial_correspondence_checksum"] or not row["correspondence_checksum"]:
                raise ValueError("formal trial is missing correspondence checksums")
            if reassociations != int(row["iteration_count"]) + 1:
                raise ValueError("formal reassociation count does not cover every iteration and final pass")
            if len(trace) != reassociations:
                raise ValueError("formal correspondence trace length does not match reassociation count")
            if trace[0] != row["initial_correspondence_checksum"] or trace[-1] != row[
                "correspondence_checksum"
            ]:
                raise ValueError("formal correspondence trace endpoints disagree")
        elif row["measurement_role"] == "baseline_only":
            if (
                formal
                or not baseline
                or reassociations
                or transforms
                or neighbor_searches
                or correspondence_builds
                or plane_fits
                or jacobians
            ):
                raise ValueError("frozen-Jacobian baseline is not isolated")
            if trace:
                raise ValueError("frozen-Jacobian trial contains a reassociation trace")
        else:
            raise ValueError("unknown measurement_role in trial table")
        iteration_limit_not_failed = _csv_bool(row["iteration_limit_not_failed"])
        if iteration_limit_not_failed is (row["termination_reason"] == "iteration_limit"):
            raise ValueError("iteration-limit status and termination reason disagree")
        if _csv_bool(row["success"]) and row["failure_reason"]:
            raise ValueError("successful trial contains a failure reason")
        if not _csv_bool(row["success"]) and not row["failure_reason"]:
            raise ValueError("failed trial is missing a failure reason")
        if _csv_bool(row["solver_converged"]) is not (
            row["termination_reason"] == "converged_step"
        ):
            raise ValueError("solver convergence flag and termination reason disagree")


def _verify_success_contract(
    trial_rows: list[dict[str, str]],
    success_config: Mapping[str, Any],
    snapshots: Mapping[str, RegistrationSnapshot],
) -> None:
    translation_threshold = float(success_config["translation_error_threshold_m"])
    rotation_threshold = float(success_config["rotation_geodesic_error_threshold_rad"])
    for row in trial_rows:
        snapshot = snapshots.get(row["snapshot_id"])
        if snapshot is None:
            raise ValueError("trial references an unknown snapshot")
        final_pose = _parse_pose(row["final_pose"], "final_pose", finite=False)
        if np.all(np.isfinite(final_pose)):
            recomputed_translation_error = translation_error_m(
                final_pose, snapshot.reference_pose
            )
            recomputed_rotation_error = rotation_geodesic_error_rad(
                final_pose, snapshot.reference_pose
            )
        else:
            recomputed_translation_error = float("nan")
            recomputed_rotation_error = float("nan")
        _require_float_close_or_nan(
            row["translation_error_m"],
            recomputed_translation_error,
            "translation_error_m",
        )
        _require_float_close_or_nan(
            row["rotation_error_rad"],
            recomputed_rotation_error,
            "rotation_error_rad",
        )
        recomputed_finite = bool(
            np.all(np.isfinite(final_pose))
            and math.isfinite(recomputed_translation_error)
            and math.isfinite(recomputed_rotation_error)
            and math.isfinite(float(row["final_cost"]))
        )
        if _csv_bool(row["finite_result"]) is not recomputed_finite:
            raise ValueError("trial finite_result does not match final pose, errors, and cost")
        expected = evaluate_recovery_success(
            recomputed_translation_error,
            recomputed_rotation_error,
            solver_converged=_csv_bool(row["solver_converged"]),
            finite_result=recomputed_finite,
            iteration_limit_not_failed=_csv_bool(row["iteration_limit_not_failed"]),
            translation_success_threshold_m=translation_threshold,
            rotation_success_threshold_rad=rotation_threshold,
        )
        if _csv_bool(row["success"]) is not expected:
            raise ValueError("trial success does not satisfy the frozen pose/convergence contract")


def _verify_curve_products(
    trial_rows: list[dict[str, str]],
    curve_rows: list[dict[str, str]],
    radius_rows: list[dict[str, str]],
    protocol: Mapping[str, Any],
) -> None:
    _require_csv_schema(curve_rows, DIRECTION_CURVE_FIELDS, "direction_curves.csv")
    _require_csv_schema(radius_rows, CAPTURE_RADIUS_FIELDS, "capture_radius_summary.csv")
    if len(curve_rows) != 360 or len(radius_rows) != 72:
        raise ValueError("Day 1 curve or radius table has an unexpected row count")
    if any(not _csv_bool(row["raw_preserved"]) for row in curve_rows):
        raise ValueError("raw recovery probability was not preserved")
    expected_directions: dict[str, dict[tuple[str, int], np.ndarray]] = {}
    expected_amplitudes: dict[str, np.ndarray] = {}
    for perturbation_type in ("translation", "rotation"):
        family = protocol["sampling"][perturbation_type]
        amplitude_key = "amplitudes" if perturbation_type == "translation" else "amplitudes_rad"
        expected_amplitudes[perturbation_type] = np.asarray(
            family[amplitude_key], dtype=np.float64
        )
        expected_directions[perturbation_type] = {
            (str(entry["direction_id"]), int(entry["signed_side"])): np.asarray(
                entry["vector"], dtype=np.float64
            )
            for entry in family["directions"]
        }
    snapshots = {row["snapshot_id"] for row in radius_rows}
    if snapshots != {f"day1_{scene}" for scene in SMOKE_SCENES}:
        raise ValueError("Day 1 smoke scene set changed")
    for snapshot_id in snapshots:
        for perturbation_type in ("translation", "rotation"):
            for path in ("full_reassociation", "frozen_jacobian"):
                subset = {
                    (row["direction_id"], int(row["signed_side"]))
                    for row in radius_rows
                    if (
                        row["snapshot_id"],
                        row["perturbation_type"],
                        row["registration_path"],
                    )
                    == (snapshot_id, perturbation_type, path)
                }
                if subset != set(expected_directions[perturbation_type]):
                    raise ValueError("signed direction curves were merged, relabeled, or omitted")

    trial_groups: dict[tuple[str, str, str, str, int], list[dict[str, str]]] = {}
    for row in trial_rows:
        key = (
            row["snapshot_id"],
            row["perturbation_type"],
            row["registration_path"],
            row["direction_id"],
            int(row["signed_side"]),
        )
        trial_groups.setdefault(key, []).append(row)
    curve_lookup: dict[tuple[str, str, str, str, int, float], dict[str, str]] = {}
    for row in curve_rows:
        key = (
            row["snapshot_id"],
            row["perturbation_type"],
            row["registration_path"],
            row["direction_id"],
            int(row["signed_side"]),
            float(row["amplitude"]),
        )
        if key in curve_lookup:
            raise ValueError("duplicate direction-curve amplitude row")
        curve_lookup[key] = row
    radius_lookup = {
        (
            row["snapshot_id"],
            row["perturbation_type"],
            row["registration_path"],
            row["direction_id"],
            int(row["signed_side"]),
        ): row
        for row in radius_rows
    }
    if len(radius_lookup) != len(radius_rows):
        raise ValueError("duplicate capture-radius summary row")
    if set(radius_lookup) != set(trial_groups):
        raise ValueError("capture-radius groups do not exactly match trial groups")

    for key, rows in trial_groups.items():
        amplitudes = np.asarray(sorted({float(row["amplitude"]) for row in rows}))
        successes = np.asarray(
            [
                sum(
                    _csv_bool(row["success"])
                    for row in rows
                    if float(row["amplitude"]) == amplitude
                )
                for amplitude in amplitudes
            ],
            dtype=int,
        )
        totals = np.asarray(
            [sum(float(row["amplitude"]) == amplitude for row in rows) for amplitude in amplitudes],
            dtype=int,
        )
        if not np.array_equal(amplitudes, expected_amplitudes[key[1]]) or np.any(totals != 3):
            raise ValueError("direction curve differs from the exact five-amplitude/three-repeat grid")
        sample_curve_row = curve_lookup[key + (float(amplitudes[0]),)]
        physical_direction = expected_directions[key[1]][(key[3], key[4])]
        full = key[2] == "full_reassociation"
        expected = build_direction_recovery_curve(
            direction_id=key[3],
            direction=physical_direction,
            signed_side=key[4],
            amplitudes=amplitudes,
            successful_trials=successes,
            total_trials=totals,
            snapshot_id=key[0],
            perturbation_type=key[1],
            registration_path=key[2],
            full_reassociation=full,
            baseline_only=not full,
            confidence_level=float(
                protocol["recovery_probability"]["confidence_interval"]["confidence_level"]
            ),
        )
        for index, amplitude in enumerate(amplitudes):
            observed = curve_lookup.get(key + (float(amplitude),))
            if observed is None:
                raise ValueError("missing direction-curve amplitude row")
            exact_counts = (
                int(observed["successful_trials"]),
                int(observed["total_trials"]),
            )
            if exact_counts != (int(successes[index]), int(totals[index])):
                raise ValueError("direction-curve trial counts do not match raw trials")
            expected_role = "formal" if full else "baseline_only"
            if observed["measurement_role"] != expected_role:
                raise ValueError("direction curve path and role disagree")
            observed_direction = np.asarray(
                [
                    float(observed["direction_x"]),
                    float(observed["direction_y"]),
                    float(observed["direction_z"]),
                ],
                dtype=np.float64,
            )
            if not np.array_equal(observed_direction, physical_direction):
                raise ValueError("direction curve vector differs from its frozen ID and side")
            for field, expected_value in (
                ("raw_probability", expected.raw_probabilities[index]),
                ("fitted_probability", expected.fitted_probabilities[index]),
                ("wilson_lower", expected.wilson_lower[index]),
                ("wilson_upper", expected.wilson_upper[index]),
            ):
                if not math.isclose(
                    float(observed[field]), float(expected_value), rel_tol=0.0, abs_tol=1.0e-12
                ):
                    raise ValueError(f"recomputed curve value mismatch: {field}")
        radius = radius_lookup.get(key)
        if radius is None:
            raise ValueError("missing capture-radius summary row")
        expected_role = "formal" if full else "baseline_only"
        if radius["measurement_role"] != expected_role:
            raise ValueError("capture-radius path and role disagree")
        radius_direction = np.asarray(
            [float(radius["direction_x"]), float(radius["direction_y"]), float(radius["direction_z"])],
            dtype=np.float64,
        )
        if not np.array_equal(radius_direction, physical_direction):
            raise ValueError("capture-radius vector differs from its frozen ID and side")
        expected_unit = "meter" if key[1] == "translation" else "radian"
        if radius["amplitude_unit"] != expected_unit:
            raise ValueError("capture-radius amplitude unit changed")
        _verify_radius_value(radius, "d50", expected.d50, expected.d50_right_censored)
        _verify_radius_value(radius, "d90", expected.d90, expected.d90_right_censored)
        expected_nonmonotonic = bool(np.any(np.diff(expected.raw_probabilities) > 0.0))
        if _csv_bool(radius["raw_nonmonotonic"]) is not expected_nonmonotonic:
            raise ValueError("raw nonmonotonic evidence flag is inconsistent")
        if radius["interpolation"] != "none" or _csv_bool(radius["extrapolated"]):
            raise ValueError("Day 1 radius interpolation/extrapolation contract changed")
    if len(curve_lookup) != len(trial_groups) * 5:
        raise ValueError("direction-curve table contains unreferenced rows")


def _verify_runtime_products(
    trial_rows: list[dict[str, str]], runtime_rows: list[dict[str, str]]
) -> None:
    _require_csv_schema(runtime_rows, RUNTIME_FIELDS, "runtime_summary.csv")
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in trial_rows:
        key = (row["snapshot_id"], row["perturbation_type"], row["registration_path"])
        grouped.setdefault(key, []).append(row)
    lookup: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in runtime_rows:
        key = (row["snapshot_id"], row["perturbation_type"], row["registration_path"])
        if key in lookup:
            raise ValueError("duplicate runtime summary group")
        lookup[key] = row
    if set(lookup) != set(grouped) or len(lookup) != 12:
        raise ValueError("runtime summary groups do not match the exact trial groups")

    for key, rows in grouped.items():
        observed = lookup[key]
        runtimes = np.asarray([float(row["runtime_ms"]) for row in rows], dtype=np.float64)
        expected_integers = {
            "trial_count": len(rows),
            "iteration_total": sum(int(row["iteration_count"]) for row in rows),
            "full_reassociation_count": sum(
                int(row["full_reassociation_count"]) for row in rows
            ),
            "transform_count": sum(int(row["transform_count"]) for row in rows),
            "nearest_neighbor_search_count": sum(
                int(row["nearest_neighbor_search_count"]) for row in rows
            ),
            "correspondence_build_count": sum(
                int(row["correspondence_build_count"]) for row in rows
            ),
            "plane_fit_count": sum(int(row["plane_fit_count"]) for row in rows),
            "jacobian_recomputation_count": sum(
                int(row["jacobian_recomputation_count"]) for row in rows
            ),
        }
        for name, expected in expected_integers.items():
            if int(observed[name]) != expected:
                raise ValueError(f"runtime summary count mismatch: {name}")
        for name, expected in (
            ("runtime_mean_ms", float(np.mean(runtimes))),
            ("runtime_median_ms", float(np.median(runtimes))),
            ("runtime_total_ms", float(np.sum(runtimes))),
        ):
            if not math.isclose(
                float(observed[name]), expected, rel_tol=1.0e-12, abs_tol=1.0e-9
            ):
                raise ValueError(f"runtime summary statistic mismatch: {name}")


def _verify_manifest_products(
    manifest: Mapping[str, Any],
    protocol_lock: Mapping[str, Any],
    protocol: Mapping[str, Any],
    trial_rows: list[dict[str, str]],
    matrix: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, bool]]:
    if manifest.get("schema_version") != "directional_capture_range_day1_run_manifest_v1":
        raise ValueError("manifest schema version changed")
    if not isinstance(manifest.get("run_id"), str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.-]*", manifest["run_id"]
    ):
        raise ValueError("manifest run_id is invalid")
    if manifest.get("formal_measurement_name") != protocol["protocol"][
        "formal_measurement_name"
    ]:
        raise ValueError("manifest formal measurement name changed")
    if manifest.get("phase") != "engineering_smoke_test_only":
        raise ValueError("manifest phase is not the Day 1 engineering smoke scope")
    if manifest.get("output_files") != list(REQUIRED_OUTPUT_FILES):
        raise ValueError("manifest output file list differs from the frozen contract")
    expected_claim_boundaries = {
        "odi_modified": False,
        "fast_lio2_modified": False,
        "second_dataset_used": False,
        "vision_used": False,
        "new_measurement_paper_claimed_complete": False,
    }
    if not _strict_json_equal(manifest.get("claim_boundaries"), expected_claim_boundaries):
        raise ValueError("manifest claim boundaries changed")

    git = manifest.get("git")
    if not isinstance(git, dict) or set(git) != {
        "branch",
        "commit",
        "worktree_clean_at_run_start",
    }:
        raise ValueError("manifest git provenance schema changed")
    if git["branch"] not in _CAPTURE_RANGE_DESCENDANT_BRANCHES:
        raise ValueError("Day 1 smoke was not run on an authorized capture-range branch")
    if not isinstance(git["commit"], str) or not re.fullmatch(r"[0-9a-f]{40}", git["commit"]):
        raise ValueError("manifest git commit is invalid")
    if type(git["worktree_clean_at_run_start"]) is not bool:
        raise ValueError("manifest run-start worktree state must be boolean")

    randomness = manifest.get("randomness")
    expected_randomness_keys = {
        "frozen_configuration",
        "global_seed",
        "method_name_in_seed",
        "seed_derivation_mismatch_count",
        "determinism_rerun_count",
        "deterministic_output_mismatch_count",
        "runtime_excluded_from_deterministic_output_comparison",
        "noise_enabled",
        "noise_checksum",
    }
    if not isinstance(randomness, dict) or set(randomness) != expected_randomness_keys:
        raise ValueError("manifest randomness schema changed")
    if randomness["frozen_configuration"] != protocol["randomness"]:
        raise ValueError("manifest randomness configuration differs from the protocol")
    expected_noise_checksum = noise_checksum(np.empty(0, dtype=np.float64))
    expected_randomness_scalars = {
        "global_seed": int(protocol["randomness"]["global_seed"]),
        "method_name_in_seed": False,
        "seed_derivation_mismatch_count": int(matrix["seed_derivation_mismatch_count"]),
        "determinism_rerun_count": 2,
        "deterministic_output_mismatch_count": 0,
        "runtime_excluded_from_deterministic_output_comparison": True,
        "noise_enabled": False,
        "noise_checksum": expected_noise_checksum,
    }
    for name, expected in expected_randomness_scalars.items():
        if type(randomness[name]) is not type(expected) or randomness[name] != expected:
            raise ValueError(f"manifest randomness evidence mismatch: {name}")

    instrumentation = matrix["instrumentation"]
    smoke = _recompute_smoke(trial_rows)
    if not _strict_json_close(manifest.get("smoke_scenes"), smoke["scenes"]):
        raise ValueError("manifest smoke-scene results do not match recomputed trials")
    gates = {
        "ENGINEERING_PASS": bool(smoke["engineering_pass"]),
        "PROTOCOL_LOCKED": bool(protocol_lock.get("protocol_locked") is True),
        "FULL_REASSOCIATION_VERIFIED": bool(smoke["full_reassociation_verified"]),
        "FROZEN_JACOBIAN_BASELINE_ISOLATED": bool(smoke["frozen_baseline_isolated"]),
        "NO_GT_LEAKAGE": bool(
            instrumentation["optimizer_gt_access_count"] == 0
            and instrumentation["gt_result_mismatch_count"] == 0
        ),
        "SEED_DETERMINISM_PASS": bool(
            matrix["seed_derivation_mismatch_count"] == 0
            and randomness["deterministic_output_mismatch_count"] == 0
        ),
        "SMOKE_PIPELINE_PASS": bool(smoke["smoke_pipeline_pass"]),
        "WORKTREE_CLEAN": bool(git["worktree_clean_at_run_start"]),
    }
    stored_gates = manifest.get("gates")
    if not isinstance(stored_gates, dict) or set(stored_gates) != DAY1_GATE_KEYS:
        raise ValueError("Day 1 gate schema is incomplete or contains extra fields")
    if not _strict_json_equal(stored_gates, gates):
        raise ValueError("stored Day 1 gates do not match recomputed evidence")
    computed_pass = all(gates.values())
    if manifest.get("DAY1_ENGINEERING_GATE") != ("PASS" if computed_pass else "FAIL"):
        raise ValueError("DAY1_ENGINEERING_GATE does not match recomputed evidence")
    if type(manifest.get("DAY2_AUTHORIZED")) is not bool or manifest.get(
        "DAY2_AUTHORIZED"
    ) is not computed_pass:
        raise ValueError("DAY2_AUTHORIZED does not match recomputed evidence")
    return smoke, gates


def _recompute_smoke(trial_rows: list[dict[str, str]]) -> dict[str, Any]:
    formal = [row for row in trial_rows if row["measurement_role"] == "formal"]
    baseline = [row for row in trial_rows if row["measurement_role"] == "baseline_only"]
    box_small = [
        row
        for row in formal
        if row["snapshot_id"] == "day1_geometry_rich_box"
        and (
            (row["perturbation_type"] == "translation" and float(row["amplitude"]) <= 0.05 + 1.0e-12)
            or (
                row["perturbation_type"] == "rotation"
                and float(row["amplitude"]) <= math.radians(1.0) + 1.0e-12
            )
        )
    ]
    corridor_axial = [
        row
        for row in formal
        if row["snapshot_id"] == "day1_long_corridor"
        and row["perturbation_type"] == "translation"
        and row["direction_id"] in {"+x", "-x"}
        and float(row["amplitude"]) >= 0.05 - 1.0e-12
    ]
    corridor_transverse = [
        row
        for row in formal
        if row["snapshot_id"] == "day1_long_corridor"
        and row["perturbation_type"] == "translation"
        and row["direction_id"] in {"+y", "-y", "+z", "-z"}
        and float(row["amplitude"]) >= 0.05 - 1.0e-12
    ]
    box_rate = _success_rate_rows(box_small)
    axial_rate = _success_rate_rows(corridor_axial)
    transverse_rate = _success_rate_rows(corridor_transverse)
    full_verified = bool(
        formal
        and all(
            int(row["full_reassociation_count"]) >= 1
            and int(row["transform_count"]) == int(row["full_reassociation_count"])
            and int(row["nearest_neighbor_search_count"])
            == int(row["full_reassociation_count"])
            and int(row["correspondence_build_count"])
            == int(row["full_reassociation_count"])
            and int(row["plane_fit_count"]) == int(row["full_reassociation_count"])
            and int(row["jacobian_recomputation_count"])
            == int(row["full_reassociation_count"])
            and _csv_bool(row["full_reassociation"])
            and not _csv_bool(row["baseline_only"])
            for row in formal
        )
    )
    baseline_isolated = bool(
        baseline
        and all(
            not _csv_bool(row["full_reassociation"])
            and _csv_bool(row["baseline_only"])
            and all(
                int(row[name]) == 0
                for name in (
                    "full_reassociation_count",
                    "transform_count",
                    "nearest_neighbor_search_count",
                    "correspondence_build_count",
                    "plane_fit_count",
                    "jacobian_recomputation_count",
                )
            )
            for row in baseline
        )
    )
    counts_complete = len(formal) == 540 and len(baseline) == 540
    box_pass = bool(box_rate > 0.5)
    corridor_pass = bool(axial_rate < transverse_rate)
    scenes: dict[str, Any] = {}
    for scene in SMOKE_SCENES:
        scene_rows = [row for row in formal if row["snapshot_id"] == f"day1_{scene}"]
        scenes[scene] = {
            "formal_trial_count": len(scene_rows),
            "formal_success_rate": _success_rate_rows(scene_rows),
        }
    scenes["geometry_rich_box"]["small_perturbation_success_rate"] = box_rate
    scenes["geometry_rich_box"]["small_perturbation_majority_pass"] = box_pass
    scenes["long_corridor"]["axial_translation_success_rate"] = axial_rate
    scenes["long_corridor"]["transverse_translation_success_rate"] = transverse_rate
    scenes["long_corridor"]["axial_weaker_trend_pass"] = corridor_pass
    engineering_pass = bool(
        box_pass and corridor_pass and full_verified and baseline_isolated and counts_complete
    )
    return {
        "engineering_pass": engineering_pass,
        "smoke_pipeline_pass": engineering_pass,
        "full_reassociation_verified": full_verified,
        "frozen_baseline_isolated": baseline_isolated,
        "optimizer_gt_access_count": 0,
        "gt_result_mismatch_count": 0,
        "seed_derivation_mismatch_count": 0,
        "deterministic_output_mismatch_count": 0,
        "counts_complete": counts_complete,
        "scenes": scenes,
    }


def _verify_radius_value(
    row: dict[str, str], name: str, expected_value: float | None, expected_censored: bool
) -> None:
    if _csv_bool(row[f"{name}_right_censored"]) is not expected_censored:
        raise ValueError(f"{name} right-censor flag mismatch")
    observed = row[name]
    if expected_value is None:
        if observed != "":
            raise ValueError(f"right-censored {name} must not contain an extrapolated value")
    elif not math.isclose(float(observed), expected_value, rel_tol=0.0, abs_tol=1.0e-12):
        raise ValueError(f"{name} value does not match the fitted curve")


def _verify_sha256sums(directory: Path) -> None:
    lines = (directory / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    expected_names = [name for name in REQUIRED_OUTPUT_FILES if name != "SHA256SUMS"]
    if len(lines) != len(expected_names):
        raise ValueError("SHA256SUMS must contain exactly one entry per hashed output")
    observed_names: list[str] = []
    for line, expected_name in zip(lines, expected_names):
        digest, separator, name = line.partition("  ")
        if (
            not separator
            or not name
            or name != expected_name
            or "/" in name
            or "\\" in name
            or not SHA256_PATTERN.fullmatch(digest)
        ):
            raise ValueError("invalid SHA256SUMS entry")
        observed_names.append(name)
        if _sha256_file(directory / name) != digest:
            raise ValueError(f"checksum mismatch: {name}")
    if observed_names != expected_names:
        raise ValueError("SHA256SUMS order or file set does not match the contract")


def _read_json(path: Path) -> dict[str, Any]:
    def unique_mapping(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, child in pairs:
            if key in value:
                raise ValueError(f"duplicate JSON key in {path.name}: {key}")
            value[key] = child
        return value

    def reject_constant(value: str) -> Any:
        raise ValueError(f"non-finite JSON constant in {path.name}: {value}")

    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=unique_mapping,
        parse_constant=reject_constant,
    )
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON mapping: {path.name}")
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        if not fieldnames or len(fieldnames) != len(set(fieldnames)):
            raise ValueError(f"CSV header is empty or contains duplicate fields: {path.name}")
        rows = list(reader)
        if any(None in row for row in rows):
            raise ValueError(f"CSV row contains fields outside its header: {path.name}")
        return rows


def _csv_bool(value: str) -> bool:
    if value == "True":
        return True
    if value == "False":
        return False
    raise ValueError(f"invalid CSV boolean: {value!r}")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_clean(root: Path) -> bool:
    output = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "status", "--porcelain"],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout
    return output.strip() == ""


def _require_csv_schema(
    rows: list[dict[str, str]], expected_fields: Sequence[str] | set[str] | frozenset[str], name: str
) -> None:
    if not rows or set(rows[0]) != set(expected_fields):
        actual = sorted(rows[0]) if rows else []
        raise ValueError(
            f"{name} schema differs from the frozen contract: "
            f"expected={sorted(expected_fields)}, actual={actual}"
        )
    if any(set(row) != set(expected_fields) for row in rows):
        raise ValueError(f"{name} contains an inconsistent row schema")


def _parse_pose(value: str, name: str, *, finite: bool = True) -> np.ndarray:
    try:
        pose = np.asarray(json.loads(value), dtype=np.float64)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid serialized pose: {name}") from exc
    if pose.shape not in {(8,), (4, 4)}:
        raise ValueError(f"{name} has an invalid shape")
    if finite and not np.all(np.isfinite(pose)):
        raise ValueError(f"{name} must be finite")
    return pose


def _parse_checksum_trace(value: str) -> tuple[str, ...]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("correspondence checksum trace is not JSON") from exc
    if not isinstance(parsed, list) or any(
        not isinstance(item, str) or not SHA256_PATTERN.fullmatch(item) for item in parsed
    ):
        raise ValueError("correspondence checksum trace is invalid")
    return tuple(parsed)


def _require_float_exact(value: str, expected: float, name: str) -> None:
    observed = float(value)
    if observed.hex() != float(expected).hex():
        raise ValueError(f"trial {name} differs from the frozen grid")


def _require_float_close_or_nan(value: str, expected: float, name: str) -> None:
    observed = float(value)
    if math.isnan(expected):
        if not math.isnan(observed):
            raise ValueError(f"recomputed trial value mismatch: {name}")
        return
    if not math.isclose(observed, expected, rel_tol=0.0, abs_tol=1.0e-12):
        raise ValueError(f"recomputed trial value mismatch: {name}")


def _require_exact_int_mapping(value: Any, expected: Mapping[str, int], name: str) -> None:
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError(f"{name} schema changed")
    for key, expected_value in expected.items():
        if type(value[key]) is not int or value[key] != expected_value:
            raise ValueError(f"{name} value mismatch: {key}")


def _strict_json_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(right, dict):
        return set(left) == set(right) and all(
            _strict_json_equal(left[key], value) for key, value in right.items()
        )
    if isinstance(right, list):
        return len(left) == len(right) and all(
            _strict_json_equal(a, b) for a, b in zip(left, right)
        )
    return left == right


def _strict_json_close(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(right, dict):
        return set(left) == set(right) and all(
            _strict_json_close(left[key], value) for key, value in right.items()
        )
    if isinstance(right, list):
        return len(left) == len(right) and all(
            _strict_json_close(a, b) for a, b in zip(left, right)
        )
    if isinstance(right, float):
        return math.isclose(left, right, rel_tol=0.0, abs_tol=1.0e-12)
    return left == right


def _success_rate_rows(rows: Sequence[Mapping[str, str]]) -> float:
    if not rows:
        return float("nan")
    return float(np.mean([_csv_bool(row["success"]) for row in rows]))


def _verify_repository_source(
    root: Path, protocol_lock: Mapping[str, Any], manifest: Mapping[str, Any]
) -> None:
    if protocol_lock.get("source_path") != DAY1_PROTOCOL_RELATIVE.as_posix():
        raise ValueError("protocol lock source path differs from the repository contract")
    source = root / DAY1_PROTOCOL_RELATIVE
    if not source.is_file() or _sha256_file(source) != protocol_lock.get("source_sha256"):
        raise ValueError("repository protocol source differs from the artifact lock")
    current = load_capture_range_protocol(source)
    if protocol_semantic_sha256(current) != FROZEN_PROTOCOL_SEMANTIC_SHA256:
        raise ValueError("repository protocol semantic lock changed")
    branch = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "branch", "--show-current"],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    if branch not in _CAPTURE_RANGE_DESCENDANT_BRANCHES:
        raise ValueError("repository is not on an authorized capture-range branch")
    ancestry = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={root}",
            "merge-base",
            "--is-ancestor",
            str(manifest["git"]["commit"]),
            "HEAD",
        ],
        cwd=root,
        text=True,
        capture_output=True,
    )
    if ancestry.returncode != 0:
        raise ValueError("manifest source commit is not an ancestor of repository HEAD")


__all__ = ["verify_capture_range_day1"]
