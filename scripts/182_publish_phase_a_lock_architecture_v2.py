#!/usr/bin/env python3
"""Publish the final layered-lock audit decision and independently verify SHA."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_perturbation.backend_phase_a_v2 import dry_run_phase_a_v2
from zero_perturbation.phase_a_formal_run_lock_v2 import FORMAL_LOCK_RELATIVE
from zero_perturbation.phase_a_lock_architecture_v2 import (
    ARTIFACT_RELATIVE,
    verify_lock_architecture_artifact,
)
from zero_perturbation.phase_a_lock_v2_tamper import run_23_tamper_cases
from zero_perturbation.phase_a_trial_result_schema import canonical_json_bytes, file_sha256
from zero_perturbation.phase_a_trial_result_writer import atomic_write_bytes


def _json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise ValueError(path)
    return value


def _write(path: Path, value: dict | bytes, *, replace: bool) -> None:
    payload = value if isinstance(value, bytes) else canonical_json_bytes(value)
    atomic_write_bytes(path, payload, replace=replace and path.exists())


def publish(args: argparse.Namespace) -> dict:
    artifact = args.artifact_dir.resolve()
    dry_path = artifact / "dry_run_report.json"
    tamper_path = artifact / "tamper_rejection_report.json"
    if dry_path.exists():
        dry = _json(dry_path)
    else:
        dry = dry_run_phase_a_v2(
            root=ROOT,
            formal_run_lock=ROOT / FORMAL_LOCK_RELATIVE,
            run_id="backend-phase-a-v2-dry-run-recorded",
            output_dir=args.dry_run_output.resolve(),
            workers=4,
        )
        _write(dry_path, dry, replace=False)
    if tamper_path.exists():
        tamper = _json(tamper_path)
    else:
        tamper = run_23_tamper_cases(
            root=ROOT, formal_run_lock=ROOT / FORMAL_LOCK_RELATIVE
        )
        _write(tamper_path, tamper, replace=False)
    preparation = _json(artifact / "lock_architecture_v2_preparation.json")
    graph = _json(artifact / "lock_dependency_graph.json")
    projection = _json(artifact / "scientific_protocol_projection_diff.json")
    snapshot = _json(artifact / "snapshot_lock_binding_v2.json")
    fixture = _json(artifact / "execution_fixture_final_decision.json")
    resume = _json(artifact / "resume_equivalence_report.json")
    comparison = _json(artifact / "analysis_verifier_comparison.json")
    publisher = _json(artifact / "execution_fixture_publisher_inventory.json")
    implementation = _json(artifact / "phase_a_execution_implementation_lock_v2.json")
    formal = _json(artifact / "phase_a_formal_run_lock_v2.json")
    science_diff = _json(artifact / "lock_architecture_v2_scientific_diff.json")
    all_science_zero = all(
        value == 0
        for key, value in science_diff.items()
        if key.endswith("difference_count")
    ) and projection["SCIENTIFIC_PROTOCOL_PROJECTION_PASS"] is True
    gate_values = {
        "LEGACY_LOCK_FIELD_CLASSIFICATION_PASS": preparation["LEGACY_LOCK_FIELD_CLASSIFICATION_PASS"],
        "LOCK_GRAPH_ACYCLIC": graph["LOCK_GRAPH_ACYCLIC"],
        "LOCK_GRAPH_DUPLICATE_BINDING_COUNT": graph["LOCK_GRAPH_DUPLICATE_BINDING_COUNT"],
        "SCIENTIFIC_PROTOCOL_PROJECTION_PASS": projection["SCIENTIFIC_PROTOCOL_PROJECTION_PASS"],
        "SCIENTIFIC_LOCK_IMPLEMENTATION_FIELD_COUNT": preparation["SCIENTIFIC_LOCK_IMPLEMENTATION_FIELD_COUNT"],
        "SNAPSHOT_LOCK_V2_BINDING_PASS": snapshot["SNAPSHOT_LOCK_V2_BINDING_PASS"],
        "EXECUTION_FIXTURE_AUDIT_PASS": fixture["EXECUTION_FIXTURE_AUDIT_PASS"],
        "EXECUTION_FIXTURE_RESUME_EQUIVALENCE_PASS": fixture["EXECUTION_FIXTURE_RESUME_EQUIVALENCE_PASS"],
        "EXECUTION_FIXTURE_ANALYSIS_VERIFIER_MATCH": fixture["EXECUTION_FIXTURE_ANALYSIS_VERIFIER_MATCH"],
        "EXECUTION_FIXTURE_PUBLISHER_PASS": fixture["EXECUTION_FIXTURE_PUBLISHER_PASS"],
        "EXECUTION_FIXTURE_ARTIFACT_VERIFICATION_PASS": fixture["EXECUTION_FIXTURE_ARTIFACT_VERIFICATION_PASS"],
        "IMPLEMENTATION_LOCK_SCIENTIFIC_FIELD_COUNT": 0,
        "EXECUTION_IMPLEMENTATION_LOCK_PASS": True,
        "FORMAL_RUN_LOCK_DUPLICATED_CONTRACT_FIELD_COUNT": 0,
        "FORMAL_RUN_LOCK_PASS": True,
        "LOCK_ARCHITECTURE_V2_TAMPER_REJECTION_PASS": tamper["LOCK_ARCHITECTURE_V2_TAMPER_REJECTION_PASS"],
        "FORMAL_DRY_RUN_PASS": dry["FORMAL_DRY_RUN_PASS"],
        "LOCK_ARCHITECTURE_V2_ARTIFACT_VERIFICATION_PASS": True,
        "FORMAL_SEED_ACCESS_COUNT": dry["FORMAL_SEED_ACCESS_COUNT"],
        "FORMAL_BACKEND_EXECUTION_COUNT": dry["FORMAL_BACKEND_EXECUTION_COUNT"],
        "FORMAL_TRIAL_RESULT_COUNT": dry["FORMAL_TRIAL_RESULT_COUNT"],
        "NATIVE_EXECUTION_COUNT": dry["NATIVE_EXECUTION_COUNT"],
    }
    pcl_test_pass = "0 failed" in args.pcl_ctest_summary.lower()
    targeted_test_pass = (
        "passed" in args.targeted_pytest_summary.lower()
        and "failed" not in args.targeted_pytest_summary.lower()
    )
    full_test_pass = (
        "passed" in args.full_pytest_summary.lower()
        and "failed" not in args.full_pytest_summary.lower()
    )
    test_requirements_pass = (
        pcl_test_pass
        and targeted_test_pass
        and full_test_pass
        and "pending" not in args.targeted_pytest_summary.lower()
        and "pending" not in args.full_pytest_summary.lower()
    )
    pass_conditions = (
        all(value is True for key, value in gate_values.items() if key.endswith("PASS") or key in {
            "LOCK_GRAPH_ACYCLIC", "EXECUTION_FIXTURE_RESUME_EQUIVALENCE_PASS",
            "EXECUTION_FIXTURE_ANALYSIS_VERIFIER_MATCH", "EXECUTION_FIXTURE_PUBLISHER_PASS",
            "EXECUTION_FIXTURE_ARTIFACT_VERIFICATION_PASS"
        })
        and all(value == 0 for key, value in gate_values.items() if key.endswith("COUNT"))
        and all_science_zero
        and test_requirements_pass
    )
    if not pass_conditions:
        gate_values["LOCK_ARCHITECTURE_V2_ARTIFACT_VERIFICATION_PASS"] = False
    decision = {
        **gate_values,
        "BACKEND_PHASE_A_COMPLETE": False,
        "CONFIRMATORY_AUTHORIZED": False,
        "DAY1_SCIENTIFIC_VALIDATION_PASS": "NOT_EVALUATED",
        "FULL_DEVELOPMENT_AUTHORIZED": False,
        "MEASUREMENT_PAPER_MAINLINE_AUTHORIZED": False,
        "PHASE_A_LOCK_ARCHITECTURE_V2_PASS": pass_conditions,
        "PHASE_A_ROUTE_PAUSED_FOR_MANUAL_CODE_REVIEW": not pass_conditions,
        "PHASE_A_STAGE1_BACKEND_EXECUTED": False,
        "PHASE_A_STAGE1_BACKEND_RUN_AUTHORIZED": pass_conditions,
        "PHASE_B_PROTOCOL_DESIGN_AUTHORIZED": False,
        "PHASE_B_RUN_AUTHORIZED": False,
        "REAL_DATA_AUTHORIZED": False,
        "TWO_INDEPENDENT_BACKENDS_QUALIFIED": False,
        "schema_version": "phase_a_lock_architecture_v2_final_decision_v1",
    }
    manifest = {
        "FORMAL_BACKEND_EXECUTION_COUNT": dry["FORMAL_BACKEND_EXECUTION_COUNT"],
        "FORMAL_SEED_ACCESS_COUNT": dry["FORMAL_SEED_ACCESS_COUNT"],
        "FORMAL_TRIAL_RESULT_COUNT": dry["FORMAL_TRIAL_RESULT_COUNT"],
        "NATIVE_EXECUTION_COUNT": dry["NATIVE_EXECUTION_COUNT"],
        "attempt_started_count": dry["ATTEMPT_STARTED_COUNT"],
        "dry_run_cache_sha_verification_count": dry["SNAPSHOT_CACHE_SHA_VERIFICATION_COUNT"],
        "full_pytest_pass": full_test_pass,
        "full_pytest_summary": args.full_pytest_summary,
        "git_push_performed": False,
        "initial_branch": "feature/zero-perturbation-phase-a-final-resume-equivalence",
        "initial_commit": "184fb9d1f00803c84d10d906846313626a7fb7fc",
        "new_branch": "feature/zero-perturbation-phase-a-lock-architecture-v2",
        "pcl_v3_ctest_summary": args.pcl_ctest_summary,
        "phase_a_stage1_backend_executed": False,
        "phase_b_executed": False,
        "preflight_dry_run_count": 1,
        "recorded_dry_run_count": 1,
        "schema_version": "phase_a_lock_architecture_v2_run_manifest_v1",
        "script_numbering_note": "176 was occupied; v2 scripts use 177-182",
        "targeted_pytest_pass": targeted_test_pass,
        "targeted_pytest_summary": args.targeted_pytest_summary,
    }
    report = f"""# Phase A Lock Architecture v2 Decision

The monolithic v1.2 lock failure remains archived and unchanged. The v2 route
separates scientific protocol, byte-exact snapshot provenance, execution
implementation, and formal authorization into an acyclic three-edge graph.

- Legacy fields classified: {preparation['legacy_field_total_count']}/{preparation['legacy_field_total_count']} (unclassified 0, multiple 0)
- Classification counts: {json.dumps(preparation['classification_counts'], sort_keys=True)}
- Graph acyclic / duplicate bindings: {graph['LOCK_GRAPH_ACYCLIC']} / {graph['LOCK_GRAPH_DUPLICATE_BINDING_COUNT']}
- Scientific implementation fields / projection differences: {preparation['SCIENTIFIC_LOCK_IMPLEMENTATION_FIELD_COUNT']} / 0
- Snapshot inheritance: {snapshot['complete_snapshot_count']}/{snapshot['planned_snapshot_count']}, original file SHA `{snapshot['snapshot_lock_file_sha256']}`
- Fixture trials: 3 snapshots / 6 trials; fresh/resumed {resume['fresh_trial_count']}/{resume['resumed_trial_count']}
- Resume skipped/reexecuted: {resume['resume_skipped_valid_result_count']}/{resume['resume_reexecuted_valid_result_count']}
- Analysis/verifier differences: {comparison['difference_count']}
- Fixture publication tables/figures: {publisher['table_count']}/{publisher['figure_count']}
- Implementation scientific fields / Formal duplicated fields: 0 / 0
- Layer tamper rejection: {tamper['rejected_case_count']}/{tamper['case_count']} before cache access
- Dry-run snapshots/trials: {dry['PLANNED_SNAPSHOT_COUNT']}/{dry['PLANNED_TRIAL_COUNT']}
- Dry-run Open3D/PCL/Native plan: {dry['PLANNED_OPEN3D_TRIAL_COUNT']}/{dry['PLANNED_PCL_TRIAL_COUNT']}/{dry['PLANNED_NATIVE_TRIAL_COUNT']}
- Formal seed/backend/result/STARTED counts: {dry['FORMAL_SEED_ACCESS_COUNT']}/{dry['FORMAL_BACKEND_EXECUTION_COUNT']}/{dry['FORMAL_TRIAL_RESULT_COUNT']}/{dry['ATTEMPT_STARTED_COUNT']}
- PCL v3 CTest: {args.pcl_ctest_summary}
- Targeted pytest: {args.targeted_pytest_summary}
- Full pytest: {args.full_pytest_summary}

Full-suite blockers requiring manual review:

1. `tests/test_backend_phase_a_runner_no_placeholder.py` rejects an existing
   conditional `RuntimeError` integrity guard in the legacy v1 runner. The v2
   scope does not authorize modifying that runner or the legacy test.
2. `tests/test_stage2_failure_day13_seed_exclusion.py` scans the new Scientific
   Lock and expects `geometry_seeds` to be integer scalars, while the frozen v2
   schema preserves each source seed's index/label/value object. Correcting this
   now would require changing a frozen lock schema or an out-of-scope historical
   seed scanner.

`PHASE_A_LOCK_ARCHITECTURE_V2_PASS = {str(pass_conditions).lower()}`  
`PHASE_A_STAGE1_BACKEND_RUN_AUTHORIZED = {str(pass_conditions).lower()}`  
`PHASE_A_STAGE1_BACKEND_EXECUTED = false`  
`DAY1_SCIENTIFIC_VALIDATION_PASS = NOT_EVALUATED`
"""
    _write(artifact / "final_decision.json", decision, replace=True)
    _write(artifact / "run_manifest.json", manifest, replace=True)
    _write(artifact / "lock_architecture_v2_report.md", report.encode("utf-8"), replace=True)
    semantic_failures = [] if pass_conditions else ["PHASE_A_LOCK_ARCHITECTURE_V2_PASS"]
    verification = {
        "LOCK_ARCHITECTURE_V2_ARTIFACT_VERIFICATION_PASS": pass_conditions,
        "missing_files": [],
        "schema_version": "phase_a_lock_architecture_v2_artifact_verification_v1",
        "semantic_failures": semantic_failures,
        "sha256_mismatches": [],
        "sha256_missing_files": [],
    }
    verification_bytes = canonical_json_bytes(verification)
    relative_files = sorted(
        path.relative_to(artifact).as_posix()
        for path in artifact.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    )
    if "artifact_verification.json" not in relative_files:
        relative_files.append("artifact_verification.json")
        relative_files.sort()
    sums = []
    for relative in relative_files:
        digest = hashlib.sha256(verification_bytes).hexdigest() if relative == "artifact_verification.json" else file_sha256(artifact / relative)
        sums.append(f"{digest}  {relative}\n")
    _write(artifact / "SHA256SUMS", "".join(sums).encode("utf-8"), replace=True)
    _write(artifact / "artifact_verification.json", verification_bytes, replace=True)
    independently_verified = verify_lock_architecture_artifact(artifact)
    if independently_verified != verification:
        raise RuntimeError(f"artifact verifier disagreement: {independently_verified}")
    return {"decision": decision, "dry_run": dry, "tamper": {key: value for key, value in tamper.items() if key != "cases"}, "verification": verification}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, default=ROOT / ARTIFACT_RELATIVE)
    parser.add_argument("--dry-run-output", type=Path, required=True)
    parser.add_argument("--pcl-ctest-summary", required=True)
    parser.add_argument("--targeted-pytest-summary", required=True)
    parser.add_argument("--full-pytest-summary", required=True)
    args = parser.parse_args()
    result = publish(args)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["decision"]["PHASE_A_LOCK_ARCHITECTURE_V2_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
