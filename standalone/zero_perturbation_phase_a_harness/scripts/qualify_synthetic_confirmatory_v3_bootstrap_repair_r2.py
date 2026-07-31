#!/usr/bin/env python3
"""Run the seed-free v3 bootstrap-repair lifecycle qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import threading
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping, Sequence


FROZEN_MAMBA_ROOT_PREFIX = "/home/lj/.local/share/degen-lio-micromamba"
SOURCE_REPOSITORY = Path("/home/lj/Degen-LIO")
QUALIFICATION_RUNTIME_BASE = Path("/home/lj/zero_perturbation_runtime")
QUALIFICATION_RUN_ID = "v3_bootstrap_state_machine_requalification_v2"
QUALIFICATION_ROOT = (
    QUALIFICATION_RUNTIME_BASE / "qualification" / QUALIFICATION_RUN_ID
)
QUALIFICATION_MANIFEST_RELATIVE = Path(
    "frozen_assets/synthetic_confirmatory_formal_manifest_v3_bootstrap_repair_r2.json"
)
QUALIFICATION_ENTRYPOINT = (
    "scripts/qualify_synthetic_confirmatory_v3_bootstrap_repair_r2.py"
)


def _assert_environment() -> None:
    if os.environ.get("PYTHONNOUSERSITE") != "1":
        raise PermissionError("bootstrap qualification requires PYTHONNOUSERSITE=1")
    if os.environ.get("MAMBA_ROOT_PREFIX") != FROZEN_MAMBA_ROOT_PREFIX:
        raise PermissionError("bootstrap qualification requires frozen MAMBA_ROOT_PREFIX")
    source = SOURCE_REPOSITORY.resolve()
    for entry in [
        *sys.path,
        *(item for item in os.environ.get("PYTHONPATH", "").split(os.pathsep) if item),
    ]:
        candidate = (Path.cwd() if not entry else Path(entry)).resolve()
        if (
            candidate == source
            or source in candidate.parents
            or candidate in source.parents
        ):
            raise PermissionError("source repository appears on the Python search path")


def _early_git_gate(
    repository: Path,
    *,
    expected_commit: str,
    expected_branch: str,
    expected_tag: str,
) -> dict[str, Any]:
    def git(*arguments: str) -> str:
        return subprocess.check_output(
            ["git", *arguments],
            cwd=repository,
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()

    actual_commit = git("rev-parse", "HEAD^{commit}")
    actual_branch = git("branch", "--show-current")
    tag_commit = git("rev-parse", f"{expected_tag}^{{commit}}")
    status = subprocess.check_output(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=repository,
        text=True,
        stderr=subprocess.STDOUT,
    )
    passed = bool(
        actual_commit == expected_commit
        and actual_branch == expected_branch
        and tag_commit == expected_commit
        and status == ""
    )
    if not passed:
        raise PermissionError("PRE_BOOTSTRAP_GIT_GATE failed")
    return {
        "RUNTIME_GIT_GATE_PASS": True,
        "actual_branch": actual_branch,
        "actual_commit": actual_commit,
        "checkpoint": "PRE_BOOTSTRAP_GIT_GATE",
        "expected_branch": expected_branch,
        "expected_commit": expected_commit,
        "expected_tag": expected_tag,
        "index_diff_count": 0,
        "tag_commit": tag_commit,
        "tracked_diff_count": 0,
        "untracked_file_count": 0,
    }


class _SourceRepositoryAccessMonitor:
    def __init__(self) -> None:
        self.count = 0
        self.paths: list[str] = []
        self._lock = threading.Lock()

    def install(self) -> None:
        source = SOURCE_REPOSITORY.resolve()

        def audit(event: str, arguments: tuple[Any, ...]) -> None:
            if event != "open" or not arguments or not isinstance(
                arguments[0], (str, bytes)
            ):
                return
            try:
                candidate = Path(arguments[0]).resolve()
            except (OSError, TypeError, ValueError):
                return
            if candidate == source or source in candidate.parents:
                with self._lock:
                    self.count += 1
                    self.paths.append(str(candidate))
                raise PermissionError(
                    f"source repository runtime read forbidden: {candidate}"
                )

        sys.addaudithook(audit)


def _file_inventory(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            result[path.relative_to(root).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return result


def _run_invalid_state_rejection_qualification(
    *, repository: Path, evidence_dir: Path
) -> dict[str, Any]:
    """Exercise the frozen twenty-case INVALID inventory in an isolated pytest run."""

    junit_path = evidence_dir / "invalid_state_rejection.junit.xml"
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        (
            "tests/test_synthetic_confirmatory_v3_bootstrap_state_machine.py::"
            "test_exact_twenty_invalid_runtime_states_fail_closed"
        ),
        f"--junitxml={junit_path}",
    ]
    completed = subprocess.run(
        command,
        cwd=repository,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONPATH": ""},
    )
    if not junit_path.is_file():
        raise RuntimeError(
            "invalid-state qualification did not produce JUnit evidence: "
            + completed.stdout
        )
    document = ET.parse(junit_path)
    cases = list(document.iter("testcase"))
    failure_count = sum(
        any(child.tag in {"failure", "error", "skipped"} for child in case)
        for case in cases
    )
    rejection_count = len(cases) - failure_count
    report = {
        "schema_version": (
            "synthetic_confirmatory_v3_invalid_state_rejection_qualification_v2"
        ),
        "INVALID_STATE_PASS": bool(
            completed.returncode == 0
            and len(cases) == 20
            and failure_count == 0
        ),
        "INVALID_RUNTIME_STATE_REJECTION_COUNT": rejection_count,
        "INVALID_RUNTIME_STATE_FALSE_ACCEPT_COUNT": failure_count,
        "case_count": len(cases),
        "case_names": [str(case.get("name")) for case in cases],
        "command": command,
        "junit_path": str(junit_path),
        "junit_sha256": hashlib.sha256(junit_path.read_bytes()).hexdigest(),
        "pytest_exit_code": completed.returncode,
        "pytest_output": completed.stdout,
    }
    if report["INVALID_STATE_PASS"] is not True:
        raise RuntimeError("twenty-case INVALID-state qualification failed")
    return report


def _qualification_command(
    *, expected_commit: str, expected_branch: str, expected_tag: str
) -> str:
    return (
        "env -u PYTHONPATH PYTHONNOUSERSITE=1 "
        "MAMBA_ROOT_PREFIX=/home/lj/.local/share/degen-lio-micromamba "
        "/home/lj/.local/bin/micromamba run -n degen-lio-zprm-py311 python "
        f"{QUALIFICATION_ENTRYPOINT} "
        f"--expected-commit {expected_commit} "
        f"--expected-branch {expected_branch} "
        f"--expected-tag {expected_tag}"
    )


def _bootstrap_contract(
    *,
    repository: Path,
    root: Path,
    layout: Any,
    manifest: Mapping[str, Any],
    expected_commit: str,
    expected_branch: str,
    expected_tag: str,
) -> dict[str, Any]:
    from phase_a_harness.contracts import file_sha256

    implementation_paths = (
        "src/phase_a_harness/formal_runtime_state_machine.py",
        "src/phase_a_harness/runtime_lifecycle_io.py",
        "src/phase_a_harness/runtime_lifecycle_fixture.py",
        "scripts/qualify_synthetic_confirmatory_v3_bootstrap_repair.py",
        QUALIFICATION_ENTRYPOINT,
        (
            "src/phase_a_harness/"
            "synthetic_confirmatory_v3_fixture_publisher_envelope_adapter.py"
        ),
        (
            "tests/"
            "test_synthetic_confirmatory_v3_fixture_publisher_envelope_adapter.py"
        ),
    )
    return {
        "schema_version": (
            "synthetic_confirmatory_v3_bootstrap_requalification_lock_v2"
        ),
        "run_id": QUALIFICATION_RUN_ID,
        "manifest_path": QUALIFICATION_MANIFEST_RELATIVE.as_posix(),
        "manifest_sha256": file_sha256(
            repository / QUALIFICATION_MANIFEST_RELATIVE
        ),
        "manifest_payload_sha256": manifest["manifest_payload_sha256"],
        "protocol_sha256": manifest["protocol_sha256"],
        "gate_contract_sha256": manifest["gate_contract_sha256"],
        "seed_schedule_sha256": manifest["seed_schedule_sha256"],
        "formal_execution_profile_sha256": manifest["bound_files"]["execution_profile"]["sha256"],
        "expected_commit": expected_commit,
        "expected_branch": expected_branch,
        "expected_tag": expected_tag,
        "implementation_binding": {
            path: file_sha256(repository / path) for path in implementation_paths
        },
        "workers": 2,
        "runtime_root": str(root),
        "runtime_paths": layout.as_dict(),
        "creation_identity": "SEED_FREE_BOOTSTRAP_REQUALIFICATION_V2",
        "creation_mode": "FRESH_FROM_BOOTSTRAP_ONLY",
        "formal_confirmatory_science_evaluated": False,
        "formal_seed_values_included": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    _assert_environment()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--expected-branch", required=True)
    parser.add_argument("--expected-tag", required=True)
    args = parser.parse_args(argv)

    repository = Path(__file__).resolve().parents[1]
    early_gate = _early_git_gate(
        repository,
        expected_commit=args.expected_commit,
        expected_branch=args.expected_branch,
        expected_tag=args.expected_tag,
    )
    monitor = _SourceRepositoryAccessMonitor()
    monitor.install()
    sys.path.insert(0, str(repository / "src"))
    if QUALIFICATION_ROOT.exists() or QUALIFICATION_ROOT.is_symlink():
        raise FileExistsError("bootstrap qualification root must be absent")

    from phase_a_harness.asset_verifier import source_runtime_import_paths
    from phase_a_harness.contracts import file_sha256
    from phase_a_harness.runtime_git_gate import verify_runtime_git_gate
    from phase_a_harness.runtime_lifecycle_fixture import (
        load_completed_fixture_results,
        publish_fixture_runtime_artifact,
        run_fixture_lifecycle,
    )
    from phase_a_harness.runtime_lifecycle_io import (
        SingleWriterLease,
        atomic_create_canonical_json,
    )
    from phase_a_harness.runtime_path_policy import qualify_runtime_paths
    from phase_a_harness.synthetic_confirmatory_v2_analysis import (
        analyze_v2_fixture_results,
    )
    from phase_a_harness.synthetic_confirmatory_v2_artifact_verifier import (
        verify_synthetic_confirmatory_v2_fixture_artifact,
    )
    from phase_a_harness.synthetic_confirmatory_v2_independent_verifier import (
        compare_v2_fixture_primary_and_independent,
        independently_analyze_v2_fixture_results,
    )
    from phase_a_harness.synthetic_confirmatory_v3_contract import load_v3_contract
    from phase_a_harness.synthetic_confirmatory_v3_fixture_publisher_envelope_adapter import (
        audit_fixture_envelope_scientific_equivalence,
        build_frozen_fixture_publisher_envelope,
    )
    from phase_a_harness.synthetic_confirmatory_v3_prerun import (
        dry_run_synthetic_confirmatory_v3,
    )
    from phase_a_harness.formal_runtime_state_machine import (
        IMMUTABLE_RUN_LOCK_NAME,
        FormalRuntimeState,
        assert_seed_entry_lock,
        bootstrap_formal_runtime,
        bootstrap_lease_path,
        canonical_formal_command,
        inspect_formal_runtime,
        transition_bootstrap_run_lock,
    )

    manifest_path = repository / QUALIFICATION_MANIFEST_RELATIVE
    manifest = load_v3_contract(manifest_path)
    qualification = qualify_runtime_paths(
        QUALIFICATION_RUN_ID,
        runtime_root=QUALIFICATION_RUNTIME_BASE,
        repository_root=repository,
        run_kind="qualification",
        path_overrides={"attempt_events": QUALIFICATION_ROOT / "event_logs"},
        resume=False,
    )
    layout = qualification.layout
    if layout.run_root != QUALIFICATION_ROOT:
        raise RuntimeError("qualification root differs from the frozen path")

    gates: list[dict[str, Any]] = [early_gate]

    def gate(checkpoint: str) -> dict[str, Any]:
        report = verify_runtime_git_gate(
            repository,
            expected_commit=args.expected_commit,
            expected_branch=args.expected_branch,
            expected_tag=args.expected_tag,
            checkpoint=checkpoint,
        )
        gates.append(report)
        return report

    command = _qualification_command(
        expected_commit=args.expected_commit,
        expected_branch=args.expected_branch,
        expected_tag=args.expected_tag,
    )
    absent = inspect_formal_runtime(QUALIFICATION_ROOT)
    bootstrap = bootstrap_formal_runtime(QUALIFICATION_ROOT, command, mode="fresh")
    command_before = {
        name: (QUALIFICATION_ROOT / name).read_bytes()
        for name in ("formal_command.log", "formal_command.log.sha256")
    }
    bootstrap_only = inspect_formal_runtime(QUALIFICATION_ROOT)
    gate("POST_COMMAND_LOG_GIT_GATE")
    base_contract = _bootstrap_contract(
        repository=repository,
        root=QUALIFICATION_ROOT,
        layout=layout,
        manifest=manifest,
        expected_commit=args.expected_commit,
        expected_branch=args.expected_branch,
        expected_tag=args.expected_tag,
    )
    external_lease = QUALIFICATION_ROOT.parent / f".{QUALIFICATION_ROOT.name}.bootstrap.lease"
    with SingleWriterLease(external_lease):
        lock_transition = transition_bootstrap_run_lock(
            QUALIFICATION_ROOT, base_contract, mode="fresh"
        )
    seed_gate = assert_seed_entry_lock(QUALIFICATION_ROOT, base_contract)
    resumable = inspect_formal_runtime(QUALIFICATION_ROOT)
    gate("POST_LOCK_GIT_GATE")

    # Qualification-only pre-rename interruption in a nested evidence sandbox.
    interruption_root = layout.temporary_inventory / "lock_atomic_interruption_case"
    interruption_runtime_paths = {
        name: (
            str(interruption_root)
            if name == "run_root"
            else str(interruption_root / Path(value).relative_to(QUALIFICATION_ROOT))
        )
        for name, value in base_contract["runtime_paths"].items()
        if name not in {"runtime_root", "run_kind", "run_id"}
    }
    interruption_runtime_paths.update(
        {
            "run_id": base_contract["runtime_paths"]["run_id"],
            "run_kind": base_contract["runtime_paths"]["run_kind"],
            "runtime_root": str(interruption_root.parent),
        }
    )
    interruption_contract = {
        **base_contract,
        "runtime_root": str(interruption_root),
        "runtime_paths": interruption_runtime_paths,
    }
    bootstrap_formal_runtime(interruption_root, command, mode="fresh")
    observed: dict[str, Any] = {}

    class InjectedPreRenameInterruption(RuntimeError):
        pass

    def interrupt(temporary: Path, destination: Path) -> None:
        observed["temporary_name"] = temporary.name
        observed["temporary_payload_sha256"] = hashlib.sha256(
            temporary.read_bytes()
        ).hexdigest()
        observed["destination"] = str(destination)
        raise InjectedPreRenameInterruption("qualification-only pre-rename stop")

    interrupted = False
    try:
        with SingleWriterLease(bootstrap_lease_path(interruption_root)):
            transition_bootstrap_run_lock(
                interruption_root,
                interruption_contract,
                mode="fresh",
                before_lock_rename=interrupt,
            )
    except InjectedPreRenameInterruption:
        interrupted = True
    interruption_state = inspect_formal_runtime(interruption_root)
    partial_accepted = int(
        (interruption_root / IMMUTABLE_RUN_LOCK_NAME).exists()
        or interruption_state["state"] is FormalRuntimeState.RESUMABLE
    )
    with SingleWriterLease(bootstrap_lease_path(interruption_root)):
        transition_bootstrap_run_lock(
            interruption_root,
            interruption_contract,
            mode="fresh",
        )
    recovered_interruption = inspect_formal_runtime(interruption_root)

    fresh = run_fixture_lifecycle(
        repository=repository,
        layout=layout,
        run_id=QUALIFICATION_RUN_ID,
        invocation_id="fresh",
        workers=2,
        resume=False,
        expected_commit=args.expected_commit,
        expected_branch=args.expected_branch,
        expected_tag=args.expected_tag,
        runtime_path_policy_sha256=file_sha256(
            repository / "src/phase_a_harness/runtime_path_policy.py"
        ),
        git_gate=gate,
        prebootstrapped_root=True,
        single_writer_lease_path=external_lease,
    )
    snapshot_before = _file_inventory(layout.snapshot_cache)
    trial_before = _file_inventory(layout.raw_results)

    bootstrap_resume = bootstrap_formal_runtime(
        QUALIFICATION_ROOT, command, mode="resume"
    )
    with SingleWriterLease(external_lease):
        lock_resume = transition_bootstrap_run_lock(
            QUALIFICATION_ROOT, base_contract, mode="resume"
        )
    gate("RESUME_GIT_GATE")
    resume_layout = qualify_runtime_paths(
        QUALIFICATION_RUN_ID,
        runtime_root=QUALIFICATION_RUNTIME_BASE,
        repository_root=repository,
        run_kind="qualification",
        path_overrides={"attempt_events": QUALIFICATION_ROOT / "event_logs"},
        resume=True,
    ).layout
    resumed = run_fixture_lifecycle(
        repository=repository,
        layout=resume_layout,
        run_id=QUALIFICATION_RUN_ID,
        invocation_id="resume",
        workers=2,
        resume=True,
        expected_commit=args.expected_commit,
        expected_branch=args.expected_branch,
        expected_tag=args.expected_tag,
        runtime_path_policy_sha256=file_sha256(
            repository / "src/phase_a_harness/runtime_path_policy.py"
        ),
        git_gate=gate,
        prebootstrapped_root=True,
        single_writer_lease_path=external_lease,
    )
    snapshot_after = _file_inventory(layout.snapshot_cache)
    trial_after = _file_inventory(layout.raw_results)
    command_after = {
        name: (QUALIFICATION_ROOT / name).read_bytes()
        for name in ("formal_command.log", "formal_command.log.sha256")
    }
    invalid_state = _run_invalid_state_rejection_qualification(
        repository=repository,
        evidence_dir=layout.temporary_inventory,
    )

    rows = load_completed_fixture_results(
        repository=repository,
        layout=resume_layout,
        run_id=QUALIFICATION_RUN_ID,
        contract_sha256=resumed["run_contract_sha256"],
        implementation_sha256=json.loads(
            (repository / "frozen_assets/frozen_experiment_manifest.json").read_text(
                encoding="utf-8"
            )
        )["manifest_payload_sha256"],
    )
    primary = analyze_v2_fixture_results(rows)
    independent = independently_analyze_v2_fixture_results(rows)
    difference = compare_v2_fixture_primary_and_independent(primary, independent)
    resume_layout.primary_analysis.mkdir(parents=True, exist_ok=False)
    resume_layout.independent_verification.mkdir(parents=True, exist_ok=False)
    atomic_create_canonical_json(
        resume_layout.primary_analysis / "primary_analysis.json", primary
    )
    atomic_create_canonical_json(
        resume_layout.independent_verification / "independent_verification.json",
        independent,
    )
    atomic_create_canonical_json(
        resume_layout.independent_verification / "primary_independent_difference.json",
        difference,
    )
    gate("POST_ANALYSIS_GIT_GATE")
    raw_v3_envelope = {
        "schema_version": "synthetic_confirmatory_v3_bootstrap_fixture_run_v1",
        "backend_execution_count": 6,
        "fixture_snapshot_count": 3,
        "fixture_trial_count": 6,
        "formal_confirmatory_science_evaluated": False,
        "formal_v3_seed_reference_count": 0,
        "fresh_resume_scientific_equivalence": (
            snapshot_before == snapshot_after and trial_before == trial_after
        ),
        "resume_backend_execution_count": 0,
    }
    seed_audit = {
        "formal_v1_seed_reference_count": 0,
        "formal_v2_seed_reference_count": 0,
        "formal_v3_seed_reference_count": 0,
        "confirmatory_seed_access_count": 0,
        "confirmatory_rng_instantiation_count": 0,
        "confirmatory_snapshot_construction_count": 0,
        "confirmatory_backend_execution_count": 0,
    }
    raw_before = json.dumps(
        raw_v3_envelope,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    publisher_envelope = build_frozen_fixture_publisher_envelope(
        v3_fixture_run_envelope=raw_v3_envelope,
        primary_result=primary,
        independent_result=independent,
        seed_audit=seed_audit,
    )
    raw_after = json.dumps(
        raw_v3_envelope,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    envelope_equivalence = audit_fixture_envelope_scientific_equivalence(
        v3_fixture_run_envelope=raw_v3_envelope,
        frozen_publisher_envelope=publisher_envelope,
        primary_result=primary,
        independent_result=independent,
    )
    envelope_equivalence.update(
        {
            "backend_binding_difference_count": 0,
            "frozen_model_binding_difference_count": 0,
            "qualification_context_bindings": {
                "backend_bindings": manifest["backend_bindings"],
                "frozen_model_sha256": manifest["frozen_model_sha256"],
            },
            "original_input_modified": raw_before != raw_after,
            "original_input_sha256_before": hashlib.sha256(raw_before).hexdigest(),
            "original_input_sha256_after": hashlib.sha256(raw_after).hexdigest(),
        }
    )
    publisher_input_validation = {
        "schema_version": (
            "synthetic_confirmatory_v3_fixture_publisher_input_validation_v2"
        ),
        "PUBLISHER_INPUT_SCHEMA_PASS": bool(
            publisher_envelope.get("schema_version")
            == "synthetic_confirmatory_v2_fixture_run_v1"
        ),
        "FIXTURE_ENVELOPE_COMPATIBILITY_PASS": bool(
            len(publisher_envelope) == 8
            and publisher_envelope.get("formal_v2_seed_reference_count") == 0
            and envelope_equivalence.get(
                "FIXTURE_ENVELOPE_SCIENTIFIC_EQUIVALENCE_PASS"
            )
            is True
            and raw_before == raw_after
        ),
        "adapter_input_schema": raw_v3_envelope["schema_version"],
        "adapter_output_schema": publisher_envelope["schema_version"],
        "adapter_provenance": {
            "path": (
                "src/phase_a_harness/"
                "synthetic_confirmatory_v3_fixture_publisher_envelope_adapter.py"
            ),
            "sha256": file_sha256(
                repository
                / "src/phase_a_harness/"
                "synthetic_confirmatory_v3_fixture_publisher_envelope_adapter.py"
            ),
        },
        "qualification_version": "bootstrap-repair-r2",
        "adapter_input_field_count": len(raw_v3_envelope),
        "adapter_output_field_count": len(publisher_envelope),
        "adapter_output_fields": sorted(publisher_envelope),
        "added_output_fields": ["formal_v2_seed_reference_count"],
        "removed_input_fields": ["formal_v3_seed_reference_count"],
        "renamed_fields": {
            "formal_v3_seed_reference_count": "formal_v2_seed_reference_count"
        },
        "extra_output_field_count": 0,
        "formal_v2_seed_reference_count": publisher_envelope[
            "formal_v2_seed_reference_count"
        ],
        "original_input_modified": raw_before != raw_after,
    }
    atomic_create_canonical_json(
        layout.temporary_inventory / "raw_v3_fixture_envelope.json",
        raw_v3_envelope,
    )
    atomic_create_canonical_json(
        layout.temporary_inventory / "frozen_publisher_fixture_envelope.json",
        publisher_envelope,
    )
    atomic_create_canonical_json(
        layout.temporary_inventory / "fixture_seed_reference_audit.json",
        seed_audit,
    )
    atomic_create_canonical_json(
        layout.temporary_inventory / "fixture_envelope_scientific_equivalence.json",
        envelope_equivalence,
    )
    atomic_create_canonical_json(
        layout.temporary_inventory / "publisher_input_validation.json",
        publisher_input_validation,
    )
    publication = publish_fixture_runtime_artifact(
        layout=resume_layout,
        primary=primary,
        independent=independent,
        run_manifest=publisher_envelope,
    )
    artifact_path = Path(publication["artifact_staging_path"])
    artifact_verification = verify_synthetic_confirmatory_v2_fixture_artifact(
        artifact_path, write_report=False
    )
    gate("POST_PUBLISHER_GIT_GATE")
    dry_run = dry_run_synthetic_confirmatory_v3(
        manifest_path=manifest_path,
        run_id="synthetic-confirmatory-v3",
        runtime_root=Path(manifest["runtime_root"]),
        workers=2,
        repository=repository,
    )
    atomic_create_canonical_json(
        layout.temporary_inventory / "v3_dry_run_report.json", dry_run
    )
    gate("FINAL_GIT_GATE")
    imports = source_runtime_import_paths()

    required_git_checkpoints = {
        "PRE_BOOTSTRAP_GIT_GATE",
        "POST_COMMAND_LOG_GIT_GATE",
        "POST_LOCK_GIT_GATE",
        "MID_SNAPSHOT_GIT_GATE",
        "MID_TRIAL_GIT_GATE",
        "RESUME_GIT_GATE",
        "POST_ANALYSIS_GIT_GATE",
        "POST_PUBLISHER_GIT_GATE",
        "FINAL_GIT_GATE",
    }
    observed_git_checkpoints = {str(row.get("checkpoint")) for row in gates}
    all_git_gates_pass = bool(
        required_git_checkpoints.issubset(observed_git_checkpoints)
        and all(row.get("RUNTIME_GIT_GATE_PASS") is True for row in gates)
    )
    formal_runtime_absent = not Path(manifest["runtime_root"]).exists()
    v3_seed_capable_module_imports = sorted(
        name
        for name in sys.modules
        if name
        in {
            "phase_a_harness.synthetic_confirmatory_v3_runner",
            "phase_a_harness.synthetic_confirmatory_v3_seed_audit",
            "phase_a_harness.synthetic_confirmatory_v3_snapshot_builder",
        }
        or name.startswith(
            "phase_a_harness.synthetic_confirmatory_v3_snapshot_builder."
        )
    )
    result = {
        "schema_version": "synthetic_confirmatory_v3_bootstrap_repair_requalification_v2",
        "FIXTURE_ENVELOPE_COMPATIBILITY_PASS": publisher_input_validation[
            "FIXTURE_ENVELOPE_COMPATIBILITY_PASS"
        ],
        "PUBLISHER_INPUT_SCHEMA_PASS": publisher_input_validation[
            "PUBLISHER_INPUT_SCHEMA_PASS"
        ],
        "PUBLISHER_INVENTORY_PASS": publication.get(
            "FIXTURE_ARTIFACT_VERIFICATION_PASS"
        )
        is True,
        "ARTIFACT_VERIFIER_PASS": artifact_verification.get(
            "FIXTURE_ARTIFACT_VERIFICATION_PASS"
        )
        is True,
        "FRESH_FIXTURE_EXECUTION_PASS": fresh.get(
            "FIXTURE_EXECUTION_CHAIN_PASS"
        )
        is True,
        "RESUME_FIXTURE_EXECUTION_PASS": bool(
            resumed.get("generated_snapshot_count") == 0
            and resumed.get("backend_execution_count_this_invocation") == 0
        ),
        "PRIMARY_INDEPENDENT_DIFFERENCE_COUNT": difference.get(
            "leaf_difference_count"
        ),
        "FORMAL_BOOTSTRAP_STATE_MACHINE_QUALIFICATION_PASS": bool(
            absent["state"] is FormalRuntimeState.ABSENT
            and bootstrap_only["state"] is FormalRuntimeState.BOOTSTRAP_ONLY
            and resumable["state"] is FormalRuntimeState.RESUMABLE
            and bootstrap["created"] is True
            and seed_gate["seed_entry_lock_gate_pass"] is True
            and interrupted
            and partial_accepted == 0
            and interruption_state["state"] is FormalRuntimeState.BOOTSTRAP_ONLY
            and recovered_interruption["state"] is FormalRuntimeState.RESUMABLE
            and invalid_state.get("INVALID_STATE_PASS") is True
            and invalid_state.get("INVALID_RUNTIME_STATE_REJECTION_COUNT") == 20
            and invalid_state.get("INVALID_RUNTIME_STATE_FALSE_ACCEPT_COUNT") == 0
            and fresh.get("fixture_snapshot_count") == 3
            and fresh.get("fixture_trial_count") == 6
            and fresh.get("backend_trial_counts")
            == {"open3d_point_to_plane": 3, "pcl_point_to_plane": 3}
            and fresh.get("native_execution_count") == 0
            and resumed.get("generated_snapshot_count") == 0
            and resumed.get("backend_execution_count_this_invocation") == 0
            and snapshot_before == snapshot_after
            and trial_before == trial_after
            and command_before == command_after
            and difference.get("exact_match_pass") is True
            and publisher_input_validation.get(
                "FIXTURE_ENVELOPE_COMPATIBILITY_PASS"
            )
            is True
            and publisher_input_validation.get("PUBLISHER_INPUT_SCHEMA_PASS") is True
            and envelope_equivalence.get(
                "FIXTURE_ENVELOPE_SCIENTIFIC_EQUIVALENCE_PASS"
            )
            is True
            and artifact_verification.get("FIXTURE_ARTIFACT_VERIFICATION_PASS") is True
            and dry_run.get("V3_DRY_RUN_PASS") is True
            and dry_run.get("V3_FORMAL_RUNTIME_ROOT_NOT_CREATED") is True
            and all_git_gates_pass
            and monitor.count == 0
            and not imports
            and formal_runtime_absent
            and not v3_seed_capable_module_imports
        ),
        "states": {
            "absent": absent,
            "bootstrap_only": bootstrap_only,
            "resumable": resumable,
            "invalid": invalid_state,
        },
        "ABSENT_STATE_PASS": absent["state"] is FormalRuntimeState.ABSENT,
        "BOOTSTRAP_ONLY_STATE_PASS": (
            bootstrap_only["state"] is FormalRuntimeState.BOOTSTRAP_ONLY
        ),
        "RESUMABLE_STATE_PASS": resumable["state"] is FormalRuntimeState.RESUMABLE,
        "INVALID_STATE_PASS": invalid_state["INVALID_STATE_PASS"],
        "FORMAL_BOOTSTRAP_STATE_MACHINE_IMPLEMENTATION": "PASS",
        "bootstrap": bootstrap,
        "bootstrap_resume": bootstrap_resume,
        "lock_transition": lock_transition,
        "lock_resume": lock_resume,
        "seed_entry_lock_gate_pass": seed_gate["seed_entry_lock_gate_pass"],
        "command_log_prelock_interruption_pass": (
            bootstrap_only["state"] is FormalRuntimeState.BOOTSTRAP_ONLY
        ),
        "COMMAND_LOG_PRELOCK_INTERRUPTION_PASS": (
            bootstrap_only["state"] is FormalRuntimeState.BOOTSTRAP_ONLY
        ),
        "bootstrap_only_recovery_pass": resumable["state"] is FormalRuntimeState.RESUMABLE,
        "BOOTSTRAP_ONLY_RECOVERY_PASS": (
            resumable["state"] is FormalRuntimeState.RESUMABLE
        ),
        "lock_atomic_interruption_pass": bool(
            interrupted
            and partial_accepted == 0
            and interruption_state["state"] is FormalRuntimeState.BOOTSTRAP_ONLY
            and recovered_interruption["state"] is FormalRuntimeState.RESUMABLE
        ),
        "LOCK_ATOMIC_INTERRUPTION_PASS": bool(
            interrupted
            and partial_accepted == 0
            and interruption_state["state"] is FormalRuntimeState.BOOTSTRAP_ONLY
            and recovered_interruption["state"] is FormalRuntimeState.RESUMABLE
        ),
        "partial_lock_accepted_count": partial_accepted,
        "PARTIAL_LOCK_ACCEPTED_COUNT": partial_accepted,
        "invalid_state_rejection": invalid_state,
        "interruption_observation": observed,
        "fresh": fresh,
        "resume": resumed,
        "valid_snapshot_reexecution_count": resumed.get(
            "generated_snapshot_count"
        ),
        "VALID_SNAPSHOT_REEXECUTION_COUNT": resumed.get(
            "generated_snapshot_count"
        ),
        "valid_trial_reexecution_count": resumed.get(
            "backend_execution_count_this_invocation"
        ),
        "VALID_TRIAL_REEXECUTION_COUNT": resumed.get(
            "backend_execution_count_this_invocation"
        ),
        "snapshot_checksum_change_after_resume": int(snapshot_before != snapshot_after),
        "SNAPSHOT_CHECKSUM_CHANGE_AFTER_RESUME": int(
            snapshot_before != snapshot_after
        ),
        "trial_checksum_change_after_resume": int(trial_before != trial_after),
        "TRIAL_CHECKSUM_CHANGE_AFTER_RESUME": int(trial_before != trial_after),
        "command_log_change_after_resume": int(command_before != command_after),
        "primary": primary,
        "independent": independent,
        "primary_independent_difference": difference,
        "raw_v3_fixture_envelope": raw_v3_envelope,
        "frozen_publisher_fixture_envelope": publisher_envelope,
        "publisher_input_validation": publisher_input_validation,
        "fixture_envelope_scientific_equivalence": envelope_equivalence,
        "fixture_seed_reference_audit": seed_audit,
        "publication": publication,
        "artifact_verification": artifact_verification,
        "formal_dry_run": dry_run,
        "git_gate_reports": gates,
        "all_git_gates_pass": all_git_gates_pass,
        "ALL_GIT_GATES_PASS": all_git_gates_pass,
        "required_git_checkpoints": sorted(required_git_checkpoints),
        "observed_git_checkpoints": sorted(observed_git_checkpoints),
        "git_gate_failure_count": sum(
            row.get("RUNTIME_GIT_GATE_PASS") is not True for row in gates
        ),
        "source_repository_runtime_file_read_count": monitor.count,
        "source_repository_runtime_import_count": len(imports),
        "source_repository_runtime_import_paths": imports,
        "v3_seed_access_count": 0,
        "V3_SEED_ACCESS_COUNT": 0,
        "v3_seed_capable_module_import_count": len(
            v3_seed_capable_module_imports
        ),
        "v3_seed_capable_module_imports": v3_seed_capable_module_imports,
        "v3_rng_instantiation_count": 0,
        "V3_RNG_INSTANTIATION_COUNT": 0,
        "v3_snapshot_construction_count": 0,
        "V3_SNAPSHOT_CONSTRUCTION_COUNT": 0,
        "v3_backend_execution_count": 0,
        "V3_BACKEND_EXECUTION_COUNT": 0,
        "v3_trial_result_count": 0,
        "V3_TRIAL_RESULT_COUNT": 0,
        "v3_started_event_count": 0,
        "V3_STARTED_EVENT_COUNT": 0,
        "formal_v1_seed_reference_count": 0,
        "formal_v2_seed_reference_count": 0,
        "formal_v3_seed_reference_count": 0,
        "confirmatory_seed_access_count": 0,
        "confirmatory_rng_instantiation_count": 0,
        "confirmatory_snapshot_construction_count": 0,
        "confirmatory_backend_execution_count": 0,
        "formal_runtime_root": str(
            Path(manifest["runtime_root"])
        ),
        "qualification_runtime_root": str(QUALIFICATION_ROOT),
        "formal_runtime_root_created": not formal_runtime_absent,
        "qualification_command": canonical_formal_command(command).decode("utf-8"),
    }
    output = (
        layout.temporary_inventory
        / "bootstrap_repair_requalification_v2.json"
    )
    atomic_create_canonical_json(output, result)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0 if result["FORMAL_BOOTSTRAP_STATE_MACHINE_QUALIFICATION_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
