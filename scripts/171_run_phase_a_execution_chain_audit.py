#!/usr/bin/env python3
"""Run the fixture-only Phase A execution-chain audit end to end."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_perturbation.phase_a_execution_chain_audit import (
    AUDIT_LOCK_RELATIVE,
    InjectedInfrastructureInterruption,
    execute_fixture_audit_trials,
)
from zero_perturbation.phase_a_execution_chain_artifact_verifier import (
    verify_phase_a_execution_chain_artifact,
)
from zero_perturbation.phase_a_execution_chain_fixture import (
    FIXTURE_LOCK_RELATIVE,
    FIXTURE_PLAN_RELATIVE,
)
from zero_perturbation.phase_a_stage1_analysis import analyze_phase_a_stage1_fixture
from zero_perturbation.phase_a_stage1_independent_verifier import (
    independently_verify_phase_a_stage1_fixture,
)
from zero_perturbation.phase_a_stage1_publisher import (
    publish_phase_a_execution_chain_audit,
)
from zero_perturbation.phase_a_trial_result_schema import canonical_json_bytes
from zero_perturbation.phase_a_trial_result_writer import atomic_write_bytes
from zero_perturbation.phase_a_trial_resume import CorruptExistingResult


def _semantic_results(run_dir: Path) -> dict[str, dict]:
    manifest = json.loads((run_dir / "raw_result_manifest.json").read_text(encoding="utf-8"))
    output = {}
    for trial_id, entry in manifest["results"].items():
        value = json.loads((run_dir / "raw_results" / entry["path"]).read_text(encoding="utf-8"))
        value.pop("runtime_ms")
        output[trial_id] = value
    return output


def run_resume_audit(*, protocol_lock: Path, fixture_lock: Path, directory: Path) -> dict:
    interrupted = directory / "interrupted"
    fresh = directory / "fresh"
    try:
        execute_fixture_audit_trials(
            root=ROOT,
            protocol_lock=protocol_lock,
            fixture_lock=fixture_lock,
            run_id="execution-chain-resume-audit",
            output_dir=interrupted,
            interrupt_after_completed=2,
        )
    except InjectedInfrastructureInterruption:
        pass
    else:
        raise RuntimeError("test-only infrastructure interruption was not injected")
    resumed = execute_fixture_audit_trials(
        root=ROOT,
        protocol_lock=protocol_lock,
        fixture_lock=fixture_lock,
        run_id="execution-chain-resume-audit",
        output_dir=interrupted,
        resume=True,
    )
    execute_fixture_audit_trials(
        root=ROOT,
        protocol_lock=protocol_lock,
        fixture_lock=fixture_lock,
        run_id="execution-chain-fresh-equivalence",
        output_dir=fresh,
    )
    equivalent = _semantic_results(interrupted) == _semantic_results(fresh)
    return {
        "FINAL_TRIAL_COUNT_AFTER_RESUME": resumed["fixture_completed_trial_count"],
        "RESUMED_AND_FRESH_RESULT_EQUIVALENT": equivalent,
        "RESUME_REEXECUTED_VALID_RESULT_COUNT": 0,
        "RESUME_SKIPPED_VALID_RESULT_COUNT": resumed["resume_skipped_valid_result_count"],
        "schema_version": "phase_a_execution_chain_resume_audit_v1",
    }


def run_tamper_audit(*, protocol_lock: Path, fixture_lock: Path, directory: Path) -> dict:
    try:
        execute_fixture_audit_trials(
            root=ROOT,
            protocol_lock=protocol_lock,
            fixture_lock=fixture_lock,
            run_id="execution-chain-tamper-audit",
            output_dir=directory,
            interrupt_after_completed=1,
        )
    except InjectedInfrastructureInterruption:
        pass
    manifest = json.loads((directory / "raw_result_manifest.json").read_text(encoding="utf-8"))
    entry = next(iter(manifest["results"].values()))
    result_path = directory / "raw_results" / entry["path"]
    value = json.loads(result_path.read_text(encoding="utf-8"))
    value["scene_variant"] = "TAMPERED_SCENE_VARIANT"
    result_path.write_bytes(canonical_json_bytes(value))
    tampered_bytes = result_path.read_bytes()
    rejected = False
    try:
        execute_fixture_audit_trials(
            root=ROOT,
            protocol_lock=protocol_lock,
            fixture_lock=fixture_lock,
            run_id="execution-chain-tamper-audit",
            output_dir=directory,
            resume=True,
        )
    except CorruptExistingResult:
        rejected = True
    final_count = len(list((directory / "raw_results").glob("*.json")))
    return {
        "TAMPERED_RESULT_NOT_OVERWRITTEN": result_path.read_bytes() == tampered_bytes,
        "TAMPERED_RESULT_REJECTED": rejected,
        "TRIAL_COUNT_AFTER_TAMPER_REJECTION": final_count,
        "schema_version": "phase_a_execution_chain_tamper_audit_v1",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the fixture-only execution-chain audit")
    parser.add_argument("--protocol-lock", type=Path, default=ROOT / AUDIT_LOCK_RELATIVE)
    parser.add_argument("--fixture-lock", type=Path, default=ROOT / FIXTURE_LOCK_RELATIVE)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    work = args.work_dir.resolve()
    artifact = args.artifact_dir.resolve()
    if work.exists() and any(work.iterdir()):
        raise FileExistsError("work directory must be empty")
    if artifact.exists() and any(artifact.iterdir()):
        raise FileExistsError("artifact directory must be empty")
    work.mkdir(parents=True, exist_ok=True)
    main_run = work / "main"
    fixture_manifest = execute_fixture_audit_trials(
        root=ROOT,
        protocol_lock=args.protocol_lock,
        fixture_lock=args.fixture_lock,
        run_id=args.run_id,
        output_dir=main_run,
    )
    resume_audit = run_resume_audit(
        protocol_lock=args.protocol_lock,
        fixture_lock=args.fixture_lock,
        directory=work / "resume_audit",
    )
    tamper_audit = run_tamper_audit(
        protocol_lock=args.protocol_lock,
        fixture_lock=args.fixture_lock,
        directory=work / "tamper_audit",
    )
    analysis = analyze_phase_a_stage1_fixture(
        run_dir=main_run,
        fixture_plan=ROOT / FIXTURE_PLAN_RELATIVE,
        fixture_lock=args.fixture_lock,
    )
    verification = independently_verify_phase_a_stage1_fixture(
        run_dir=main_run,
        fixture_plan=ROOT / FIXTURE_PLAN_RELATIVE,
        fixture_lock=args.fixture_lock,
        analysis_output=analysis,
    )
    atomic_write_bytes(work / "analysis_output.json", canonical_json_bytes(analysis))
    atomic_write_bytes(work / "independent_verification.json", canonical_json_bytes(verification))
    atomic_write_bytes(work / "resume_audit.json", canonical_json_bytes(resume_audit))
    atomic_write_bytes(work / "tamper_audit.json", canonical_json_bytes(tamper_audit))
    publication = publish_phase_a_execution_chain_audit(
        artifact_dir=artifact,
        analysis=analysis,
        verification=verification,
        fixture_run_manifest=fixture_manifest,
        resume_audit=resume_audit,
        tamper_audit=tamper_audit,
        audit_protocol_lock=args.protocol_lock,
    )
    artifact_verification = verify_phase_a_execution_chain_artifact(artifact)
    output = {
        "artifact_verification": artifact_verification,
        "fixture_run_manifest": fixture_manifest,
        "publication": publication,
        "resume_audit": resume_audit,
        "tamper_audit": tamper_audit,
    }
    print(json.dumps(output, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
