"""Independent compact-artifact verification for Development."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib.image as mpimg
import pandas as pd

from .protocol import PROTOCOL_SHA256, file_sha256, load_protocol


REQUIRED_TABLES = {
    "protocol_summary.csv",
    "scene_inventory.csv",
    "snapshot_inventory.csv",
    "trial_results.csv",
    "zero_initialization_error.csv",
    "systematic_offset_summary.csv",
    "repeatability_summary.csv",
    "correspondence_turnover.csv",
    "normal_turnover.csv",
    "full_frozen_comparison.csv",
    "noise_condition_summary.csv",
    "backend_agreement.csv",
    "scene_contrast.csv",
    "traditional_metric_correlations.csv",
    "multi_attractor_summary.csv",
    "runtime_summary.csv",
    "gate_summary.csv",
}
REQUIRED_FIGURES = {
    "ideal_matched_control.png",
    "scene_translation_error.png",
    "scene_rotation_error.png",
    "systematic_offset_vectors.png",
    "repeatability_vs_systematic_offset.png",
    "full_vs_frozen_paired.png",
    "turnover_vs_full_frozen_difference.png",
    "noise_condition_effects.png",
    "backend_scene_ranking.png",
}


def _verify_sums(artifact: Path) -> list[str]:
    errors = []
    lines = (artifact / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    declared = set()
    for line in lines:
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


def verify_development(root: str | Path) -> dict[str, Any]:
    repository = Path(root).resolve()
    protocol = load_protocol(repository)
    artifact = repository / protocol.section("outputs")["artifact_root"]
    errors: list[str] = []
    tables = artifact / "tables"
    figures = artifact / "figures"
    if {path.name for path in tables.glob("*.csv")} != REQUIRED_TABLES:
        errors.append("required table inventory mismatch")
    if {path.name for path in figures.glob("*.png")} != REQUIRED_FIGURES:
        errors.append("required figure inventory mismatch")

    inventory = pd.read_csv(tables / "snapshot_inventory.csv")
    trials = pd.read_csv(tables / "trial_results.csv")
    diagnostics = pd.read_csv(tables / "full_frozen_comparison.csv")
    manifest = json.loads((artifact / "run_manifest.json").read_text(encoding="utf-8"))
    expected_snapshots = int(manifest["snapshot_count"])
    expected_trials = int(manifest["trial_count"])
    if expected_snapshots not in {42, 1260}:
        errors.append("artifact snapshot count is neither frozen smoke nor complete Development")
    if expected_trials != expected_snapshots * 3:
        errors.append("artifact trial count is not three times the snapshot count")
    if len(inventory) != expected_snapshots or inventory["snapshot_id"].nunique() != expected_snapshots:
        errors.append("snapshot inventory does not match manifest")
    if len(trials) != expected_trials:
        errors.append("trial inventory does not match manifest")
    counts = trials.groupby("snapshot_id")["registration_backend"].agg(["count", "nunique"])
    if not ((counts["count"] == 3) & (counts["nunique"] == 3)).all():
        errors.append("each snapshot must contain exactly three distinct backend trials")
    if not (
        trials.groupby("snapshot_id")["backend_input_checksum"].nunique() == 1
    ).all():
        errors.append("backend input checksum pairing violation")
    if len(diagnostics) != expected_snapshots:
        errors.append("full/frozen comparison does not match snapshot count")

    decision = json.loads((artifact / "final_decision.json").read_text(encoding="utf-8"))
    lock = json.loads((artifact / "development_protocol_lock.json").read_text(encoding="utf-8"))
    if manifest["protocol_sha256"] != PROTOCOL_SHA256 or lock["protocol_sha256"] != PROTOCOL_SHA256:
        errors.append("protocol SHA mismatch")
    for field in (
        "confirmatory_seed_instantiation_count",
        "old_capture_range_test_seed_access_count",
        "gt_optimization_leakage_count",
        "snapshot_pairing_violation_count",
    ):
        if int(manifest[field]) != 0:
            errors.append(f"nonzero firewall/pairing count: {field}")
    for fixed_false in (
        "ZERO_PERTURBATION_CONFIRMATORY_RUN_AUTHORIZED",
        "REAL_DATA_VALIDATION_AUTHORIZED",
        "MEASUREMENT_PAPER_MAINLINE_AUTHORIZED",
    ):
        if decision[fixed_false] is not False:
            errors.append(f"fixed-false authority changed: {fixed_false}")
    required_authorization = (
        "DEVELOPMENT_PIPELINE_EXECUTABLE",
        "ALL_1260_SNAPSHOTS_COMPLETE",
        "ALL_3780_TRIALS_COMPLETE",
        "SNAPSHOT_PAIRING_PASS",
        "OPEN3D_BACKEND_PASS",
        "NO_CONFIRMATORY_SEED_ACCESS",
        "NO_OLD_CAPTURE_TEST_SEED_ACCESS",
        "NO_GT_OPTIMIZATION_LEAKAGE",
        "IDEAL_MATCHED_CONTROL_PASS",
        "PRELIMINARY_SCENE_EFFECT_OBSERVED",
        "PRELIMINARY_CROSS_BACKEND_SIGNAL_OBSERVED",
        "PRELIMINARY_REASSOCIATION_EFFECT_OBSERVED",
    )
    expected_authorization = bool(
        all(decision[field] is True for field in required_authorization)
        and decision["NEW_PROTOCOL_AMBIGUITIES_FOUND"] is False
    )
    if decision["ZERO_PERTURBATION_CONFIRMATORY_LOCK_AUTHORIZED"] is not expected_authorization:
        errors.append("Confirmatory-lock authorization does not match frozen conjunction")
    if expected_snapshots == 42:
        if decision["IDEAL_MATCHED_CONTROL_PASS"] is not False:
            errors.append("early-stop smoke artifact must record failed IDEAL_MATCHED control")
        if decision["FULL_DEVELOPMENT_RUN_EXECUTED"] is not False:
            errors.append("early-stop artifact incorrectly claims full Development execution")
        if decision["PRELIMINARY_SCIENTIFIC_SIGNALS_EVALUATED"] is not False:
            errors.append("preliminary signals must remain unevaluated after hard-gate failure")

    for path in sorted(figures.glob("*.png")):
        image = mpimg.imread(path)
        if image.ndim not in (2, 3) or image.shape[0] < 400 or image.shape[1] < 600:
            errors.append(f"figure failed dimensions/readability check: {path.name}")
    report = (artifact / "development_report.md").read_text(encoding="utf-8")
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
    errors.extend(_verify_sums(artifact))
    return {
        "schema_version": "zero_perturbation_development_verification_v1",
        "verification_pass": not errors,
        "error_count": len(errors),
        "errors": errors,
        "snapshot_count": len(inventory),
        "trial_count": len(trials),
        "table_count": len(REQUIRED_TABLES),
        "figure_count": len(REQUIRED_FIGURES),
    }


__all__ = ["REQUIRED_FIGURES", "REQUIRED_TABLES", "verify_development"]
