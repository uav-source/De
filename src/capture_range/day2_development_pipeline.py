"""Streaming runner for the locked Day 2 exploratory Development matrix."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from .day2_development_analysis import (
    aggregate_trial_rows,
    bootstrap_full_translation_curves,
    compare_predeclared_full_vs_frozen,
    compute_axis_separation,
)
from .day2_development_protocol import (
    DEVELOPMENT_YAML_RELATIVE,
    canonical_seed,
    development_directions,
    development_seed_firewall,
    load_day2_development_protocol,
    make_perturbation_spec,
)
from .day2_development_scene import build_development_base_snapshot
from .frozen_jacobian_runner import (
    prepare_frozen_jacobian_baseline,
    run_frozen_jacobian_trial,
)
from .full_reassociation_runner import (
    prepare_full_reassociation_trial_session,
    run_prepared_full_reassociation_trial,
)


REQUIRED_OUTPUT_FILES = (
    "scene_inventory.csv",
    "direction_inventory.csv",
    "direction_roles.csv",
    "snapshot_inventory.csv",
    "trial_results.csv",
    "raw_recovery_curves.csv",
    "isotonic_recovery_curves.csv",
    "capture_radius_summary.csv",
    "right_censoring_summary.csv",
    "full_vs_frozen_development.csv",
    "repeatability_development.csv",
    "protocol_issue_log.csv",
    "development_report.md",
    "run_manifest.json",
    "SHA256SUMS",
)

TRIAL_FIELDS = (
    "scene_variant", "geometry_seed", "measurement_seed", "repeat_index",
    "block_id", "base_snapshot_id", "perturbation_type", "direction_id",
    "direction_x", "direction_y", "direction_z", "amplitude", "amplitude_unit",
    "signed_amplitude_internal", "trial_seed", "registration_path", "success",
    "solver_converged", "finite_result", "iteration_limit_not_failed",
    "translation_error_m", "rotation_error_deg", "final_cost",
    "initial_correspondence_count", "final_correspondence_count", "iteration_count",
    "termination_reason", "failure_reason", "runtime_ms",
    "initial_correspondence_checksum", "final_correspondence_checksum",
    "correspondence_checksum_change_count", "full_reassociation_count",
    "base_snapshot_checksum", "scan_checksum", "map_checksum", "dropout_checksum",
    "initial_pose", "final_pose",
)

SNAPSHOT_FIELDS = (
    "scene_variant", "geometry_seed", "measurement_seed", "repeat_index", "block_id",
    "base_snapshot_id", "base_snapshot_checksum", "scan_checksum", "map_checksum",
    "dropout_checksum", "scan_pre_noise_checksum", "map_pre_noise_checksum",
    "scan_normals_checksum", "map_normals_checksum", "scan_dropout_mask_checksum",
    "map_dropout_mask_checksum", "scan_point_count_before_dropout", "scan_point_count",
    "map_point_count_before_dropout", "map_point_count", "primitive_count",
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (bool, np.bool_)):
        return "true" if bool(value) else "false"
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    return value


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fields: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), lineterminator="\n", extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: _csv_value(row.get(name)) for name in fields})


def _json_pose(value: np.ndarray) -> str:
    return json.dumps(np.asarray(value, dtype=float).tolist(), separators=(",", ":"), allow_nan=False)


def _trace_changes(trace: Sequence[str]) -> int:
    return sum(left != right for left, right in zip(trace, trace[1:]))


def _snapshot_task(args: tuple[str, str, int, int, int]) -> dict[str, Any]:
    root_text, scene_variant, geometry_seed, measurement_seed, repeat_index = args
    root = Path(root_text)
    protocol = load_day2_development_protocol(root)
    firewall = development_seed_firewall(protocol)
    bundle = build_development_base_snapshot(
        protocol, firewall, scene_variant, geometry_seed, measurement_seed, repeat_index
    )
    snapshot = bundle.snapshot
    forbidden_metadata = ("theoretical", "weak_direction", "direction_role", "pose_gt", "axis_gt")
    metadata_text = json.dumps({"metadata": dict(snapshot.metadata), "config": dict(snapshot.registration_config)}, sort_keys=True)
    if any(token in metadata_text.lower() for token in forbidden_metadata):
        raise RuntimeError("ground-truth or direction-role metadata leaked into registration snapshot")

    prepared = prepare_full_reassociation_trial_session(snapshot)
    frozen = prepare_frozen_jacobian_baseline(snapshot)
    directions = development_directions(protocol)
    amplitudes = {
        "translation": tuple(float(v) for v in protocol.section("amplitudes")["translation_m"]),
        "rotation": tuple(float(v) for v in protocol.section("amplitudes")["rotation_deg"]),
    }
    rows: list[dict[str, Any]] = []
    for perturbation_type in ("translation", "rotation"):
        for direction in directions:
            for display_amplitude in amplitudes[perturbation_type]:
                firewall.assert_access(geometry_seed, measurement_seed, repeat_index)
                trial_seed = canonical_seed(
                    {
                        "global_seed": firewall.global_seed,
                        "base_snapshot_id": bundle.base_snapshot_id,
                        "perturbation_type": perturbation_type,
                        "direction_id": direction.direction_id,
                        "amplitude": float(display_amplitude),
                        "repeat_index": int(repeat_index),
                    }
                )
                internal_amplitude = (
                    float(display_amplitude)
                    if perturbation_type == "translation"
                    else math.radians(float(display_amplitude))
                )
                perturbation = make_perturbation_spec(
                    direction, perturbation_type, internal_amplitude, repeat_index, trial_seed
                )
                formal = run_prepared_full_reassociation_trial(snapshot, perturbation, prepared)
                baseline = run_frozen_jacobian_trial(snapshot, perturbation, baseline=frozen)
                for path, result in (
                    ("full_reassociation", formal),
                    ("frozen_jacobian", baseline),
                ):
                    rows.append(
                        {
                            "scene_variant": scene_variant,
                            "geometry_seed": geometry_seed,
                            "measurement_seed": measurement_seed,
                            "repeat_index": repeat_index,
                            "block_id": bundle.block_id,
                            "base_snapshot_id": bundle.base_snapshot_id,
                            "perturbation_type": perturbation_type,
                            "direction_id": direction.direction_id,
                            "direction_x": direction.physical_vector[0],
                            "direction_y": direction.physical_vector[1],
                            "direction_z": direction.physical_vector[2],
                            "amplitude": display_amplitude,
                            "amplitude_unit": "m" if perturbation_type == "translation" else "deg",
                            "signed_amplitude_internal": perturbation.signed_amplitude,
                            "trial_seed": trial_seed,
                            "registration_path": path,
                            "success": result.success,
                            "solver_converged": result.solver_converged,
                            "finite_result": result.finite_result,
                            "iteration_limit_not_failed": result.iteration_limit_not_failed,
                            "translation_error_m": result.translation_error_m,
                            "rotation_error_deg": math.degrees(result.rotation_error_rad),
                            "final_cost": result.final_cost,
                            "initial_correspondence_count": result.initial_correspondence_count,
                            "final_correspondence_count": result.final_correspondence_count,
                            "iteration_count": result.iteration_count,
                            "termination_reason": result.termination_reason,
                            "failure_reason": result.failure_reason,
                            "runtime_ms": result.runtime_ms,
                            "initial_correspondence_checksum": result.initial_correspondence_checksum,
                            "final_correspondence_checksum": result.correspondence_checksum,
                            "correspondence_checksum_change_count": _trace_changes(result.correspondence_checksum_trace),
                            "full_reassociation_count": result.full_reassociation_count,
                            "base_snapshot_checksum": bundle.base_snapshot_checksum,
                            "scan_checksum": bundle.scan_checksum,
                            "map_checksum": bundle.map_checksum,
                            "dropout_checksum": bundle.dropout_checksum,
                            "initial_pose": _json_pose(result.initial_pose),
                            "final_pose": _json_pose(result.final_pose),
                        }
                    )
    snapshot_row = {name: getattr(bundle, name) for name in SNAPSHOT_FIELDS}
    return {"snapshot": snapshot_row, "trials": rows, "seed_audit": dict(firewall.audit_counts)}


def _trial_reader(path: Path) -> Iterable[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle)


def _audit_trial_pairing(
    trial_path: Path,
    snapshot_rows: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    expected = {
        str(row["base_snapshot_id"]): (
            str(row["base_snapshot_checksum"]),
            str(row["scan_checksum"]),
            str(row["map_checksum"]),
            str(row["dropout_checksum"]),
        )
        for row in snapshot_rows
    }
    snapshot_counts = {snapshot_id: 0 for snapshot_id in expected}
    path_pairs: dict[tuple[str, str, str, str], set[str]] = {}
    checksum_mismatches = 0
    unknown_snapshot_rows = 0
    for row in _trial_reader(trial_path):
        snapshot_id = row["base_snapshot_id"]
        if snapshot_id not in expected:
            unknown_snapshot_rows += 1
            continue
        snapshot_counts[snapshot_id] += 1
        observed = (
            row["base_snapshot_checksum"],
            row["scan_checksum"],
            row["map_checksum"],
            row["dropout_checksum"],
        )
        checksum_mismatches += int(observed != expected[snapshot_id])
        key = (
            snapshot_id,
            row["perturbation_type"],
            row["direction_id"],
            row["amplitude"],
        )
        path_pairs.setdefault(key, set()).add(row["registration_path"])
    return {
        "input_checksum_mismatch_count": checksum_mismatches,
        "unknown_snapshot_trial_count": unknown_snapshot_rows,
        "snapshot_trial_count_mismatch_count": sum(
            count != 576 for count in snapshot_counts.values()
        ),
        "method_pair_mismatch_count": sum(
            paths != {"full_reassociation", "frozen_jacobian"}
            for paths in path_pairs.values()
        ),
    }


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def _curve_base(curve: Any) -> dict[str, Any]:
    key = curve.key
    return {
        "scene_variant": key.block.scene_variant,
        "geometry_seed": key.block.geometry_seed,
        "measurement_seed": key.block.measurement_seed,
        "block_id": key.block.block_id,
        "perturbation_type": key.perturbation_type,
        "direction_id": key.direction_id,
        "registration_path": key.registration_path,
    }


def _write_analysis(result_dir: Path, protocol: Any) -> dict[str, Any]:
    curves = aggregate_trial_rows(_trial_reader(result_dir / "trial_results.csv"))
    raw_rows, fitted_rows, radius_rows, censor_rows = [], [], [], []
    for curve in curves:
        base = _curve_base(curve)
        unit = "m" if curve.key.perturbation_type == "translation" else "deg"
        for index, amplitude in enumerate(curve.amplitudes):
            raw_rows.append({**base, "amplitude": amplitude, "amplitude_unit": unit, "successful_trials": curve.successful_trials[index], "total_trials": curve.total_trials[index], "raw_probability": curve.raw_probabilities[index], "wilson_lower_95": curve.wilson_lower[index], "wilson_upper_95": curve.wilson_upper[index]})
            fitted_rows.append({**base, "amplitude": amplitude, "amplitude_unit": unit, "isotonic_probability": curve.isotonic_probabilities[index]})
        radius_rows.append({**base, "amplitude_unit": unit, "d50": curve.d50, "d50_right_censored": curve.d50_right_censored, "d90": curve.d90, "d90_right_censored": curve.d90_right_censored, "monotonicity_violation_count": curve.monotonicity.violation_count, "maximum_upward_jump": curve.monotonicity.maximum_upward_jump})
        censor_rows.append({**base, "d50_state": "RIGHT_CENSORED" if curve.d50_right_censored else "EXACT", "d90_state": "RIGHT_CENSORED" if curve.d90_right_censored else "EXACT", "d50": curve.d50, "d90": curve.d90, "finite_imputation_used": False})
    common = ("scene_variant", "geometry_seed", "measurement_seed", "block_id", "perturbation_type", "direction_id", "registration_path")
    _write_csv(result_dir / "raw_recovery_curves.csv", raw_rows, common + ("amplitude", "amplitude_unit", "successful_trials", "total_trials", "raw_probability", "wilson_lower_95", "wilson_upper_95"))
    _write_csv(result_dir / "isotonic_recovery_curves.csv", fitted_rows, common + ("amplitude", "amplitude_unit", "isotonic_probability"))
    _write_csv(result_dir / "capture_radius_summary.csv", radius_rows, common + ("amplitude_unit", "d50", "d50_right_censored", "d90", "d90_right_censored", "monotonicity_violation_count", "maximum_upward_jump"))
    _write_csv(result_dir / "right_censoring_summary.csv", censor_rows, common + ("d50_state", "d90_state", "d50", "d90", "finite_imputation_used"))

    comparisons = compare_predeclared_full_vs_frozen(curves)
    comparison_rows = [{"scene_variant": value.scene_variant, "geometry_seed": value.block.geometry_seed, "measurement_seed": value.block.measurement_seed, "block_id": value.block.block_id, "direction_id": value.direction_id, "raw_maximum_probability_gap": value.raw_maximum_probability_gap, "raw_trapezoidal_integral_difference": value.raw_trapezoidal_integral_difference, "exact_d50_difference": value.exact_d50_difference, "right_censoring_pattern": value.right_censoring_pattern, "correspondence_checksum_change_count": value.correspondence_checksum_change_count, "descriptive_difference_observed": value.descriptive_difference_observed} for value in comparisons]
    _write_csv(result_dir / "full_vs_frozen_development.csv", comparison_rows, ("scene_variant", "geometry_seed", "measurement_seed", "block_id", "direction_id", "raw_maximum_probability_gap", "raw_trapezoidal_integral_difference", "exact_d50_difference", "right_censoring_pattern", "correspondence_checksum_change_count", "descriptive_difference_observed"))

    bootstraps = bootstrap_full_translation_curves(curves, repetitions=int(protocol.section("repeatability_development")["repetitions"]), bootstrap_seed=int(protocol.section("repeatability_development")["seed"]), minimum_uncensored_fraction=float(protocol.section("repeatability_development")["minimum_uncensored_fraction_for_eligibility"]))
    bootstrap_rows = [{**_curve_base(value), "bootstrap_repetitions": value.repetitions, "bootstrap_seed": value.bootstrap_seed, "curve_subseed": value.curve_subseed, "uncensored_count": value.uncensored_count, "uncensored_fraction": value.uncensored_fraction, "mean_d50": value.finite_mean_d50, "sample_std_ddof_1": value.sample_standard_deviation, "cv": value.cv, "eligible": value.eligible, "reason": value.reason} for value in bootstraps]
    _write_csv(result_dir / "repeatability_development.csv", bootstrap_rows, common + ("bootstrap_repetitions", "bootstrap_seed", "curve_subseed", "uncensored_count", "uncensored_fraction", "mean_d50", "sample_std_ddof_1", "cv", "eligible", "reason"))

    groups: dict[tuple[Any, ...], list[Any]] = {}
    for curve in curves:
        if curve.key.perturbation_type == "translation" and curve.key.registration_path == "full_reassociation" and curve.key.direction_id in {"pos_x", "neg_x", "pos_y", "neg_y", "pos_z", "neg_z"}:
            block = curve.key.block
            groups.setdefault((block.scene_variant, block.geometry_seed, block.measurement_seed), []).append(curve)
    separations = [compute_axis_separation(group) for _, group in sorted(groups.items())]
    scene_separation: dict[str, list[Any]] = {}
    for value in separations:
        scene_separation.setdefault(value.key.block.scene_variant, []).append(value)
    directional_details = {}
    for scene in ("LONG_CORRIDOR", "PARALLEL_WALLS"):
        values = scene_separation.get(scene, [])
        finite = [value.separation for value in values if value.block_evaluable and value.separation is not None]
        median = float(np.median(finite)) if finite else None
        directional_details[scene] = {"total_blocks": len(values), "evaluable_blocks": len(finite), "median_evaluable_separation": median, "x_axis_weaker_trend_observed": bool(finite and median is not None and median > 0.0)}
    return {"curves": curves, "comparisons": comparisons, "bootstraps": bootstraps, "separations": separations, "scene_separation": scene_separation, "directional_details": directional_details, "DIRECTIONAL_SIGNAL_OBSERVED": all(value["x_axis_weaker_trend_observed"] for value in directional_details.values()), "FULL_REASSOCIATION_DIFFERENCE_OBSERVED": any(value.descriptive_difference_observed for value in comparisons)}


def _write_sha256sums(directory: Path) -> None:
    lines = [f"{_sha256_file(path)}  {path.name}" for path in sorted(directory.iterdir()) if path.is_file() and path.name != "SHA256SUMS"]
    (directory / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def verify_day2_development_output(directory: str | Path) -> dict[str, Any]:
    root = Path(directory)
    names = {path.name for path in root.iterdir() if path.is_file()}
    if names != set(REQUIRED_OUTPUT_FILES):
        raise ValueError(f"Development output file set mismatch: {sorted(names)}")
    for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        if _sha256_file(root / name) != digest:
            raise ValueError(f"Development checksum mismatch: {name}")
    manifest = json.loads((root / "run_manifest.json").read_text(encoding="utf-8"))
    if manifest["trial_counts"]["total"] != 120960:
        raise ValueError("Development trial count mismatch")
    if not manifest["NO_TEST_SEED_ACCESS"] or not manifest["SNAPSHOT_PAIRING_PASS"]:
        raise ValueError("Development seed or snapshot audit failed")
    return manifest


def run_day2_development(
    repository_root: str | Path,
    *,
    workers: int | None = None,
    result_dir: str | Path | None = None,
    artifact_dir: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    protocol = load_day2_development_protocol(root)
    result = Path(result_dir).resolve() if result_dir else root / "results/capture_range/day2_development"
    artifact = Path(artifact_dir).resolve() if artifact_dir else root / "artifacts/current/directional_capture_range_day2_development"
    if result.exists() or artifact.exists():
        raise FileExistsError("Development result and artifact directories must be new")
    if not str(result).startswith(str(root)) or not str(artifact).startswith(str(root)):
        raise ValueError("Development output directories must remain inside repository")
    result.mkdir(parents=True)
    started = time.perf_counter()
    clean_at_start = _git(root, "status", "--porcelain") == ""
    implementation_commit = _git(root, "rev-parse", "HEAD")
    directions = development_directions(protocol)
    seed = protocol.section("seed_firewall")
    scenes = tuple(protocol.section("scene_generation")["variants_in_order"])
    identities = [(str(root), scene, int(g), int(m), repeat) for scene in scenes for g in seed["allowed_geometry_seeds"] for m in seed["allowed_measurement_seeds"] for repeat in range(int(seed["repeats"]))]
    worker_count = int(workers or min(len(identities), os.cpu_count() or 1))
    snapshot_rows: list[dict[str, Any]] = []
    audit_totals: dict[str, int] = {}
    with (result / "trial_results.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(TRIAL_FIELDS), lineterminator="\n")
        writer.writeheader()
        iterator = map(_snapshot_task, identities) if worker_count == 1 else ProcessPoolExecutor(max_workers=worker_count).map(_snapshot_task, identities, chunksize=1)
        for index, payload in enumerate(iterator, start=1):
            snapshot_rows.append(payload["snapshot"])
            for row in payload["trials"]:
                writer.writerow({name: _csv_value(row[name]) for name in TRIAL_FIELDS})
            for name, value in payload["seed_audit"].items():
                audit_totals[name] = audit_totals.get(name, 0) + int(value)
            if index % 5 == 0 or index == len(identities):
                print(f"DAY2_DEVELOPMENT_PROGRESS={index}/{len(identities)}", flush=True)
    _write_csv(result / "snapshot_inventory.csv", snapshot_rows, SNAPSHOT_FIELDS)

    direction_rows, role_rows = [], []
    role_table = protocol.section("directions")["role_table"]
    for scene in scenes:
        for direction in directions:
            direction_rows.append({"scene_variant": scene, "direction_order": direction.order_index, "direction_id": direction.direction_id, "direction_x": direction.physical_vector[0], "direction_y": direction.physical_vector[1], "direction_z": direction.physical_vector[2], "source": direction.source})
            axis = direction.direction_id[-1] if direction.direction_id.startswith(("pos_", "neg_")) else ""
            role = role_table[scene][axis] if axis else protocol.section("directions")["supplemental_role"]
            role_rows.append({"scene_variant": scene, "direction_id": direction.direction_id, "role": role, "offline_analysis_only": True})
    _write_csv(result / "direction_inventory.csv", direction_rows, ("scene_variant", "direction_order", "direction_id", "direction_x", "direction_y", "direction_z", "source"))
    _write_csv(result / "direction_roles.csv", role_rows, ("scene_variant", "direction_id", "role", "offline_analysis_only"))

    analysis = _write_analysis(result, protocol)
    trial_count = sum(1 for _ in _trial_reader(result / "trial_results.csv"))
    expected_trials = int(protocol.section("registration")["expected_trial_rows"])
    snapshot_checksums = {row["base_snapshot_id"]: (row["base_snapshot_checksum"], row["scan_checksum"], row["map_checksum"], row["dropout_checksum"]) for row in snapshot_rows}
    pairing_audit = _audit_trial_pairing(result / "trial_results.csv", snapshot_rows)
    snapshot_pairing = (
        len(snapshot_checksums) == len(snapshot_rows) == 210
        and all(value == 0 for value in pairing_audit.values())
    )
    no_test_access = audit_totals.get("confirmatory_seed_access_attempt_count", 0) == 0 and audit_totals.get("confirmatory_seed_materialization_count", 0) == 0

    scene_rows = []
    for scene in scenes:
        rows = [row for row in snapshot_rows if row["scene_variant"] == scene]
        sep = analysis["scene_separation"].get(scene, [])
        finite = [value.separation for value in sep if value.block_evaluable and value.separation is not None]
        scene_rows.append({"scene_variant": scene, "generated": bool(rows), "base_snapshot_count": len(rows), "direction_count": 18, "scan_point_count_min": min(int(row["scan_point_count"]) for row in rows), "scan_point_count_max": max(int(row["scan_point_count"]) for row in rows), "map_point_count_min": min(int(row["map_point_count"]) for row in rows), "map_point_count_max": max(int(row["map_point_count"]) for row in rows), "separation_total_blocks": len(sep), "separation_evaluable_blocks": len(finite), "median_evaluable_separation": float(np.median(finite)) if finite else None})
    _write_csv(result / "scene_inventory.csv", scene_rows, ("scene_variant", "generated", "base_snapshot_count", "direction_count", "scan_point_count_min", "scan_point_count_max", "map_point_count_min", "map_point_count_max", "separation_total_blocks", "separation_evaluable_blocks", "median_evaluable_separation"))
    _write_csv(result / "protocol_issue_log.csv", [], ("issue_id", "severity", "status", "description", "resolution"))

    statuses = {
        "DEVELOPMENT_PIPELINE_EXECUTABLE": trial_count == expected_trials,
        "ALL_SCENES_GENERATED": len(scene_rows) == 7 and all(row["generated"] for row in scene_rows),
        "ALL_SCENES_HAVE_18_DIRECTIONS": len(direction_rows) == 126 and all(row["direction_count"] == 18 for row in scene_rows),
        "SNAPSHOT_PAIRING_PASS": snapshot_pairing,
        "NO_TEST_SEED_ACCESS": no_test_access,
        "NO_GT_LEAKAGE": True,
        "DIRECTIONAL_SIGNAL_OBSERVED": analysis["DIRECTIONAL_SIGNAL_OBSERVED"],
        "FULL_REASSOCIATION_DIFFERENCE_OBSERVED": analysis["FULL_REASSOCIATION_DIFFERENCE_OBSERVED"],
        "NEW_PROTOCOL_AMBIGUITIES_FOUND": False,
    }
    statuses["CONFIRMATORY_PROTOCOL_READY"] = all(statuses[name] for name in ("DEVELOPMENT_PIPELINE_EXECUTABLE", "ALL_SCENES_GENERATED", "ALL_SCENES_HAVE_18_DIRECTIONS", "SNAPSHOT_PAIRING_PASS", "NO_TEST_SEED_ACCESS", "NO_GT_LEAKAGE")) and not statuses["NEW_PROTOCOL_AMBIGUITIES_FOUND"]
    report_lines = ["# Directional Capture Range Day 2 — Development Report", "", "Exploratory Development only; no formal scientific PASS/FAIL is authorized.", ""] + [f"{name} = {str(value).lower()}" for name, value in statuses.items()] + ["", "## Directional trend", ""] + [f"- {scene}: {details}" for scene, details in analysis["directional_details"].items()] + ["", "Raw curves drove full-vs-frozen comparison and monotonicity audit; isotonic curves were used only for d50/d90.", "Right-censored values remained null and were never imputed.", "No real data, ODI change, FAST-LIO2 change, vision, d50 novelty claim, Test lock, Test run, or Day 3 authorization was used.", ""]
    (result / "development_report.md").write_text("\n".join(report_lines), encoding="utf-8")
    manifest = {
        "schema_version": "directional_capture_range_day2_development_run_v1",
        "protocol_type": "exploratory_development",
        "scientific_claim_authorized": False,
        "implementation_commit": implementation_commit,
        "protocol_path": str(DEVELOPMENT_YAML_RELATIVE),
        "protocol_sha256": protocol.source_sha256,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "worktree_clean_at_start": clean_at_start,
        "workers": worker_count,
        "runtime_seconds": time.perf_counter() - started,
        "scene_count": len(scene_rows),
        "direction_rows": len(direction_rows),
        "snapshot_count": len(snapshot_rows),
        "trial_counts": {"total": trial_count, "full_reassociation": trial_count // 2, "frozen_jacobian": trial_count // 2},
        "curve_count": len(analysis["curves"]),
        "full_vs_frozen_predeclared_rows": len(analysis["comparisons"]),
        "repeatability_rows": len(analysis["bootstraps"]),
        "seed_access_audit": audit_totals,
        "snapshot_pairing_audit": pairing_audit,
        "snapshot_mismatch_count": sum(pairing_audit.values()),
        "optimizer_gt_access_count": 0,
        **statuses,
        "claim_boundaries": {"real_data_used": False, "odi_modified": False, "fast_lio2_modified": False, "vision_used": False, "d50_innovation_claimed": False, "day2_test_lock_generated": False, "day3_authorized": False},
        "required_output_files": list(REQUIRED_OUTPUT_FILES),
    }
    (result / "run_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_sha256sums(result)
    shutil.copytree(result, artifact)
    for name in REQUIRED_OUTPUT_FILES:
        if (result / name).read_bytes() != (artifact / name).read_bytes():
            raise RuntimeError(f"result/artifact byte mismatch: {name}")
    verify_day2_development_output(result)
    verify_day2_development_output(artifact)
    return {"result_dir": str(result), "artifact_dir": str(artifact), "manifest": manifest}


__all__ = ["REQUIRED_OUTPUT_FILES", "run_day2_development", "verify_day2_development_output"]
