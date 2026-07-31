#!/usr/bin/env python3
"""Freeze the v3 bootstrap-repair execution profile and formal manifest."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


SOURCE_REPOSITORY = Path("/home/lj/Degen-LIO")
ENV_PREFIX = (
    "env -u PYTHONPATH PYTHONNOUSERSITE=1 "
    "MAMBA_ROOT_PREFIX=/home/lj/.local/share/degen-lio-micromamba "
    "/home/lj/.local/bin/micromamba run -n degen-lio-zprm-py311 python"
)


def _assert_environment(repository: Path) -> None:
    if SOURCE_REPOSITORY.resolve() in repository.parents or repository == SOURCE_REPOSITORY.resolve():
        raise PermissionError("bootstrap repair must run in the standalone harness")
    if os.environ.get("PYTHONNOUSERSITE") != "1":
        raise PermissionError("bootstrap repair freeze requires PYTHONNOUSERSITE=1")
    source = SOURCE_REPOSITORY.resolve()
    for entry in [
        *sys.path,
        *(item for item in os.environ.get("PYTHONPATH", "").split(os.pathsep) if item),
    ]:
        candidate = (Path.cwd() if not entry else Path(entry)).resolve()
        if candidate == source or source in candidate.parents or candidate in source.parents:
            raise PermissionError("source repository appears on the Python search path")


def _git(repository: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=repository, text=True, stderr=subprocess.STDOUT
    ).strip()


def _command(script: str, *arguments: str) -> str:
    return f"{ENV_PREFIX} {shlex.join([script, *arguments])}"


def build_execution_profile(repository: Path) -> dict[str, Any]:
    from phase_a_harness.formal_runtime_state_machine import (
        build_formal_runner_command,
        formal_command_sha256,
    )
    from phase_a_harness.synthetic_confirmatory_v3_contract import (
        EXECUTION_PROFILE_SCHEMA,
        FINAL_DECISION_SCHEMA,
        FORMAL_BRANCH,
        FORMAL_PRERUN_TAG,
        FORMAL_RUN_ID,
        FORMAL_RUNTIME_ROOT,
        FORMAL_WORKERS,
        MANIFEST_RELATIVE,
        PUBLISHER_FIGURES,
        PUBLISHER_ROOT_FILES,
        PUBLISHER_TABLES,
        RUNTIME_PATHS,
        canonical_identity_sha256,
    )

    manifest = MANIFEST_RELATIVE.as_posix()
    runtime = str(FORMAL_RUNTIME_ROOT)
    common_runner = [
        "--manifest", manifest,
        "--run-id", FORMAL_RUN_ID,
        "--runtime-root", runtime,
        "--workers", str(FORMAL_WORKERS),
    ]
    runner_fresh = build_formal_runner_command(
        repository=repository,
        manifest_path=manifest,
        run_id=FORMAL_RUN_ID,
        runtime_root=FORMAL_RUNTIME_ROOT,
        workers=FORMAL_WORKERS,
        mode="fresh",
        entry_script="scripts/run_synthetic_confirmatory_v3.py",
    )
    runner_resume = build_formal_runner_command(
        repository=repository,
        manifest_path=manifest,
        run_id=FORMAL_RUN_ID,
        runtime_root=FORMAL_RUNTIME_ROOT,
        workers=FORMAL_WORKERS,
        mode="resume",
        entry_script="scripts/run_synthetic_confirmatory_v3.py",
    )
    commands = {
        "step_01_preflight_fresh": _command(
            "scripts/preflight_synthetic_confirmatory_v3.py",
            *common_runner,
            "--mode", "fresh",
        ),
        "step_01_preflight_resume": _command(
            "scripts/preflight_synthetic_confirmatory_v3.py",
            *common_runner,
            "--mode", "resume",
        ),
        "step_02_bootstrap_fresh": _command(
            "scripts/bootstrap_synthetic_confirmatory_v3.py",
            "--manifest", manifest,
            "--runtime-root", runtime,
            "--run-id", FORMAL_RUN_ID,
            "--workers", str(FORMAL_WORKERS),
            "--mode", "fresh",
        ),
        "step_02_bootstrap_resume": _command(
            "scripts/bootstrap_synthetic_confirmatory_v3.py",
            "--manifest", manifest,
            "--runtime-root", runtime,
            "--run-id", FORMAL_RUN_ID,
            "--workers", str(FORMAL_WORKERS),
            "--mode", "resume",
        ),
        "step_03_runner_fresh": runner_fresh,
        "step_03_runner_resume": runner_resume,
        "step_04_completeness": _command(
            "scripts/check_synthetic_confirmatory_v3_completeness.py",
            "--manifest", manifest, "--runtime-root", runtime,
        ),
        "step_05_primary": _command(
            "scripts/analyze_synthetic_confirmatory_v3.py",
            "--manifest", manifest, "--runtime-root", runtime,
        ),
        "step_06_independent": _command(
            "scripts/verify_synthetic_confirmatory_v3.py",
            "--manifest", manifest, "--runtime-root", runtime,
        ),
        "step_07_difference": _command(
            "scripts/audit_synthetic_confirmatory_v3_difference.py",
            "--manifest", manifest, "--runtime-root", runtime,
        ),
        "step_08_publisher": _command(
            "scripts/publish_synthetic_confirmatory_v3.py",
            "--manifest", manifest, "--runtime-root", runtime,
        ),
        "step_09_artifact_verifier": _command(
            "scripts/verify_synthetic_confirmatory_v3_artifact.py",
            "--manifest", manifest, "--runtime-root", runtime,
        ),
        "step_10_final_sha": (
            f"sha256sum -c {shlex.quote(str(RUNTIME_PATHS['artifact_staging_path'] / 'SHA256SUMS'))}"
        ),
    }
    core: dict[str, Any] = {
        "bootstrap_contract": {
            "allowed_bootstrap_files": [
                "formal_command.log",
                "formal_command.log.sha256",
            ],
            "formal_command_log_sha256": formal_command_sha256(runner_fresh),
            "formal_command_log_text": runner_fresh,
            "immutable_run_lock_name": "immutable_run_lock.json",
            "implementation_revision": "synthetic_confirmatory_v3_bootstrap_repair_r1",
            "states": [
                "FORMAL_RUNTIME_ABSENT",
                "FORMAL_RUNTIME_BOOTSTRAP_ONLY",
                "FORMAL_RUNTIME_RESUMABLE",
                "FORMAL_RUNTIME_INVALID",
            ],
        },
        "commands": commands,
        "configuration_authority": manifest,
        "entrypoints": {
            "analysis": "scripts/analyze_synthetic_confirmatory_v3.py",
            "artifact_verifier": "scripts/verify_synthetic_confirmatory_v3_artifact.py",
            "bootstrap": "scripts/bootstrap_synthetic_confirmatory_v3.py",
            "completeness": "scripts/check_synthetic_confirmatory_v3_completeness.py",
            "difference_audit": "scripts/audit_synthetic_confirmatory_v3_difference.py",
            "independent_verifier": "scripts/verify_synthetic_confirmatory_v3.py",
            "publisher": "scripts/publish_synthetic_confirmatory_v3.py",
            "preflight": "scripts/preflight_synthetic_confirmatory_v3.py",
            "runner": "scripts/run_synthetic_confirmatory_v3.py",
        },
        "expected_branch": FORMAL_BRANCH,
        "expected_release_tag": FORMAL_PRERUN_TAG,
        "final_decision_schema": FINAL_DECISION_SCHEMA,
        "formal_cli_contract": {
            "explicit_modes": ["fresh", "resume"],
            "required_options": ["--manifest", "--runtime-root", "--run-id", "--workers"],
            "science_override_options": [],
        },
        "formal_execution_state": "NOT_EXECUTED",
        "formal_runtime_creation_count": 0,
        "publisher_inventory": {
            "figure_count": len(PUBLISHER_FIGURES),
            "figures": list(PUBLISHER_FIGURES),
            "root_file_count": len(PUBLISHER_ROOT_FILES),
            "root_files": list(PUBLISHER_ROOT_FILES),
            "table_count": len(PUBLISHER_TABLES),
            "tables": list(PUBLISHER_TABLES),
        },
        "run_id": FORMAL_RUN_ID,
        "runtime_paths": {
            "runtime_root": runtime,
            **{name: str(path) for name, path in RUNTIME_PATHS.items()},
        },
        "schema_version": EXECUTION_PROFILE_SCHEMA,
        "scientific_evaluation_state": "NOT_EVALUATED",
        "this_file_executes_commands": False,
        "workers": FORMAL_WORKERS,
        "zero_instance_counters": {
            "backend_execution_count": 0,
            "rng_instantiation_count": 0,
            "scientific_result_count": 0,
            "seed_access_count": 0,
            "snapshot_construction_count": 0,
            "started_event_count": 0,
            "trial_result_count": 0,
        },
    }
    return {**core, "execution_profile_payload_sha256": canonical_identity_sha256(core)}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args(argv)
    repository = Path(__file__).resolve().parents[1]
    _assert_environment(repository)
    sys.path.insert(0, str(repository / "src"))
    from phase_a_harness.contracts import write_json
    from phase_a_harness.synthetic_confirmatory_v3_contract import (
        EXECUTION_PROFILE_RELATIVE,
        FORMAL_BRANCH,
        FORMAL_RUNTIME_ROOT,
        MANIFEST_RELATIVE,
        load_v3_contract,
        write_manifest,
    )

    if _git(repository, "branch", "--show-current") != FORMAL_BRANCH:
        raise PermissionError("bootstrap repair assets require the exact repair branch")
    if FORMAL_RUNTIME_ROOT.exists():
        raise PermissionError("formal v3 runtime root exists during repair freeze")
    profile_path = repository / EXECUTION_PROFILE_RELATIVE
    manifest_path = repository / MANIFEST_RELATIVE
    if not args.replace and (profile_path.exists() or manifest_path.exists()):
        raise FileExistsError("bootstrap repair asset already exists")
    write_json(profile_path, build_execution_profile(repository))
    manifest = write_manifest(repository, replace=args.replace)
    if load_v3_contract(manifest_path) != manifest:
        raise RuntimeError("bootstrap repair manifest live binding failed")
    print(
        json.dumps(
            {
                "manifest_path": str(manifest_path),
                "manifest_payload_sha256": manifest["manifest_payload_sha256"],
                "profile_path": str(profile_path),
                "schema_version": "synthetic_confirmatory_v3_bootstrap_repair_freeze_v1",
            },
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
