"""Independent verification for the stopped backend-qualification artifact."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib.image as mpimg
import pandas as pd

from .protocol import file_sha256


REQUIRED_TABLES = {
    "dependency_audit.csv",
    "pcl_build_manifest.csv",
    "backend_parameter_contract.csv",
    "ideal_matched_snapshot_inventory.csv",
    "ideal_matched_trial_results.csv",
    "ideal_matched_backend_summary.csv",
    "ideal_matched_scene_summary.csv",
    "backend_input_checksum_audit.csv",
    "scene_signal_smoke_results.csv",
    "scene_signal_backend_ranking.csv",
    "gate_summary.csv",
}
REQUIRED_FIGURES = {
    "ideal_matched_backend_translation.png",
    "ideal_matched_backend_rotation.png",
    "ideal_matched_scene_breakdown.png",
    "open3d_vs_pcl_scene_ranking.png",
    "scene_signal_translation_error.png",
}
PROTOCOL_SHA256 = "109426c0da08f2ebb1647735d617a8693d0ae21b57c8c80474c81d224f6c45b8"


def _verify_sums(artifact: Path) -> list[str]:
    errors: list[str] = []
    sums = artifact / "SHA256SUMS"
    if not sums.is_file():
        return ["SHA256SUMS is missing"]
    declared: set[str] = set()
    for line in sums.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        declared.add(relative)
        path = artifact / relative
        if not path.is_file():
            errors.append(f"SHA256SUMS path missing: {relative}")
        elif file_sha256(path) != digest:
            errors.append(f"SHA256 mismatch: {relative}")
    actual = {
        path.relative_to(artifact).as_posix()
        for path in artifact.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    if declared != actual:
        errors.append("SHA256SUMS inventory does not match artifact files")
    return errors


def verify_backend_qualification(root: str | Path) -> dict[str, Any]:
    repository = Path(root).resolve()
    artifact = repository / "artifacts/current/zero_perturbation_backend_qualification"
    tables = artifact / "tables"
    figures = artifact / "figures"
    errors: list[str] = []

    if {path.name for path in tables.glob("*.csv")} != REQUIRED_TABLES:
        errors.append("required table inventory mismatch")
    if {path.name for path in figures.glob("*.png")} != REQUIRED_FIGURES:
        errors.append("required figure inventory mismatch")

    protocol = repository / "configs/zero_perturbation/backend_qualification_v1.yaml"
    if file_sha256(protocol) != PROTOCOL_SHA256:
        errors.append("qualification protocol hash changed")
    decision = json.loads((artifact / "final_decision.json").read_text(encoding="utf-8"))
    manifest = json.loads((artifact / "run_manifest.json").read_text(encoding="utf-8"))
    lock = json.loads(
        (artifact / "backend_qualification_protocol_lock.json").read_text(encoding="utf-8")
    )
    if lock["protocol_sha256"] != PROTOCOL_SHA256:
        errors.append("protocol lock hash mismatch")

    snapshots = pd.read_csv(tables / "ideal_matched_snapshot_inventory.csv")
    trials = pd.read_csv(tables / "ideal_matched_trial_results.csv")
    phase_b = pd.read_csv(tables / "scene_signal_smoke_results.csv")
    if len(snapshots) != 0 or len(trials) != 0 or len(phase_b) != 0:
        errors.append("qualification rows exist after the build-smoke stop")
    if any(
        int(manifest[field]) != 0
        for field in (
            "ideal_matched_snapshot_count",
            "ideal_matched_trial_count",
            "phase_b_snapshot_count",
            "phase_b_trial_count",
            "backend_input_checksum_mismatch_count",
            "gt_optimization_leakage_count",
            "confirmatory_seed_instantiation_count",
            "old_capture_range_test_seed_access_count",
            "native_qualification_trial_invocation_count",
        )
    ):
        errors.append("nonzero trial or firewall count after prerequisite stop")

    if decision["PCL_DEPENDENCY_READY"] is not True:
        errors.append("dependency readiness result changed")
    for field in (
        "NATIVE_BACKEND_QUALIFICATION_PASS",
        "PCL_BACKEND_BUILD_PASS",
        "OPEN3D_BACKEND_QUALIFICATION_PASS",
        "PCL_BACKEND_QUALIFICATION_PASS",
        "IDEAL_MATCHED_SNAPSHOT_DIVERSITY_PASS",
        "BACKEND_INPUT_PAIRING_PASS",
        "TWO_INDEPENDENT_BACKENDS_QUALIFIED",
        "CROSS_BACKEND_SCENE_SIGNAL_OBSERVED",
        "ZERO_PERTURBATION_FULL_DEVELOPMENT_REDESIGN_AUTHORIZED",
        "ZERO_PERTURBATION_FULL_DEVELOPMENT_RUN_AUTHORIZED",
        "ZERO_PERTURBATION_CONFIRMATORY_LOCK_AUTHORIZED",
        "ZERO_PERTURBATION_CONFIRMATORY_RUN_AUTHORIZED",
        "REAL_DATA_VALIDATION_AUTHORIZED",
        "MEASUREMENT_PAPER_MAINLINE_AUTHORIZED",
    ):
        if decision[field] is not False:
            errors.append(f"false decision changed: {field}")
    if decision["stop_reason"] != "PCL_IDENTICAL_CLOUD_IDENTITY_SMOKE_FAILED":
        errors.append("stop reason changed")
    if decision["parameter_rescue_attempted"] is not False:
        errors.append("artifact claims a forbidden parameter rescue")

    dependency = pd.read_csv(tables / "dependency_audit.csv")
    final_probe = dependency[dependency["check_id"] == "final_conda_pcl_probe"]
    if len(final_probe) != 1 or bool(final_probe.iloc[0]["pass"]) is not True:
        errors.append("required PCL pkg-config probe did not pass")
    build = pd.read_csv(tables / "pcl_build_manifest.csv")
    identity = build[build["step"] == "identical_cloud_identity_ctest"]
    if len(identity) != 1 or identity.iloc[0]["status"] != "fail":
        errors.append("identity-smoke failure evidence changed")

    for path in sorted(figures.glob("*.png")):
        image = mpimg.imread(path)
        if image.ndim not in (2, 3) or image.shape[0] < 500 or image.shape[1] < 900:
            errors.append(f"figure failed readability dimensions: {path.name}")
    report = (artifact / "backend_qualification_report.md").read_text(encoding="utf-8")
    for heading in (
        "## Technical summary",
        "## Scope, data, and metric definitions",
        "## Methodology and reproducibility",
        "## Limitations, uncertainty, and robustness checks",
        "## Recommended next step",
        "## Further questions",
    ):
        if heading not in report:
            errors.append(f"technical report section missing: {heading}")

    for path in (
        repository / "reports/zero_perturbation_pcl_environment/environment_creation.log",
        repository / "reports/zero_perturbation_pcl_environment/package_versions.json",
        repository / "reports/zero_perturbation_pcl_environment/micromamba_explicit.txt",
        repository / "reports/zero_perturbation_pcl_environment/compiler_version.txt",
        repository / "reports/zero_perturbation_pcl_environment/pkg_config_versions.txt",
        repository / "reports/zero_perturbation_pcl_environment/build_log.txt",
        repository / "reports/zero_perturbation_pcl_environment/smoke_test.txt",
    ):
        if not path.is_file():
            errors.append(f"environment evidence missing: {path.name}")

    errors.extend(_verify_sums(artifact))
    return {
        "schema_version": "zero_perturbation_backend_qualification_verification_v1",
        "verification_pass": not errors,
        "error_count": len(errors),
        "errors": errors,
        "phase_a_snapshot_count": len(snapshots),
        "phase_a_trial_count": len(trials),
        "phase_b_trial_count": len(phase_b),
        "table_count": len(REQUIRED_TABLES),
        "figure_count": len(REQUIRED_FIGURES),
    }


__all__ = [
    "PROTOCOL_SHA256",
    "REQUIRED_FIGURES",
    "REQUIRED_TABLES",
    "verify_backend_qualification",
]

