from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from phase_a_harness import synthetic_confirmatory_v3_prerun as prerun
from phase_a_harness import synthetic_confirmatory_v3_runner as runner


def _fake_plan(tmp_path: Path) -> tuple[Path, Path]:
    scenes = [f"SCENE_{index}" for index in range(7)]
    geometries = list(range(100, 105))
    measurements = list(range(200, 203))
    snapshots: list[dict[str, object]] = []
    for scene in scenes:
        for geometry in geometries:
            snapshots.extend(
                [
                    {
                        "planned_snapshot_id": f"fake::{scene}::{geometry}::ideal",
                        "scene_variant": scene,
                        "condition": "IDEAL_MATCHED",
                        "geometry_seed": geometry,
                        "measurement_seed": "",
                        "repeat_index": 0,
                        "planned_backend_count": 2,
                        "replicate_semantics": "ONE_CONTROL_INPUT",
                    },
                    {
                        "planned_snapshot_id": (
                            f"fake::{scene}::{geometry}::independent"
                        ),
                        "scene_variant": scene,
                        "condition": "INDEPENDENT_NOISE_FREE",
                        "geometry_seed": geometry,
                        "measurement_seed": "",
                        "repeat_index": 0,
                        "planned_backend_count": 2,
                        "replicate_semantics": (
                            "ONE_DETERMINISTIC_INDEPENDENT_INPUT"
                        ),
                    },
                ]
            )
            for measurement in measurements:
                for repeat in range(5):
                    snapshots.append(
                        {
                            "planned_snapshot_id": (
                                f"fake::{scene}::{geometry}::{measurement}::{repeat}"
                            ),
                            "scene_variant": scene,
                            "condition": "FULL_NOISE",
                            "geometry_seed": geometry,
                            "measurement_seed": measurement,
                            "repeat_index": repeat,
                            "planned_backend_count": 2,
                            "replicate_semantics": (
                                "FIFTEEN_STOCHASTIC_INPUTS_PER_SCENE_GEOMETRY"
                            ),
                        }
                    )
    trials = []
    for snapshot in snapshots:
        for backend in ("open3d_point_to_plane", "pcl_point_to_plane"):
            trials.append(
                {
                    "planned_trial_id": (
                        f"{snapshot['planned_snapshot_id']}::{backend}"
                    ),
                    "planned_snapshot_id": snapshot["planned_snapshot_id"],
                    "scene_variant": snapshot["scene_variant"],
                    "condition": snapshot["condition"],
                    "geometry_seed": snapshot["geometry_seed"],
                    "measurement_seed": snapshot["measurement_seed"],
                    "repeat_index": snapshot["repeat_index"],
                    "backend": backend,
                }
            )

    import csv

    snapshot_path = tmp_path / "snapshots.csv"
    trial_path = tmp_path / "trials.csv"
    with snapshot_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=prerun.SNAPSHOT_FIELDS)
        writer.writeheader()
        writer.writerows(snapshots)
    with trial_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=prerun.TRIAL_FIELDS)
        writer.writeheader()
        writer.writerows(trials)
    return snapshot_path, trial_path


def test_v3_plan_exact_counts_pairing_and_independent_semantics(tmp_path: Path) -> None:
    snapshots, trials = _fake_plan(tmp_path)
    report = prerun.audit_v3_plan(snapshots, trials)
    assert report["V3_PLAN_AUDIT_PASS"] is True
    assert report["planned_snapshot_count"] == 595
    assert report["planned_trial_count"] == 1190
    assert report["condition_snapshot_counts"] == {
        "FULL_NOISE": 525,
        "IDEAL_MATCHED": 35,
        "INDEPENDENT_NOISE_FREE": 35,
    }
    assert report["pairing_violation_count"] == 0
    assert report["independent_pseudoreplication_plan_count"] == 0
    assert report["native_trial_count"] == 0


def test_v3_rejects_retired_manifest_identities() -> None:
    repository = Path(__file__).resolve().parents[1]
    for relative in (
        "frozen_assets/synthetic_confirmatory_formal_manifest_v1.json",
        "frozen_assets/synthetic_confirmatory_formal_manifest_v2.json",
    ):
        with pytest.raises((ValueError, FileNotFoundError)):
            prerun.load_v3_contract_compat(
                repository / relative, repository=repository
            )


def test_retired_runners_reject_v3_manifest_path(tmp_path: Path) -> None:
    manifest = tmp_path / "frozen_assets" / "synthetic_confirmatory_formal_manifest_v3.json"
    manifest.parent.mkdir()
    manifest.write_text('{"schema_version":"synthetic_confirmatory_formal_manifest_v3"}\n')
    from phase_a_harness.synthetic_confirmatory_runner import (
        load_synthetic_confirmatory_stack as load_v1,
    )
    from phase_a_harness.synthetic_confirmatory_v2_runner import (
        load_synthetic_confirmatory_stack as load_v2,
    )

    with pytest.raises(ValueError):
        load_v1(manifest, require_authorized=False)
    with pytest.raises(ValueError):
        load_v2(manifest, require_authorized=False)


def test_exact_external_path_rejects_symlink_and_repository_overlap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    good = tmp_path / "runtime" / "formal"
    monkeypatch.setattr(prerun, "FORMAL_RUNTIME_ROOT", good)
    report = prerun.qualify_v3_formal_runtime_path(
        good, repository=repository, require_absent=True
    )
    assert report["FORMAL_RUNTIME_PATH_CONTRACT_PASS"] is True

    target = tmp_path / "real"
    target.mkdir()
    link = tmp_path / "formal-link"
    link.symlink_to(target, target_is_directory=True)
    monkeypatch.setattr(prerun, "FORMAL_RUNTIME_ROOT", link)
    with pytest.raises(prerun.V3ContractError):
        prerun.qualify_v3_formal_runtime_path(
            link, repository=repository, require_absent=False
        )

    overlap = repository / "formal"
    monkeypatch.setattr(prerun, "FORMAL_RUNTIME_ROOT", overlap)
    with pytest.raises(prerun.V3ContractError):
        prerun.qualify_v3_formal_runtime_path(
            overlap, repository=repository, require_absent=True
        )


def test_zero_instantiation_dry_run_canonical_aliases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    formal = tmp_path / "never-created"
    monkeypatch.setattr(prerun, "FORMAL_RUNTIME_ROOT", formal)
    plan = {
        "V3_PLAN_AUDIT_PASS": True,
        "backend_trial_counts": {
            "open3d_point_to_plane": 595,
            "pcl_point_to_plane": 595,
        },
        "condition_snapshot_counts": {
            "FULL_NOISE": 525,
            "IDEAL_MATCHED": 35,
            "INDEPENDENT_NOISE_FREE": 35,
        },
        "duplicate_snapshot_count": 0,
        "duplicate_trial_count": 0,
        "independent_pseudoreplication_plan_count": 0,
        "native_trial_count": 0,
        "pairing_violation_count": 0,
        "planned_snapshot_count": 595,
        "planned_snapshot_unique_count": 595,
        "planned_trial_count": 1190,
        "planned_trial_unique_count": 1190,
    }
    monkeypatch.setattr(
        prerun,
        "validate_v3_frozen_contract",
        lambda **_kwargs: {
            "FORMAL_GIT_GATE_PASS": True,
            "V3_FROZEN_CONTRACT_PASS": True,
            "contract_loader": "fake",
            "git_gate": {"RUNTIME_GIT_GATE_PASS": True},
            "lifecycle_core_binding": {"RUNTIME_LIFECYCLE_CORE_BINDING_PASS": True},
            "manifest_path": str(tmp_path / "manifest.json"),
            "manifest_sha256": "a" * 64,
            "plan_audit": plan,
            "runtime_path_contract": {"FORMAL_RUNTIME_PATH_CONTRACT_PASS": True},
        },
    )
    report = prerun.dry_run_synthetic_confirmatory_v3(
        manifest_path=tmp_path / "manifest.json",
        run_id="synthetic-confirmatory-v3",
        runtime_root=formal,
        workers=2,
        repository=tmp_path,
    )
    assert not formal.exists()
    assert report["V3_DRY_RUN_PASS"] is True
    assert report["V3_FORMAL_RUNTIME_ROOT_NOT_CREATED"] is True
    assert report["backend_trial_counts"] == {
        "Native": 0,
        "Open3D": 595,
        "PCL": 595,
    }
    for name in (
        "V3_RNG_INSTANTIATION_COUNT",
        "V3_SNAPSHOT_CONSTRUCTION_COUNT",
        "V3_BACKEND_EXECUTION_COUNT",
        "V3_TRIAL_RESULT_COUNT",
        "V3_STARTED_EVENT_COUNT",
    ):
        assert report[name] == 0


def test_release_tag_branch_and_clean_git_gate(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    subprocess.run(["git", "init"], cwd=repository, check=True)
    subprocess.run(
        ["git", "checkout", "-b", "v3-test"], cwd=repository, check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "v3@example.invalid"],
        cwd=repository,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "v3 test"], cwd=repository, check=True
    )
    tracked = repository / "tracked.txt"
    tracked.write_text("frozen\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-m", "freeze"], cwd=repository, check=True)
    subprocess.run(["git", "tag", "v3-release"], cwd=repository, check=True)
    identity = prerun.manifest_git_identity(
        {"expected_branch": "v3-test", "expected_release_tag": "v3-release"},
        repository=repository,
        require_release_tag=True,
    )
    from phase_a_harness.runtime_git_gate import (
        RuntimeGitGateError,
        verify_runtime_git_gate,
    )

    assert verify_runtime_git_gate(
        repository,
        expected_commit=identity["commit"],
        expected_branch=identity["branch"],
        expected_tag=identity["tag"],
        checkpoint="TEST",
    )["RUNTIME_GIT_GATE_PASS"] is True
    (repository / "untracked.txt").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(RuntimeGitGateError):
        verify_runtime_git_gate(
            repository,
            expected_commit=identity["commit"],
            expected_branch=identity["branch"],
            expected_tag=identity["tag"],
            checkpoint="TEST_DIRTY",
        )


def test_snapshot_builder_import_does_not_import_rng_or_create_formal_root(
    tmp_path: Path,
) -> None:
    repository = Path(__file__).resolve().parents[1]
    code = "\n".join(
        [
            "import json, sys",
            f"sys.path.insert(0, {str(repository / 'src')!r})",
            "before=set(sys.modules)",
            "import phase_a_harness.synthetic_confirmatory_v3_snapshot_builder",
            "after=set(sys.modules)",
            "bad=sorted(name for name in after-before if name == 'numpy.random' or name.startswith('numpy.random.'))",
            "print(json.dumps({'bad':bad}))",
        ]
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=tmp_path,
    )
    assert json.loads(completed.stdout) == {"bad": []}


def test_fake_external_fresh_then_resume_does_not_reexecute_valid_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    formal = tmp_path / "external-formal"
    monkeypatch.setattr(runner, "FORMAL_RUNTIME_ROOT", formal)
    monkeypatch.setattr(runner, "EXPECTED_SNAPSHOT_COUNT", 3)
    monkeypatch.setattr(runner, "EXPECTED_TRIAL_COUNT", 6)
    snapshots = [
        {
            "planned_snapshot_id": f"snapshot-{index}",
            "scene_variant": "FAKE",
            "condition": "IDEAL_MATCHED",
            "geometry_seed": index,
            "measurement_seed": None,
            "repeat_index": 0,
            "planned_backend_count": 2,
            "replicate_semantics": "ONE_CONTROL_INPUT",
        }
        for index in range(3)
    ]
    trials = [
        {
            "planned_trial_id": f"{snapshot['planned_snapshot_id']}::{backend}",
            "planned_snapshot_id": snapshot["planned_snapshot_id"],
            "scene_variant": "FAKE",
            "condition": "IDEAL_MATCHED",
            "geometry_seed": snapshot["geometry_seed"],
            "measurement_seed": None,
            "repeat_index": 0,
            "backend": backend,
        }
        for snapshot in snapshots
        for backend in ("open3d_point_to_plane", "pcl_point_to_plane")
    ]
    paths = {
        "analysis": formal / "analysis",
        "artifact_staging": formal / "artifact_staging",
        "backend_temporary": formal / "backend_tmp",
        "event_log": formal / "event_logs",
        "publisher_staging": formal / "publisher_staging",
        "raw_results": formal / "raw_results",
        "snapshot_cache": formal / "snapshot_cache",
        "snapshot_lock": formal / "snapshot_lock.json",
        "temporary_inventory": formal / "working_inventory",
        "verification": formal / "verification",
        "raw_manifest": formal / "raw_result_manifest.json",
        "formal_command_log": formal / "formal_command.log",
        "formal_command_sha256": formal / "formal_command.log.sha256",
        "run_lock": formal / "immutable_run_lock.json",
        "run_manifest": formal / "run_manifest.json",
    }
    manifest = {
        "bound_files": {
            "backend_parameter_contract": {"sha256": "1" * 64},
            "pcl_cli": {"sha256": "2" * 64},
            "execution_profile": {"sha256": "c" * 64},
            "fixture_runner": {"sha256": "d" * 64},
        },
        "expected_branch": "fake",
        "expected_release_tag": "fake-tag",
        "formal_bootstrap_contract": {
            "implementation_revision": "fixture-bootstrap-repair-r1",
            "state_machine_schema": "fixture_formal_runtime_state_machine_v1",
        },
        "gate_contract_sha256": "e" * 64,
        "manifest_payload_sha256": "3" * 64,
        "protocol_sha256": "4" * 64,
        "run_id": "synthetic-confirmatory-v3",
        "seed_schedule_sha256": "5" * 64,
        "workers": 2,
    }
    stack = {
        "manifest": manifest,
        "manifest_path": tmp_path / "manifest.json",
        "parameters": {},
        "pcl_cli": tmp_path / "pcl",
        "repository": tmp_path,
        "runtime_paths": paths,
        "snapshots": snapshots,
        "trials": trials,
        "validated_contract": {
            "git_identity": {"commit": "6" * 40},
            "plan_audit": {
                "planned_snapshot_identity_sha256": "7" * 64,
                "planned_trial_identity_sha256": "8" * 64,
            },
            "planned_snapshots_sha256": "9" * 64,
            "planned_trials_sha256": "a" * 64,
        },
        "manifest_sha256": "b" * 64,
    }
    monkeypatch.setattr(runner, "load_v3_execution_stack", lambda **_kwargs: stack)
    monkeypatch.setattr(runner, "_git_gate", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(runner, "_recover_orphans", lambda *_args, **_kwargs: [])

    calls: list[str] = []

    def execute(_stack: object, row: dict[str, object]):
        calls.append(str(row["planned_trial_id"]))
        payload = {
            "backend": row["backend"],
            "condition": "IDEAL_MATCHED",
            "finite_output": True,
            "planned_trial_id": row["planned_trial_id"],
            "reference_pose_checksum": "r",
            "snapshot_checksum": "s",
            "snapshot_id": row["planned_snapshot_id"],
            "solver_failure": False,
            "source_checksum": "x",
            "target_checksum": "y",
        }
        return {"backend": row["backend"]}, payload

    monkeypatch.setattr(runner, "_execute_one", execute)

    def audit(_stack, raw, expected, *, allow_orphans):
        payloads = []
        for trial_id in sorted(raw["results"]):
            row = expected[trial_id]
            payloads.append(
                {
                    "backend": row["backend"],
                    "condition": "IDEAL_MATCHED",
                    "finite_output": True,
                    "snapshot_id": row["planned_snapshot_id"],
                    "solver_failure": False,
                    "source_checksum": "x",
                    "target_checksum": "y",
                    "reference_pose_checksum": "r",
                    "snapshot_checksum": "s",
                }
            )
        return {
            "checksum_mismatch_count": 0,
            "corrupt_trial_count": 0,
            "duplicate_trial_count": 0,
            "extra_trial_count": 0,
            "missing_trial_count": len(expected) - len(payloads),
            "orphan_result_files": [],
            "payloads": payloads,
            "reverse_inventory_mismatch_count": 0,
        }

    monkeypatch.setattr(runner, "_audit_raw_inventory", audit)

    import phase_a_harness.asset_verifier as asset_verifier
    import phase_a_harness.full_synthetic_development_protocol as protocol
    import phase_a_harness.full_synthetic_snapshot_builder as full_builder
    import phase_a_harness.synthetic_confirmatory_v3_snapshot_builder as builder
    from phase_a_harness.runtime_lifecycle_io import (
        atomic_create_canonical_json,
        atomic_replace_canonical_json,
        read_canonical_json,
    )

    monkeypatch.setattr(protocol, "assert_isolated_python_runtime", lambda: None)
    monkeypatch.setattr(asset_verifier, "source_runtime_import_paths", lambda: [])
    monkeypatch.setattr(
        full_builder,
        "FullSyntheticSourceAccessMonitor",
        lambda: SimpleNamespace(count=0, install=lambda: None),
    )

    lock_value = {
        "schema_version": "fake",
        "snapshots": [
            {"snapshot_id": row["planned_snapshot_id"]} for row in snapshots
        ],
    }

    def prepare(_repository, _cache, _snapshots, *, lock_path, resume):
        if Path(lock_path).exists():
            lock = read_canonical_json(lock_path)
        else:
            atomic_create_canonical_json(lock_path, lock_value)
            lock = lock_value
        return {
            "lock": lock,
            "confirmatory_rng_instantiation_count_this_invocation": 0,
            "generated_snapshot_count": 0 if resume else 3,
            "resumed_snapshot_count": 3 if resume else 0,
        }

    monkeypatch.setattr(builder, "prepare_v3_snapshots", prepare)
    from phase_a_harness.formal_runtime_state_machine import (
        FormalRuntimeState,
        bootstrap_formal_runtime,
        build_formal_runner_command,
        classify_formal_runtime,
    )

    manifest_path = tmp_path / "manifest.json"
    frozen_fresh_command = build_formal_runner_command(
        repository=tmp_path,
        manifest_path=manifest_path,
        run_id="synthetic-confirmatory-v3",
        runtime_root=formal,
        workers=2,
        mode="fresh",
    )
    bootstrap = bootstrap_formal_runtime(
        formal, frozen_fresh_command, mode="fresh"
    )
    assert bootstrap["state_after"] is FormalRuntimeState.BOOTSTRAP_ONLY
    assert classify_formal_runtime(formal) is FormalRuntimeState.BOOTSTRAP_ONLY

    first = runner.execute_synthetic_confirmatory_v3(
        repository=tmp_path,
        manifest_path=manifest_path,
        run_id="synthetic-confirmatory-v3",
        runtime_root=formal,
        workers=2,
        resume=False,
        mode="fresh",
        expected_formal_command=frozen_fresh_command,
        invocation_id="fresh-from-bootstrap-only",
    )
    assert first["completed_trial_count"] == 6
    assert first["backend_execution_count_this_invocation"] == 6
    assert len(calls) == 6
    assert classify_formal_runtime(formal) is FormalRuntimeState.RESUMABLE

    resume_bootstrap = bootstrap_formal_runtime(
        formal, frozen_fresh_command, mode="resume"
    )
    assert resume_bootstrap["state_before"] is FormalRuntimeState.RESUMABLE
    assert resume_bootstrap["created"] is False
    expected_resume_invocation = build_formal_runner_command(
        repository=tmp_path,
        manifest_path=manifest_path,
        run_id="synthetic-confirmatory-v3",
        runtime_root=formal,
        workers=2,
        mode="resume",
    )
    second = runner.execute_synthetic_confirmatory_v3(
        repository=tmp_path,
        manifest_path=manifest_path,
        run_id="synthetic-confirmatory-v3",
        runtime_root=formal,
        workers=2,
        resume=True,
        mode="resume",
        expected_formal_command=expected_resume_invocation,
        invocation_id="resume-identical",
    )
    assert second["backend_execution_count_this_invocation"] == 0
    assert second["resume_skipped_valid_result_count"] == 6
    assert len(calls) == 6


def test_v3_thin_clis_do_not_call_retired_high_level_orchestrators() -> None:
    repository = Path(__file__).resolve().parents[1]
    paths = [
        repository / "src/phase_a_harness/synthetic_confirmatory_v3_runner.py",
        repository / "scripts/analyze_synthetic_confirmatory_v3.py",
        repository / "scripts/verify_synthetic_confirmatory_v3.py",
        repository / "scripts/publish_synthetic_confirmatory_v3.py",
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    for forbidden in (
        "synthetic_confirmatory_v2_runner",
        "synthetic_confirmatory_v2_snapshot_builder",
        "analyze_synthetic_confirmatory(",
        "independently_verify_synthetic_confirmatory(",
        "publish_synthetic_confirmatory(",
    ):
        assert forbidden not in source


def _generic_final_decision() -> dict[str, bool]:
    return {
        "CONFIRMATORY_EVIDENCE_INTEGRITY_PASS": True,
        "H1_IDEAL_CONTROL_PASS": True,
        "H2_LONG_CORRIDOR_SCENE_EFFECT_PASS": True,
        "H3_CROSS_BACKEND_SCENE_RANKING_PASS": True,
        "H4_REASSOCIATION_MECHANISM_PASS": True,
        "H5_FROZEN_MODEL_B_INCREMENTAL_VALUE_PASS": True,
        "H6_FULL_NOISE_SYSTEMATIC_OFFSET_PASS": True,
        "SYNTHETIC_CONFIRMATORY_EXECUTED": True,
        "SYNTHETIC_CONFIRMATORY_COMPLETE": True,
        "SYNTHETIC_CONFIRMATORY_PASS": True,
        "CONFIRMATORY_RUN_AUTHORIZED": False,
        "REAL_DATA_RUN_AUTHORIZED": False,
        "MEASUREMENT_PAPER_MAINLINE_AUTHORIZED": False,
    }


def test_v3_final_decision_adapter_versions_nested_and_projection() -> None:
    generic = _generic_final_decision()
    primary = runner._adapt_v3_analysis(
        {"final_decision": generic}, independent=False
    )
    independent = runner._adapt_v3_analysis(
        {
            "final_decision": generic,
            "verification_projection": {"final_decision": generic},
        },
        independent=True,
    )
    decision = primary["final_decision"]
    assert decision == independent["final_decision"]
    assert decision == independent["verification_projection"]["final_decision"]
    assert decision["schema_version"] == runner.V3_FINAL_DECISION_SCHEMA
    assert decision["SYNTHETIC_CONFIRMATORY_V3_EXECUTED"] is True
    assert decision["SYNTHETIC_CONFIRMATORY_V3_COMPLETE"] is True
    assert decision["SYNTHETIC_CONFIRMATORY_V3_PASS"] is True
    assert decision["CONFIRMATORY_V3_RUN_AUTHORIZED"] is False
    assert "SYNTHETIC_CONFIRMATORY_EXECUTED" not in decision
    assert "CONFIRMATORY_RUN_AUTHORIZED" not in decision

    assert runner._genericize_v3_analysis(
        primary, independent=False
    )["final_decision"] == generic
    generic_independent = runner._genericize_v3_analysis(
        independent, independent=True
    )
    assert generic_independent["final_decision"] == generic
    assert (
        generic_independent["verification_projection"]["final_decision"]
        == generic
    )


def test_v3_final_decision_adapter_rejects_schema_drift() -> None:
    generic = _generic_final_decision()
    with pytest.raises(runner.V3ContractError):
        runner._validate_v3_final_decision(generic)
    with pytest.raises(runner.V3ContractError):
        runner._adapt_v3_final_decision({**generic, "unexpected": False})
    v3 = runner._adapt_v3_final_decision(generic)
    with pytest.raises(runner.V3ContractError):
        runner._validate_v3_final_decision({**v3, "schema_version": "v2"})


def test_v3_artifact_verifier_binds_persisted_report_and_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import phase_a_harness.synthetic_confirmatory_artifact_verifier as generic

    generic_report = {"ARTIFACT_VERIFICATION_PASS": True, "live": "exact"}
    monkeypatch.setattr(
        generic,
        "verify_synthetic_confirmatory_artifact",
        lambda _path, *, write_report=False: dict(generic_report),
    )
    decision = runner._adapt_v3_final_decision(_generic_final_decision())
    primary = {
        "schema_version": runner.PRIMARY_ANALYSIS_SCHEMA,
        "final_decision": decision,
    }
    independent = {
        "schema_version": runner.INDEPENDENT_SCHEMA,
        "final_decision": decision,
        "verification_projection": {"final_decision": decision},
    }
    run = {
        "schema_version": runner.FORMAL_RUN_SCHEMA,
        "run_id": "synthetic-confirmatory-v3",
    }
    root_files = {
        "primary_analysis.json": primary,
        "independent_verification.json": independent,
        "final_decision.json": decision,
        "run_manifest.json": run,
        "artifact_verification.json": generic_report,
    }
    for name, value in root_files.items():
        (tmp_path / name).write_text(
            json.dumps(value, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    (tmp_path / "synthetic_confirmatory_report.md").write_text(
        "# Synthetic Confirmatory v3\n\n"
        "SYNTHETIC_CONFIRMATORY_V3_EXECUTED\n"
        "SYNTHETIC_CONFIRMATORY_V3_COMPLETE\n"
        "SYNTHETIC_CONFIRMATORY_V3_PASS\n",
        encoding="utf-8",
    )
    (tmp_path / "SHA256SUMS").write_text("placeholder\n", encoding="utf-8")
    for directory, names in (
        ("tables", generic.FORMAL_TABLES),
        ("figures", generic.FORMAL_FIGURES),
    ):
        (tmp_path / directory).mkdir()
        for name in names:
            (tmp_path / directory / name).write_bytes(b"fixture")

    report = runner.verify_v3_formal_artifact(tmp_path)
    assert report["V3_FORMAL_ARTIFACT_VERIFICATION_PASS"] is True
    assert report["v3_final_decision_identity_pass"] is True
    assert report["v3_report_identity_pass"] is True
    assert report["persisted_artifact_verification_match_pass"] is True

    (tmp_path / "artifact_verification.json").write_text(
        json.dumps({"ARTIFACT_VERIFICATION_PASS": True, "live": "tampered"})
        + "\n",
        encoding="utf-8",
    )
    tampered = runner.verify_v3_formal_artifact(tmp_path)
    assert tampered["persisted_artifact_verification_match_pass"] is False
    assert tampered["V3_FORMAL_ARTIFACT_VERIFICATION_PASS"] is False
