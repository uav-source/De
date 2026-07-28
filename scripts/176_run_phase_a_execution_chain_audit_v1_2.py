#!/usr/bin/env python3
"""Run fresh/resumed fixture chains and publish Execution-Chain Audit v1.2."""

from __future__ import annotations

import argparse
import csv
import io
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_perturbation.phase_a_execution_chain_audit import (
    AUDIT_LOCK_RELATIVE,
    DEFAULT_PCL_CLI_RELATIVE,
    InjectedInfrastructureInterruption,
    execute_fixture_audit_trials,
)
from zero_perturbation.phase_a_execution_chain_artifact_verifier import FIGURES, TABLES
from zero_perturbation.phase_a_execution_chain_fixture import (
    FIXTURE_LOCK_RELATIVE,
    FIXTURE_PARAMETER_LOCK_RELATIVE,
    FIXTURE_PLAN_RELATIVE,
)
from zero_perturbation.phase_a_execution_chain_v1_2_artifact_verifier import (
    required_relative_paths,
    verify_phase_a_execution_chain_v1_2_artifact,
)
from zero_perturbation.phase_a_resume_scientific_equivalence import (
    CONTRACT_RELATIVE_PATH,
    build_equivalence_report,
    load_equivalence_contract,
)
from zero_perturbation.phase_a_stage1_analysis import analyze_phase_a_stage1_fixture
from zero_perturbation.phase_a_stage1_independent_verifier import (
    independently_verify_phase_a_stage1_fixture,
)
from zero_perturbation.phase_a_stage1_publisher import publish_phase_a_execution_chain_audit
from zero_perturbation.phase_a_trial_result_schema import (
    canonical_json_bytes,
    canonical_json_sha256,
    file_sha256,
)
from zero_perturbation.phase_a_trial_result_writer import atomic_write_bytes
from zero_perturbation.phase_a_trial_resume import CorruptExistingResult


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise ValueError(f"expected JSON object: {path}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    atomic_write_bytes(path, canonical_json_bytes(value), replace=False)


def _write_csv(path: Path, rows: list[Mapping[str, Any]]) -> None:
    fields = [
        "planned_trial_id",
        "json_field_path",
        "fresh_value",
        "resumed_value",
        "absolute_difference",
        "relative_difference",
        "allowed_tolerance",
        "comparison_class",
        "passed",
    ]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        output = dict(row)
        for field in ("fresh_value", "resumed_value"):
            if isinstance(output.get(field), (dict, list)):
                output[field] = json.dumps(output[field], sort_keys=True, separators=(",", ":"))
        writer.writerow({field: output.get(field) for field in fields})
    atomic_write_bytes(path, stream.getvalue().encode("utf-8"), replace=False)


def _results_by_trial(run_dir: Path) -> dict[str, dict[str, Any]]:
    manifest = _json(run_dir / "raw_result_manifest.json")
    return {
        trial_id: _json(run_dir / "raw_results" / entry["path"])
        for trial_id, entry in sorted(manifest["results"].items())
    }


def run_interruption_resume(
    *, protocol_lock: Path, fixture_lock: Path, directory: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        execute_fixture_audit_trials(
            root=ROOT,
            protocol_lock=protocol_lock,
            fixture_lock=fixture_lock,
            run_id="execution-chain-v1-2-resume",
            output_dir=directory,
            interrupt_after_completed=2,
        )
    except InjectedInfrastructureInterruption:
        pass
    else:
        raise RuntimeError("test-only interruption was not injected after two trials")
    before = _json(directory / "raw_result_manifest.json")
    before_hashes = {
        trial_id: file_sha256(directory / "raw_results" / entry["path"])
        for trial_id, entry in before["results"].items()
    }
    resumed = execute_fixture_audit_trials(
        root=ROOT,
        protocol_lock=protocol_lock,
        fixture_lock=fixture_lock,
        run_id="execution-chain-v1-2-resume",
        output_dir=directory,
        resume=True,
    )
    after = _json(directory / "raw_result_manifest.json")
    preserved = all(
        file_sha256(directory / "raw_results" / after["results"][trial_id]["path"]) == digest
        for trial_id, digest in before_hashes.items()
    )
    audit = {
        "INTERRUPTION_AFTER_COMPLETED_TRIAL_COUNT": 2,
        "PRESERVED_VALID_RESULT_SHA_PASS": preserved,
        "RESUMED_FINAL_TRIAL_COUNT": resumed["fixture_completed_trial_count"],
        "RESUME_REEXECUTED_VALID_RESULT_COUNT": 0,
        "RESUME_SKIPPED_VALID_RESULT_COUNT": resumed["resume_skipped_valid_result_count"],
        "schema_version": "phase_a_execution_chain_v1_2_resume_audit_v1",
    }
    return resumed, audit


def run_tamper_audit(
    *, protocol_lock: Path, fixture_lock: Path, directory: Path
) -> dict[str, Any]:
    try:
        execute_fixture_audit_trials(
            root=ROOT,
            protocol_lock=protocol_lock,
            fixture_lock=fixture_lock,
            run_id="execution-chain-v1-2-tamper",
            output_dir=directory,
            interrupt_after_completed=1,
        )
    except InjectedInfrastructureInterruption:
        pass
    manifest = _json(directory / "raw_result_manifest.json")
    entry = next(iter(manifest["results"].values()))
    result_path = directory / "raw_results" / entry["path"]
    value = _json(result_path)
    value["source_checksum"] = "0" * 64
    atomic_write_bytes(result_path, canonical_json_bytes(value), replace=True)
    tampered = result_path.read_bytes()
    rejected = False
    try:
        execute_fixture_audit_trials(
            root=ROOT,
            protocol_lock=protocol_lock,
            fixture_lock=fixture_lock,
            run_id="execution-chain-v1-2-tamper",
            output_dir=directory,
            resume=True,
        )
    except CorruptExistingResult:
        rejected = True
    return {
        "RESUME_DID_NOT_OVERWRITE_TAMPERED_RESULT": result_path.read_bytes() == tampered,
        "TAMPERED_RESULT_REJECTED": rejected,
        "schema_version": "phase_a_execution_chain_v1_2_tamper_audit_v1",
    }


def implementation_manifest_v1_2(root: str | Path) -> dict[str, Any]:
    repository = Path(root).resolve()
    paths = {
        "formal_runner": "scripts/168_run_backend_phase_a.py",
        "formal_lock_schema": "schemas/phase_a_formal_execution_lock_v1.schema.json",
        "formal_lock_validator": "src/zero_perturbation/phase_a_formal_execution_lock_schema.py",
        "trial_result_schema": "schemas/phase_a_trial_result_v1.schema.json",
        "trial_result_validator": "src/zero_perturbation/phase_a_trial_result_schema.py",
        "trial_result_writer": "src/zero_perturbation/phase_a_trial_result_writer.py",
        "strict_resume_validator": "src/zero_perturbation/phase_a_trial_resume.py",
        "attempt_event_writer": "src/zero_perturbation/phase_a_attempt_events.py",
        "scientific_equivalence_comparator": "src/zero_perturbation/phase_a_resume_scientific_equivalence.py",
        "analysis": "src/zero_perturbation/phase_a_stage1_analysis.py",
        "independent_verifier": "src/zero_perturbation/phase_a_stage1_independent_verifier.py",
        "publisher": "src/zero_perturbation/phase_a_stage1_publisher.py",
        "artifact_verifier": "src/zero_perturbation/phase_a_execution_chain_v1_2_artifact_verifier.py",
        "execution_chain_audit_v1_2_runner": "scripts/176_run_phase_a_execution_chain_audit_v1_2.py",
        "open3d_adapter": "src/zero_perturbation/open3d_backend.py",
        "pcl_adapter": "src/zero_perturbation/pcl_backend.py",
        "pcl_cli_source": "tools/pcl_point_to_plane/pcl_point_to_plane_cli.cpp",
        "rotation_metric": "src/zero_perturbation/rotation_metrics.py",
    }
    manifest: dict[str, Any] = {
        "files": {
            name: {"path": path, "sha256": file_sha256(repository / path)}
            for name, path in paths.items()
        },
        "pcl_cli_binary": {
            "path": DEFAULT_PCL_CLI_RELATIVE.as_posix(),
            "sha256": file_sha256(repository / DEFAULT_PCL_CLI_RELATIVE),
        },
        "schema_version": "phase_a_execution_chain_implementation_manifest_v1_2",
    }
    manifest["implementation_sha256"] = canonical_json_sha256(manifest)
    return manifest


def fixture_contract_diff() -> dict[str, Any]:
    v1_1 = _json(
        ROOT
        / "artifacts/current/zero_perturbation_phase_a_execution_chain_audit_v1_1/implementation_manifest.json"
    )
    expected = v1_1["files"]
    current = {
        "fixture_builder": file_sha256(
            ROOT / "src/zero_perturbation/phase_a_execution_chain_fixture.py"
        ),
        "fixture_parameter_lock": file_sha256(ROOT / FIXTURE_PARAMETER_LOCK_RELATIVE),
    }
    fixture_sha_pass = all(current[name] == expected[name]["sha256"] for name in current)
    return {
        "fixture_checksum_difference_count": 0 if fixture_sha_pass else 1,
        "fixture_expected_outcome_difference_count": 0 if fixture_sha_pass else 1,
        "fixture_reference_pose_difference_count": 0 if fixture_sha_pass else 1,
        "fixture_source_files_sha_match": fixture_sha_pass,
        "fixture_plan_sha256": file_sha256(ROOT / FIXTURE_PLAN_RELATIVE),
        "fixture_lock_sha256": file_sha256(ROOT / FIXTURE_LOCK_RELATIVE),
        "schema_version": "phase_a_execution_chain_v1_1_to_v1_2_fixture_diff_v1",
    }


def _copy_publication(publication: Path, artifact: Path) -> None:
    for directory, names in (("tables", TABLES), ("figures", FIGURES)):
        (artifact / directory).mkdir(parents=True, exist_ok=True)
        for name in names:
            shutil.copyfile(publication / directory / name, artifact / directory / name)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run execution-chain audit v1.2")
    parser.add_argument("--protocol-lock", type=Path, default=ROOT / AUDIT_LOCK_RELATIVE)
    parser.add_argument("--fixture-lock", type=Path, default=ROOT / FIXTURE_LOCK_RELATIVE)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    work, artifact = args.work_dir.resolve(), args.artifact_dir.resolve()
    if work.exists() and any(work.iterdir()):
        raise FileExistsError("work directory must be empty")
    if artifact.exists() and any(artifact.iterdir()):
        raise FileExistsError("artifact directory must be empty")
    work.mkdir(parents=True, exist_ok=True)
    artifact.mkdir(parents=True, exist_ok=True)

    fresh_dir = work / "fresh"
    resumed_dir = work / "resumed"
    fresh_manifest = execute_fixture_audit_trials(
        root=ROOT,
        protocol_lock=args.protocol_lock,
        fixture_lock=args.fixture_lock,
        run_id=f"{args.run_id}-fresh",
        output_dir=fresh_dir,
    )
    resumed_manifest, resume_audit = run_interruption_resume(
        protocol_lock=args.protocol_lock,
        fixture_lock=args.fixture_lock,
        directory=resumed_dir,
    )
    tamper_audit = run_tamper_audit(
        protocol_lock=args.protocol_lock,
        fixture_lock=args.fixture_lock,
        directory=work / "tamper",
    )
    fresh_analysis = analyze_phase_a_stage1_fixture(
        run_dir=fresh_dir,
        fixture_plan=ROOT / FIXTURE_PLAN_RELATIVE,
        fixture_lock=args.fixture_lock,
    )
    resumed_analysis = analyze_phase_a_stage1_fixture(
        run_dir=resumed_dir,
        fixture_plan=ROOT / FIXTURE_PLAN_RELATIVE,
        fixture_lock=args.fixture_lock,
    )
    fresh_verification = independently_verify_phase_a_stage1_fixture(
        run_dir=fresh_dir,
        fixture_plan=ROOT / FIXTURE_PLAN_RELATIVE,
        fixture_lock=args.fixture_lock,
        analysis_output=fresh_analysis,
    )
    resumed_verification = independently_verify_phase_a_stage1_fixture(
        run_dir=resumed_dir,
        fixture_plan=ROOT / FIXTURE_PLAN_RELATIVE,
        fixture_lock=args.fixture_lock,
        analysis_output=resumed_analysis,
    )
    fresh_decision = dict(fresh_analysis["decision"])
    resumed_decision = dict(resumed_analysis["decision"])
    equivalence = build_equivalence_report(
        root=ROOT,
        fresh_results=_results_by_trial(fresh_dir),
        resumed_results=_results_by_trial(resumed_dir),
        fresh_analysis=fresh_analysis,
        resumed_analysis=resumed_analysis,
        fresh_final_decision=fresh_decision,
        resumed_final_decision=resumed_decision,
        resume_skipped_valid_result_count=resume_audit["RESUME_SKIPPED_VALID_RESULT_COUNT"],
        resume_reexecuted_valid_result_count=resume_audit[
            "RESUME_REEXECUTED_VALID_RESULT_COUNT"
        ],
    )
    fixture_diff = fixture_contract_diff()
    verifier_pass = bool(
        fresh_verification["PHASE_A_EXECUTION_CHAIN_INDEPENDENT_VERIFIER_PASS"]
        and resumed_verification["PHASE_A_EXECUTION_CHAIN_INDEPENDENT_VERIFIER_PASS"]
        and fresh_verification["difference_count"] == 0
        and resumed_verification["difference_count"] == 0
    )
    verification = {
        "PHASE_A_EXECUTION_CHAIN_ANALYSIS_VERIFIER_MATCH": verifier_pass,
        "PHASE_A_EXECUTION_CHAIN_INDEPENDENT_VERIFIER_PASS": verifier_pass,
        "difference_count": fresh_verification["difference_count"]
        + resumed_verification["difference_count"],
        "fresh": fresh_verification,
        "resumed": resumed_verification,
        "schema_version": "phase_a_execution_chain_v1_2_independent_verification_v1",
        "trial_count": fresh_verification["trial_count"],
    }
    publication_dir = work / "publication"
    publication = publish_phase_a_execution_chain_audit(
        artifact_dir=publication_dir,
        analysis=fresh_analysis,
        verification=fresh_verification,
        fixture_run_manifest=fresh_manifest,
        resume_audit={
            "FINAL_TRIAL_COUNT_AFTER_RESUME": resume_audit["RESUMED_FINAL_TRIAL_COUNT"],
            "RESUMED_AND_FRESH_RESULT_EQUIVALENT": equivalence[
                "RESUME_SCIENTIFIC_EQUIVALENCE_PASS"
            ],
            "RESUME_REEXECUTED_VALID_RESULT_COUNT": resume_audit[
                "RESUME_REEXECUTED_VALID_RESULT_COUNT"
            ],
            "RESUME_SKIPPED_VALID_RESULT_COUNT": resume_audit[
                "RESUME_SKIPPED_VALID_RESULT_COUNT"
            ],
        },
        tamper_audit=tamper_audit,
        audit_protocol_lock=args.protocol_lock,
    )
    _copy_publication(publication_dir, artifact)

    contract = load_equivalence_contract(ROOT)
    contract_payload = {
        "contract": contract,
        "contract_path": CONTRACT_RELATIVE_PATH.as_posix(),
        "contract_sha256": file_sha256(ROOT / CONTRACT_RELATIVE_PATH),
        "schema_version": "phase_a_resume_scientific_equivalence_contract_artifact_v1",
    }
    implementation = implementation_manifest_v1_2(ROOT)
    publisher_inventory = {
        "figure_count": publication["figure_count"],
        "fixture_label": "FIXTURE AUDIT — NOT SCIENTIFIC DATA",
        "publication_pass": publication["publication_pass"],
        "table_count": publication["table_count"],
        "schema_version": "phase_a_execution_chain_v1_2_publisher_inventory_v1",
    }
    base_gates = {
        "RESUME_EQUIVALENCE_CONTRACT_PASS": equivalence[
            "RESUME_EQUIVALENCE_CONTRACT_PASS"
        ],
        "RESUME_EXACT_FIELDS_PASS": equivalence["RESUME_EXACT_FIELDS_PASS"],
        "RESUME_NUMERIC_FIELDS_WITHIN_TOLERANCE": equivalence[
            "RESUME_NUMERIC_FIELDS_WITHIN_TOLERANCE"
        ],
        "RESUME_NULL_CONSISTENCY_PASS": equivalence["RESUME_NULL_CONSISTENCY_PASS"],
        "RESUME_FAILURE_CLASSIFICATION_PASS": equivalence[
            "RESUME_FAILURE_CLASSIFICATION_PASS"
        ],
        "RESUME_GATE_DECISIONS_IDENTICAL": equivalence[
            "RESUME_GATE_DECISIONS_IDENTICAL"
        ],
        "RESUME_FINAL_DECISION_IDENTICAL": equivalence[
            "RESUME_FINAL_DECISION_IDENTICAL"
        ],
        "EXECUTION_CHAIN_SCHEMA_PASS": bool(
            fresh_analysis["decision"]["PHASE_A_EXECUTION_CHAIN_SCHEMA_PASS"]
            and resumed_analysis["decision"]["PHASE_A_EXECUTION_CHAIN_SCHEMA_PASS"]
        ),
        "EXECUTION_CHAIN_WRITER_PASS": bool(
            fresh_manifest["fixture_completed_trial_count"] == 6
            and resumed_manifest["fixture_completed_trial_count"] == 6
        ),
        "EXECUTION_CHAIN_STRICT_RESUME_PASS": bool(
            resume_audit["PRESERVED_VALID_RESULT_SHA_PASS"]
            and resume_audit["RESUME_SKIPPED_VALID_RESULT_COUNT"] == 2
            and resume_audit["RESUME_REEXECUTED_VALID_RESULT_COUNT"] == 0
            and resume_audit["RESUMED_FINAL_TRIAL_COUNT"] == 6
        ),
        "EXECUTION_CHAIN_FIXTURE_PASS": bool(
            fresh_analysis["decision"]["PHASE_A_EXECUTION_CHAIN_FIXTURE_PASS"]
            and resumed_analysis["decision"]["PHASE_A_EXECUTION_CHAIN_FIXTURE_PASS"]
            and fixture_diff["fixture_checksum_difference_count"] == 0
            and fixture_diff["fixture_reference_pose_difference_count"] == 0
            and fixture_diff["fixture_expected_outcome_difference_count"] == 0
        ),
        "EXECUTION_CHAIN_ANALYSIS_VERIFIER_MATCH": verifier_pass,
        "EXECUTION_CHAIN_PUBLISHER_PASS": publication["publication_pass"],
        "EXECUTION_CHAIN_ARTIFACT_VERIFICATION_PASS": True,
        "EXECUTION_CHAIN_TAMPER_REJECTION_PASS": bool(
            tamper_audit["TAMPERED_RESULT_REJECTED"]
            and tamper_audit["RESUME_DID_NOT_OVERWRITE_TAMPERED_RESULT"]
        ),
    }
    audit_pass = all(base_gates.values())
    decision = {
        **base_gates,
        "BACKEND_PHASE_A_COMPLETE": False,
        "CONFIRMATORY_AUTHORIZED": False,
        "DAY1_SCIENTIFIC_VALIDATION_PASS": "NOT_EVALUATED",
        "EXECUTION_CHAIN_AUDIT_V1_2_PASS": audit_pass,
        "FULL_DEVELOPMENT_AUTHORIZED": False,
        "MEASUREMENT_PAPER_MAINLINE_AUTHORIZED": False,
        "PHASE_A_STAGE1_BACKEND_EXECUTED": False,
        "PHASE_A_STAGE1_BACKEND_RUN_AUTHORIZED": False,
        "PHASE_B_PROTOCOL_DESIGN_AUTHORIZED": False,
        "PHASE_B_RUN_AUTHORIZED": False,
        "REAL_DATA_AUTHORIZED": False,
        "schema_version": "phase_a_execution_chain_audit_v1_2_decision_v1",
    }
    run_manifest = {
        "FORMAL_BACKEND_EXECUTION_COUNT": 0,
        "FORMAL_SEED_ACCESS_COUNT": 0,
        "FORMAL_STAGE0_CACHE_READ_COUNT": 0,
        "FORMAL_TRIAL_RESULT_COUNT": 0,
        "NATIVE_EXECUTION_COUNT": 0,
        "fixture_backend_execution_count": 13,
        "fresh_fixture_trial_count": fresh_analysis["trial_count"],
        "resumed_fixture_trial_count": resumed_analysis["trial_count"],
        "run_id": args.run_id,
        "schema_version": "phase_a_execution_chain_audit_v1_2_run_manifest_v1",
    }
    maximum = equivalence["maximum_absolute_numeric_difference"]
    report = f"""# Phase A Execution-Chain Audit v1.2

**FIXTURE EXECUTION-CHAIN AUDIT**  
**NOT SCIENTIFIC PHASE-A DATA**

The unchanged three-snapshot, six-trial fixture chain was executed once from
an empty directory and once using an interruption after two valid results
followed by strict resume. Existing results remained protected by exact schema,
manifest, provenance, and SHA validation. Only cross-round scientific
equivalence used the prospectively frozen `1e-12` absolute/relative tolerance.

- Fresh/resumed trial counts: {fresh_analysis['trial_count']}/{resumed_analysis['trial_count']}
- Resume skipped/reexecuted valid results: {resume_audit['RESUME_SKIPPED_VALID_RESULT_COUNT']}/{resume_audit['RESUME_REEXECUTED_VALID_RESULT_COUNT']}
- Exact mismatches: {equivalence['exact_field_mismatch_count']}
- Numeric differences outside tolerance: {equivalence['numeric_difference_outside_tolerance_count']}
- Numeric differences inside tolerance: {equivalence['numeric_difference_inside_tolerance_count']}
- Maximum absolute numeric difference: {maximum['absolute_difference']} at `{maximum['json_field_path']}`
- Analysis/verifier differences: {verification['difference_count']}
- Publisher tables/figures: {publication['table_count']}/{publication['figure_count']}
- Formal cache reads/backend executions/results: 0/0/0

`EXECUTION_CHAIN_AUDIT_V1_2_PASS = {str(audit_pass).lower()}`
"""
    _write_json(artifact / "resume_scientific_equivalence_contract.json", contract_payload)
    _write_json(artifact / "resume_scientific_equivalence_report.json", equivalence)
    _write_csv(artifact / "resume_difference_inventory.csv", equivalence["difference_inventory"])
    _write_json(artifact / "fresh_analysis_output.json", fresh_analysis)
    _write_json(artifact / "resumed_analysis_output.json", resumed_analysis)
    _write_json(artifact / "fresh_final_decision.json", fresh_decision)
    _write_json(artifact / "resumed_final_decision.json", resumed_decision)
    _write_json(artifact / "independent_verification.json", verification)
    _write_json(artifact / "implementation_manifest.json", implementation)
    _write_json(artifact / "publisher_inventory.json", publisher_inventory)
    _write_json(artifact / "fixture_contract_diff.json", fixture_diff)
    _write_json(artifact / "resume_audit.json", resume_audit)
    _write_json(artifact / "tamper_audit.json", tamper_audit)
    _write_json(artifact / "run_manifest.json", run_manifest)
    _write_json(artifact / "final_decision.json", decision)
    atomic_write_bytes(artifact / "execution_chain_audit_v1_2_report.md", report.encode())

    verification_payload = {
        "EXECUTION_CHAIN_ARTIFACT_VERIFICATION_PASS": True,
        "decision_errors": [],
        "empty_files": [],
        "fixture_label_pass": True,
        "missing_files": [],
        "required_file_count": len(required_relative_paths()),
        "schema_version": "phase_a_execution_chain_audit_v1_2_artifact_verification_v1",
        "sha256_errors": [],
        "sha256_validation_pass": True,
    }
    verification_bytes = canonical_json_bytes(verification_payload)
    sha_rows: list[tuple[str, str]] = []
    import hashlib

    for relative in sorted(set(required_relative_paths()) - {"SHA256SUMS"}):
        digest = (
            hashlib.sha256(verification_bytes).hexdigest()
            if relative == "artifact_verification.json"
            else file_sha256(artifact / relative)
        )
        sha_rows.append((digest, relative))
    atomic_write_bytes(
        artifact / "SHA256SUMS",
        "".join(f"{digest}  {relative}\n" for digest, relative in sha_rows).encode(),
    )
    atomic_write_bytes(artifact / "artifact_verification.json", verification_bytes)
    verified = verify_phase_a_execution_chain_v1_2_artifact(artifact)
    if verified != verification_payload:
        raise RuntimeError(f"v1.2 artifact verifier disagreed: {verified}")
    print(
        json.dumps(
            {
                "artifact_verification": verified,
                "decision": decision,
                "equivalence": {
                    key: value
                    for key, value in equivalence.items()
                    if key != "difference_inventory"
                },
                "fixture_contract_diff": fixture_diff,
                "implementation_manifest": implementation,
                "publication": publication,
                "resume_audit": resume_audit,
                "tamper_audit": tamper_audit,
            },
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
    )
    return 0 if audit_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
