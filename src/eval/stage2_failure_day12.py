"""Read-only Stage 2 Day 12 input locking and four-figure pipeline."""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

import matplotlib
import numpy as np
import scipy
from PIL import __version__ as pillow_version

from eval.analysis_lock import compute_directory_hash, git_commit, git_status_clean
from eval.stage2_failure_day11b_provenance import result_tree_manifest
from eval.stage2_failure_day12_figure_qc import (
    audit_figures,
    audit_plot_code,
    compare_reproduction,
)
from eval.stage2_failure_day12_figures import generate_four_figures
from eval.stage2_failure_day12_input_audit import verify_day11b_v2_plot_input
from eval.stage2_failure_day12_plot_data import (
    build_all_plot_data,
    build_descriptive_summary,
    read_merged_rows,
    validate_plot_data,
    write_plot_data,
)
from eval.stage2_failure_day12_schema import (
    DAY12_SCHEMA_VERSION,
    DESCRIPTIVE_SUMMARY_FIELDS,
    EXPECTED_METHODS,
    EXPECTED_STRESSES,
    EXPECTED_SWEEPS,
    INPUT_LOCK_SCHEMA_VERSION,
    evaluate_day12_gate,
    write_csv,
)
from eval.synthetic_pipeline_common import load_yaml, write_json


DAY11B_V2_CHECKPOINT = "checkpoint/day11b-v2-provenance-pass"
DAY11B_V2_CHECKPOINT_COMMIT = "480960def270d2739a21bfc4967990318d2ed3c3"
HISTORICAL_PATHS = (
    "artifacts/current/detector_stage2a",
    "artifacts/history/stage2b_column_scaling_no_go",
    "artifacts/current/weak_update_stage2c",
)
CAPTIONS = """# Stage 2 Day 12 diagnostic figure captions

## Figure 1 — Innovation and frozen-window timelines

Displays `weak_innovation_z_huber` and `huber_window_mean` for every saved frame. NaN values remain curve breaks. Shading is derived only from saved `stress_active` rows.

## Figure 2 — Prior and posterior absolute axial error

Displays all saved `prior_axis_error_abs_m` and `posterior_axis_error_abs_m` values. Offline GT fields are used only where `offline_evaluation_only` is true. Shading is derived only from saved `stress_active` rows.

## Figure 3 — Current same-sign run timelines

Displays `huber_current_same_sign_run_length`; the historical maximum is not substituted and no run cutoff is defined. Shading is derived only from saved `stress_active` rows.

## Figure 4 — Clean/coherent descriptive distributions

Displays box summaries plus every included frame value with the preregistered deterministic horizontal displacement. Innovation and current-run values require `stat_input_valid`; window mean and CUSUM require `window_ready`. Frame-wise values are serially correlated and boxes are descriptive only.
This distribution figure uses saved `stress` groups and has no timeline shading; no stress interval is inferred from the plotted values.

These figures use two preregistered deterministic diagnostic cases.
They are not representative statistics and are not an independent test.
No threshold, AUROC, FPR, or Stage 2 decision is derived from them.
"""


def verify_day12_input(
    root: Path, day11b_run_dir: Path, run_id: str, output_root: Path,
    overwrite: bool = False,
) -> Mapping[str, Any]:
    root = Path(root).resolve()
    if not git_status_clean(root):
        raise RuntimeError("Day 12 requires a clean worktree at start")
    _validate_git_preconditions(root)
    config = _load_config(root)
    result_dir = Path(output_root).resolve() / str(run_id)
    _validate_output_path(day11b_run_dir, result_dir)
    if result_dir.exists() and overwrite:
        shutil.rmtree(result_dir)
    result_dir.mkdir(parents=True, exist_ok=True)
    audit = verify_day11b_v2_plot_input(root, day11b_run_dir)
    _write_input_audit(result_dir, audit)
    if not audit["DAY12_INPUT_AUDIT_PASS"]:
        raise RuntimeError("Day 12 input audit failed; figures are forbidden")
    lock = _build_input_lock(root, Path(day11b_run_dir).resolve(), result_dir, audit)
    write_json(result_dir / "day12_input_lock.json", lock)
    validate_input_lock(result_dir / "day12_input_lock.json")
    return {
        "result_dir": str(result_dir), "DAY12_INPUT_AUDIT_PASS": True,
        "day12_input_lock_sha256": _sha256(result_dir / "day12_input_lock.json"),
        "figures_generated": False, "config": config,
    }


def generate_day12_figures(
    root: Path, day11b_run_dir: Path, run_id: str, output_root: Path,
    overwrite: bool = False,
) -> Mapping[str, Any]:
    root = Path(root).resolve()
    clean_at_start = git_status_clean(root)
    if not clean_at_start:
        raise RuntimeError("Day 12 requires a clean worktree at start")
    _validate_git_preconditions(root)
    config = _load_config(root)
    result_dir = Path(output_root).resolve() / str(run_id)
    _validate_output_path(day11b_run_dir, result_dir)
    if result_dir.exists() and overwrite:
        shutil.rmtree(result_dir)
    result_dir.mkdir(parents=True, exist_ok=True)
    historical_before = _historical_hashes(root)
    audit = verify_day11b_v2_plot_input(root, day11b_run_dir)
    _write_input_audit(result_dir, audit)
    if not audit["DAY12_INPUT_AUDIT_PASS"]:
        raise RuntimeError("Day 12 input audit failed; figures are forbidden")
    lock = _build_input_lock(root, Path(day11b_run_dir).resolve(), result_dir, audit)
    write_json(result_dir / "day12_input_lock.json", lock)
    validate_input_lock(result_dir / "day12_input_lock.json")

    merged_path = Path(day11b_run_dir).resolve() / "replay_frame_diagnostics_merged.csv"
    merged_fields, merged_rows = read_merged_rows(merged_path)
    figure_data = build_all_plot_data(merged_fields, merged_rows)
    plot_files = write_plot_data(result_dir, figure_data)
    plot_validation = validate_plot_data(figure_data, merged_fields, merged_rows)
    plot_audits = []
    for record, validation in zip(plot_files["files"], plot_validation["audits"]):
        plot_audits.append({
            **validation, **record, "source_merged_sha256": audit["merged_csv_sha256"],
            "selection_rule": _selection_rule(record["figure_id"]),
            "audit_pass": bool(validation["audit_pass"]),
        })
    plot_audit = {
        "schema_version": "stage2_failure_day12_plot_data_audit_v2",
        "files": plot_audits, "plot_data_file_count": 4,
        "plot_data_audit_failure_count": plot_validation["plot_data_audit_failure_count"],
        "source_row_hash_mismatch_count": plot_validation["source_row_hash_mismatch_count"],
        "source_value_mismatch_count": plot_validation["source_value_mismatch_count"],
        "audit_pass": plot_validation["plot_data_audit_failure_count"] == 0,
    }
    write_json(result_dir / "plot_data_audit.json", plot_audit)
    summary_rows = build_descriptive_summary(merged_rows)
    write_csv(result_dir / "day12_descriptive_summary.csv", summary_rows, DESCRIPTIVE_SUMMARY_FIELDS)
    (result_dir / "figure_captions.md").write_text(CAPTIONS, encoding="utf-8")
    generate_four_figures(figure_data, result_dir, int(config["png_dpi"]))
    qc = audit_figures(result_dir, int(config["png_dpi"]))
    write_json(result_dir / "figure_qc.json", qc)
    static = audit_plot_code(root / "src/eval/stage2_failure_day12_figures.py")
    write_json(result_dir / "plot_code_static_audit.json", static)

    with tempfile.TemporaryDirectory(prefix="degen_lio_day12_repro_") as temporary:
        second = Path(temporary) / "second"
        _render_reproduction(second, figure_data, merged_rows, int(config["png_dpi"]))
        reproducibility = compare_reproduction(result_dir, second)
    write_json(result_dir / "reproducibility_audit.json", reproducibility)

    current_tree = result_tree_manifest(root, Path(day11b_run_dir).resolve())
    before_tree = (Path.home() / "day11b_v2_result_sha256_before_day12.txt").read_bytes()
    tree_before_digest = hashlib.sha256(before_tree).hexdigest()
    tree_after_digest = hashlib.sha256(current_tree).hexdigest()
    historical_after = _historical_hashes(root)
    manifest: Dict[str, Any] = {
        "run_id": str(run_id), "task": "Stage 2 Failure-Mechanism Diagnosis — Day 12",
        "schema_version": DAY12_SCHEMA_VERSION, "created_at": datetime.now(timezone.utc).isoformat(),
        "git_branch": _git_branch(root), "git_commit": git_commit(root),
        "git_status_clean_at_start": clean_at_start, "python_version": platform.python_version(),
        "numpy_version": np.__version__, "scipy_version": scipy.__version__,
        "matplotlib_version": matplotlib.__version__, "pillow_version": pillow_version,
        "python311_available": False, "python311_tests_pass": False,
        "day11b_v2_checkpoint_commit": _git_rev(root, f"{DAY11B_V2_CHECKPOINT}^{{}}"),
        "head_descends_from_day11b_v2_checkpoint": _git_ancestor(root, DAY11B_V2_CHECKPOINT, "HEAD"),
        "day11b_v2_manifest_sha256": audit["day11b_manifest_sha256"],
        "day11b_v2_summary_sha256": audit["day11b_summary_sha256"],
        "replay_plan_sha256": audit["replay_plan_sha256"],
        "replay_case_summary_sha256": audit["replay_case_summary_sha256"],
        "merged_csv_sha256": audit["merged_csv_sha256"],
        "day12_input_lock_sha256": _sha256(result_dir / "day12_input_lock.json"),
        "day12_input_audit_pass": audit["DAY12_INPUT_AUDIT_PASS"],
        "expected_case_count": 8, "actual_case_count": audit["actual_case_count"],
        "expected_merged_row_count": audit["expected_merged_row_count"],
        "actual_merged_row_count": audit["actual_merged_row_count"],
        "strategy_chain_comparison_count": audit["strategy_chain_comparison_count"],
        "strategy_chain_mismatch_count": audit["strategy_chain_mismatch_count"],
        "case_identity_mismatch_count": audit["case_identity_mismatch_count"],
        "duplicate_frame_key_count": audit["duplicate_key_count"],
        "missing_frame_key_count": audit["missing_key_count"],
        "nonfinite_violation_count": audit["nonfinite_violation_count"],
        "method_expanded_contaminated_measurement_count": audit["method_expanded_contaminated_measurement_count"],
        "external_unique_contaminated_measurement_count": audit["external_unique_contaminated_measurement_count"],
        "method_expanded_stress_active_frame_count": audit["method_expanded_stress_active_frame_count"],
        "external_unique_stress_active_frame_count": audit["external_unique_stress_active_frame_count"],
        "clean_external_contaminated_measurement_count": audit["clean_external_contaminated_measurement_count"],
        "coherent_burst_count": audit["coherent_burst_count"],
        "coherent_burst_lengths": audit["coherent_burst_lengths"],
        "coherent_offset_abs_m": audit["coherent_offset_abs_m"],
        "coherent_shared_sign_pass": audit["coherent_shared_sign_pass"],
        "contaminated_non_axial_support_count": audit["contaminated_non_axial_support_count"],
        "axial_only_audit_pass": audit["axial_only_audit_pass"],
        "points_lidar_mismatch_count": audit["points_lidar_mismatch_count"],
        "normals_world_mismatch_count": audit["normals_world_mismatch_count"],
        "R_diag_mismatch_count": audit["R_diag_mismatch_count"],
        "plot_data_file_count": plot_audit["plot_data_file_count"],
        "plot_data_audit_failure_count": plot_audit["plot_data_audit_failure_count"],
        "source_row_hash_mismatch_count": plot_audit["source_row_hash_mismatch_count"],
        "source_value_mismatch_count": plot_audit["source_value_mismatch_count"],
        "plot_data_files": plot_files["files"], "expected_figure_count": 4,
        "png_figure_count": qc["png_figure_count"], "pdf_figure_count": qc["pdf_figure_count"],
        "unexpected_figure_count": qc["unexpected_figure_count"],
        "forbidden_output_count": qc["forbidden_output_count"],
        "figure_qc_failure_count": qc["figure_qc_failure_count"], "figure_files": qc["figures"],
        **{key: reproducibility[key] for key in (
            "repro_plot_data_byte_identical", "repro_png_pixel_hash_identical",
            "repro_summary_byte_identical", "repro_captions_byte_identical"
        )},
        "day11b_v2_result_tree_digest_before": tree_before_digest,
        "day11b_v2_result_tree_digest_after": tree_after_digest,
        "day11b_v2_results_unchanged": before_tree == current_tree,
        "estimator_replayed": False, "new_seed_used": False,
        "day11b_results_modified": False, "figure_data_selected_after_viewing": False,
        "best_statistic_selected": False, "best_method_selected": False,
        "threshold_created": False, "threshold_line_drawn": False,
        "auroc_computed": False, "fpr_computed": False, "f1_computed": False,
        "detection_delay_computed": False, "significance_test_performed": False,
        "replay_is_independent_test": False, "replay_is_representative": False,
        "figures_for_diagnosis_only": True,
        "historical_artifact_hashes_before": historical_before,
        "historical_artifact_hashes_after": historical_after,
        "historical_artifacts_unchanged": historical_before == historical_after,
        "plot_code_static_audit_pass": static["audit_pass"],
        "STAGE2_GATE": "INCOMPLETE", "STAGE3_GATE": "NOT_STARTED",
        "COHERENT_BIAS_DETECTABLE": "UNDETERMINED", "RISK_WARNING_AUTHORIZED": False,
        "FAST_LIO2_INTEGRATION_AUTHORIZED": False, "PUBLIC_DISCLOSURE_AUTHORIZED": False,
    }
    passed = evaluate_day12_gate(manifest) and static["audit_pass"] and qc["audit_pass"] and reproducibility["audit_pass"]
    manifest["DAY12_DIAGNOSTIC_FIGURES_PASS"] = passed
    manifest["DAY13_NEW_SEED_DIAGNOSTIC_AUTHORIZED"] = passed
    write_json(result_dir / "day12_summary.json", manifest)
    write_json(result_dir / "run_manifest.json", manifest)
    return manifest


def validate_input_lock(path: Path) -> None:
    lock = json.loads(Path(path).read_text(encoding="utf-8"))
    expected = {
        "schema_version": INPUT_LOCK_SCHEMA_VERSION,
        "lock_type": "day12_locked_diagnostic_plot_input_v2",
        "expected_case_count": 8, "method_list": list(EXPECTED_METHODS),
        "stress_list": list(EXPECTED_STRESSES), "sweep_list": list(EXPECTED_SWEEPS),
        "external_unique_contaminated_measurement_count": 436,
        "external_unique_stress_active_frame_count": 40,
        "coherent_burst_count": 2, "coherent_burst_lengths": [20, 20],
        "coherent_offset_abs_m": 0.03, "replay_is_independent_test": False,
        "replay_is_representative": False, "figures_for_diagnosis_only": True,
        "threshold_selection_allowed": False, "stage2_gate_decision_allowed": False,
        "input_audit_pass": True,
        "day11b_v2_checkpoint_commit": DAY11B_V2_CHECKPOINT_COMMIT,
        "head_descends_from_day11b_v2_checkpoint": True,
    }
    if any(lock.get(field) != value for field, value in expected.items()):
        raise ValueError("Day 12 input lock has changed")
    for path_field, hash_field in (
        ("day11b_manifest_path", "day11b_manifest_sha256"),
        ("day11b_summary_path", "day11b_summary_sha256"),
        ("replay_plan_path", "replay_plan_sha256"),
        ("replay_case_summary_path", "replay_case_summary_sha256"),
        ("merged_csv_path", "merged_csv_sha256"),
        ("input_audit_path", "input_audit_sha256"),
    ):
        if _sha256(Path(lock[path_field])) != lock[hash_field]:
            raise ValueError(f"Day 12 input lock hash mismatch: {hash_field}")


def _build_input_lock(root: Path, run_dir: Path, result_dir: Path, audit: Mapping[str, Any]) -> Mapping[str, Any]:
    fields = {
        "schema_version": INPUT_LOCK_SCHEMA_VERSION,
        "lock_type": "day12_locked_diagnostic_plot_input_v2",
        "created_at": datetime.now(timezone.utc).isoformat(), "git_branch": _git_branch(root),
        "git_commit": git_commit(root),
        "day11b_v2_checkpoint_commit": _git_rev(root, f"{DAY11B_V2_CHECKPOINT}^{{}}"),
        "head_descends_from_day11b_v2_checkpoint": _git_ancestor(root, DAY11B_V2_CHECKPOINT, "HEAD"),
        "day11b_v2_run_dir": str(run_dir),
        "day11b_manifest_path": str(run_dir / "run_manifest.json"),
        "day11b_summary_path": str(run_dir / "day11b_v2_summary.json"),
        "replay_plan_path": str(run_dir / "replay_plan.csv"),
        "replay_case_summary_path": str(run_dir / "replay_case_summary.csv"),
        "merged_csv_path": str(run_dir / "replay_frame_diagnostics_merged.csv"),
        "input_audit_path": str(result_dir / "day12_input_audit.json"),
        "input_audit_pass": audit["DAY12_INPUT_AUDIT_PASS"],
        "expected_case_count": 8, "actual_case_count": audit["actual_case_count"],
        "expected_merged_row_count": audit["expected_merged_row_count"],
        "actual_merged_row_count": audit["actual_merged_row_count"],
        "case_ids": audit["case_ids"], "method_list": list(EXPECTED_METHODS),
        "stress_list": list(EXPECTED_STRESSES), "sweep_list": list(EXPECTED_SWEEPS),
        "strategy_chain_mismatch_count": audit["strategy_chain_mismatch_count"],
        "case_identity_mismatch_count": audit["case_identity_mismatch_count"],
        "duplicate_key_count": audit["duplicate_key_count"], "missing_key_count": audit["missing_key_count"],
        "nonfinite_violation_count": audit["nonfinite_violation_count"],
        "method_expanded_contaminated_measurement_count": audit["method_expanded_contaminated_measurement_count"],
        "external_unique_contaminated_measurement_count": audit["external_unique_contaminated_measurement_count"],
        "method_expanded_stress_active_frame_count": audit["method_expanded_stress_active_frame_count"],
        "external_unique_stress_active_frame_count": audit["external_unique_stress_active_frame_count"],
        "coherent_burst_count": audit["coherent_burst_count"],
        "coherent_burst_lengths": audit["coherent_burst_lengths"],
        "coherent_offset_abs_m": audit["coherent_offset_abs_m"],
        "coherent_shared_sign_pass": audit["coherent_shared_sign_pass"],
        "axial_only_audit_pass": audit["axial_only_audit_pass"],
        "replay_is_independent_test": False, "replay_is_representative": False,
        "figures_for_diagnosis_only": True, "threshold_selection_allowed": False,
        "stage2_gate_decision_allowed": False,
    }
    fields.update({key: audit[key] for key in (
        "day11b_manifest_sha256", "day11b_summary_sha256", "replay_plan_sha256",
        "replay_case_summary_sha256", "merged_csv_sha256", "strategy_chain_audit_sha256",
        "axial_support_audit_sha256", "base_observation_pairing_audit_sha256",
        "v1_v2_scientific_equivalence_audit_sha256",
    )})
    fields["input_audit_sha256"] = _sha256(result_dir / "day12_input_audit.json")
    return fields


def _write_input_audit(result_dir: Path, audit: Mapping[str, Any]) -> None:
    write_json(result_dir / "day12_input_audit.json", audit)
    write_csv(result_dir / "day12_input_audit.csv", audit["checks"], ("check", "pass", "detail"))


def _render_reproduction(target: Path, data: Mapping[str, Sequence[Mapping[str, Any]]], merged_rows: Sequence[Mapping[str, str]], dpi: int) -> None:
    write_plot_data(target, data)
    write_csv(target / "day12_descriptive_summary.csv", build_descriptive_summary(merged_rows), DESCRIPTIVE_SUMMARY_FIELDS)
    (target / "figure_captions.md").parent.mkdir(parents=True, exist_ok=True)
    (target / "figure_captions.md").write_text(CAPTIONS, encoding="utf-8")
    generate_four_figures(data, target, dpi)


def _load_config(root: Path) -> Mapping[str, Any]:
    config = load_yaml(root / "configs/stage2_failure/day12_figures.yaml")
    expected = {
        "mode": "day12_diagnostic_figures_v2", "schema_version": DAY12_SCHEMA_VERSION,
        "input_run_dir": "results/stage2_failure_analysis/day11b_replay/stage2_failure_day11b_replay_v2",
        "expected_methods": list(EXPECTED_METHODS), "expected_stress": list(EXPECTED_STRESSES),
        "expected_sweeps": list(EXPECTED_SWEEPS), "expected_case_count": 8,
        "figure_formats": ["png", "pdf"], "png_dpi": 300, "matplotlib_backend": "Agg",
        "font_family": "DejaVu Sans", "use_constrained_layout": True,
        "crop_data_range": False, "clip_outliers": False, "smooth_timeline": False,
        "interpolate_missing": False, "forward_fill_missing": False,
        "use_fixed_line_styles": True, "use_marker_shape_redundancy": True,
        "black_white_distinguishable": True, "generate_exactly_four_figures": True,
        "generate_plot_data_csv": True, "generate_figure_captions": True,
        "create_threshold": False, "draw_threshold_line": False, "compute_auroc": False,
        "compute_fpr": False, "compute_f1": False, "compute_detection_delay": False,
        "perform_significance_test": False, "select_best_statistic": False,
        "select_best_method": False, "replay_estimator": False, "use_new_seed": False,
        "modify_day11b_results": False,
    }
    for field, value in expected.items():
        if config.get(field) != value or type(config.get(field)) is not type(value):
            raise ValueError(f"Day 12 config field changed: {field}")
    return config


def _selection_rule(figure_id: str) -> str:
    return {
        "day12_fig01_innovation_timeline": "all saved frames; NaN preserved",
        "day12_fig02_prior_posterior_axis_error": "all saved offline-evaluation frames",
        "day12_fig03_same_sign_run_timeline": "all saved frames; current run only",
        "day12_fig04_clean_stress_distributions": "fixed per-metric stat_input_valid/window_ready rules",
    }[figure_id]


def _validate_output_path(day11b: Path, result: Path) -> None:
    if Path(result).resolve() == Path(day11b).resolve() or Path(day11b).resolve() in Path(result).resolve().parents:
        raise ValueError("Day 12 output may not modify the Day 11B v2 tree")


def _validate_git_preconditions(root: Path) -> None:
    checkpoint = _git_rev(root, f"{DAY11B_V2_CHECKPOINT}^{{}}")
    if checkpoint != DAY11B_V2_CHECKPOINT_COMMIT:
        raise RuntimeError("Day 11B v2 checkpoint commit mismatch")
    if not _git_ancestor(root, DAY11B_V2_CHECKPOINT, "HEAD"):
        raise RuntimeError("HEAD does not descend from the Day 11B v2 checkpoint")


def _historical_hashes(root: Path) -> Mapping[str, str]:
    return {path: compute_directory_hash(root / path) for path in HISTORICAL_PATHS}


def _git_branch(root: Path) -> str:
    return subprocess.check_output(["git", "branch", "--show-current"], cwd=str(root), text=True).strip()


def _git_rev(root: Path, revision: str) -> str:
    return subprocess.check_output(["git", "rev-parse", revision], cwd=str(root), text=True).strip()


def _git_ancestor(root: Path, first: str, second: str) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", first, second], cwd=str(root), check=False).returncode == 0


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
