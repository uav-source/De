"""Independent structural, decision, and SHA verifier for audit v1.2."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .phase_a_execution_chain_artifact_verifier import FIGURES, TABLES
from .phase_a_trial_result_schema import file_sha256


ROOT_FILES = (
    "execution_chain_audit_v1_2_report.md",
    "resume_scientific_equivalence_contract.json",
    "resume_scientific_equivalence_report.json",
    "resume_difference_inventory.csv",
    "fresh_analysis_output.json",
    "resumed_analysis_output.json",
    "fresh_final_decision.json",
    "resumed_final_decision.json",
    "independent_verification.json",
    "implementation_manifest.json",
    "publisher_inventory.json",
    "fixture_contract_diff.json",
    "resume_audit.json",
    "tamper_audit.json",
    "artifact_verification.json",
    "run_manifest.json",
    "final_decision.json",
    "SHA256SUMS",
)


def required_relative_paths() -> tuple[str, ...]:
    return (
        tuple(f"tables/{name}" for name in TABLES)
        + tuple(f"figures/{name}" for name in FIGURES)
        + ROOT_FILES
    )


def verify_phase_a_execution_chain_v1_2_artifact(path: str | Path) -> dict[str, Any]:
    artifact = Path(path).resolve()
    required = required_relative_paths()
    missing = [relative for relative in required if not (artifact / relative).is_file()]
    empty = [
        relative
        for relative in required
        if (artifact / relative).is_file() and (artifact / relative).stat().st_size == 0
    ]
    decision_errors: list[str] = []
    try:
        decision = json.loads((artifact / "final_decision.json").read_text(encoding="utf-8"))
        required_true = (
            "RESUME_EQUIVALENCE_CONTRACT_PASS",
            "RESUME_EXACT_FIELDS_PASS",
            "RESUME_NUMERIC_FIELDS_WITHIN_TOLERANCE",
            "RESUME_NULL_CONSISTENCY_PASS",
            "RESUME_FAILURE_CLASSIFICATION_PASS",
            "RESUME_GATE_DECISIONS_IDENTICAL",
            "RESUME_FINAL_DECISION_IDENTICAL",
            "EXECUTION_CHAIN_SCHEMA_PASS",
            "EXECUTION_CHAIN_WRITER_PASS",
            "EXECUTION_CHAIN_STRICT_RESUME_PASS",
            "EXECUTION_CHAIN_FIXTURE_PASS",
            "EXECUTION_CHAIN_ANALYSIS_VERIFIER_MATCH",
            "EXECUTION_CHAIN_PUBLISHER_PASS",
            "EXECUTION_CHAIN_ARTIFACT_VERIFICATION_PASS",
            "EXECUTION_CHAIN_TAMPER_REJECTION_PASS",
            "EXECUTION_CHAIN_AUDIT_V1_2_PASS",
        )
        decision_errors.extend(name for name in required_true if decision.get(name) is not True)
        if decision.get("PHASE_A_STAGE1_BACKEND_EXECUTED") is not False:
            decision_errors.append("formal backend execution state changed")
        if decision.get("DAY1_SCIENTIFIC_VALIDATION_PASS") != "NOT_EVALUATED":
            decision_errors.append("scientific validation state changed")
    except (OSError, json.JSONDecodeError) as error:
        decision_errors.append(f"invalid final decision: {error}")
    report_label_pass = False
    try:
        report = (artifact / "execution_chain_audit_v1_2_report.md").read_text(
            encoding="utf-8"
        )
        report_label_pass = (
            "FIXTURE EXECUTION-CHAIN AUDIT" in report
            and "NOT SCIENTIFIC PHASE-A DATA" in report
        )
    except OSError:
        pass
    sha_errors: list[str] = []
    try:
        lines = (artifact / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
        listed: set[str] = set()
        for line in lines:
            digest, relative = line.split("  ", 1)
            listed.add(relative)
            candidate = artifact / relative
            if not candidate.is_file() or file_sha256(candidate) != digest:
                sha_errors.append(relative)
        if listed != set(required) - {"SHA256SUMS"}:
            sha_errors.append("SHA256SUMS inventory mismatch")
    except (OSError, ValueError) as error:
        sha_errors.append(f"invalid SHA256SUMS: {error}")
    passed = bool(
        not missing
        and not empty
        and not decision_errors
        and report_label_pass
        and not sha_errors
    )
    return {
        "EXECUTION_CHAIN_ARTIFACT_VERIFICATION_PASS": passed,
        "decision_errors": decision_errors,
        "empty_files": empty,
        "fixture_label_pass": report_label_pass,
        "missing_files": missing,
        "required_file_count": len(required),
        "schema_version": "phase_a_execution_chain_audit_v1_2_artifact_verification_v1",
        "sha256_errors": sha_errors,
        "sha256_validation_pass": not sha_errors,
    }


__all__ = ["required_relative_paths", "verify_phase_a_execution_chain_v1_2_artifact"]
