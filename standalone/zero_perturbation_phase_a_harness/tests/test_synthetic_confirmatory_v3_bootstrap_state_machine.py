from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import pytest

from phase_a_harness.formal_runtime_state_machine import (
    FORMAL_COMMAND_LOG_NAME,
    FORMAL_COMMAND_SHA256_NAME,
    FORMAL_COMMAND_SHA256_SCHEMA,
    IMMUTABLE_RUN_LOCK_NAME,
    SINGLE_WRITER_LEASE_NAME,
    FormalBootstrapError,
    FormalCommandBindingError,
    FormalRuntimeState,
    InvalidFormalRuntimeError,
    assert_seed_entry_lock,
    bootstrap_formal_runtime,
    build_formal_runner_command,
    canonical_formal_command,
    classify_formal_runtime,
    formal_command_sha256,
    inspect_formal_runtime,
    transition_bootstrap_run_lock,
    verify_formal_command_binding,
)
from phase_a_harness.runtime_lifecycle_io import (
    atomic_replace_canonical_json,
    build_immutable_run_lock,
    canonical_json_bytes,
    read_canonical_json,
)


FIXTURE_COMMAND = (
    "env -u PYTHONPATH PYTHONNOUSERSITE=1 python "
    "fixture_formal_runner.py --manifest fixture_manifest.json "
    "--run-id bootstrap-fixture --workers 2 --mode fresh"
)
ALTERNATE_COMMAND = FIXTURE_COMMAND.removesuffix("fresh") + "resume"


def _contract(root: Path, **updates: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "schema_version": "bootstrap_state_machine_fixture_contract_v1",
        "run_id": "bootstrap-fixture",
        "manifest_path": "fixture_manifest.json",
        "manifest_sha256": "1" * 64,
        "manifest_payload_sha256": "2" * 64,
        "protocol_sha256": "3" * 64,
        "gate_contract_sha256": "4" * 64,
        "seed_schedule_sha256": "5" * 64,
        "formal_execution_profile_sha256": "6" * 64,
        "expected_commit": "7" * 40,
        "expected_branch": "fixture-bootstrap-branch",
        "expected_tag": "fixture-bootstrap-tag",
        "implementation_binding": {"fixture_runtime.py": "8" * 64},
        "workers": 2,
        "runtime_root": str(root),
        "runtime_paths": {
            "snapshot_cache": str(root / "snapshot_cache"),
            "snapshot_lock": str(root / "snapshot_lock.json"),
            "raw_results": str(root / "raw_results"),
            "event_logs": str(root / "event_logs"),
        },
        "creation_identity": "seed-free-fixture",
    }
    value.update(updates)
    return value


def _bootstrap(root: Path, command: str = FIXTURE_COMMAND) -> dict[str, Any]:
    return bootstrap_formal_runtime(root, command, mode="fresh")


def _make_resumable(
    root: Path,
    *,
    command: str = FIXTURE_COMMAND,
    contract: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    _bootstrap(root, command)
    bound = _contract(root) if contract is None else contract
    report = transition_bootstrap_run_lock(root, bound, mode="fresh")
    return bound, report


def _write_command_pair(root: Path, command: str) -> None:
    payload = canonical_formal_command(command)
    (root / FORMAL_COMMAND_LOG_NAME).write_bytes(payload)
    atomic_replace_canonical_json(
        root / FORMAL_COMMAND_SHA256_NAME,
        {
            "command_log_path": FORMAL_COMMAND_LOG_NAME,
            "command_log_sha256": hashlib.sha256(payload).hexdigest(),
            "command_log_size_bytes": len(payload),
            "schema_version": FORMAL_COMMAND_SHA256_SCHEMA,
        },
    )


def test_four_formal_runtime_states_are_mutually_classified(tmp_path: Path) -> None:
    root = tmp_path / "qualification-runtime"
    assert classify_formal_runtime(root) is FormalRuntimeState.ABSENT

    bootstrap = _bootstrap(root)
    assert bootstrap["state_before"] is FormalRuntimeState.ABSENT
    assert bootstrap["state_after"] is FormalRuntimeState.BOOTSTRAP_ONLY
    assert classify_formal_runtime(root) is FormalRuntimeState.BOOTSTRAP_ONLY

    transition = transition_bootstrap_run_lock(
        root, _contract(root), mode="fresh"
    )
    assert transition["state_before"] is FormalRuntimeState.BOOTSTRAP_ONLY
    assert transition["state_after"] is FormalRuntimeState.RESUMABLE
    assert transition["is_resume"] is False
    assert classify_formal_runtime(root) is FormalRuntimeState.RESUMABLE

    (root / "unknown-object").write_bytes(b"forbidden")
    inspection = inspect_formal_runtime(root)
    assert inspection["state"] is FormalRuntimeState.INVALID
    assert inspection["reasons"]


def test_root_existence_is_not_resume_and_bootstrap_fresh_is_idempotent(
    tmp_path: Path,
) -> None:
    root = tmp_path / "qualification-runtime"
    first = _bootstrap(root)
    before = {
        name: (root / name).read_bytes()
        for name in (FORMAL_COMMAND_LOG_NAME, FORMAL_COMMAND_SHA256_NAME)
    }
    second = _bootstrap(root)
    after = {
        name: (root / name).read_bytes()
        for name in (FORMAL_COMMAND_LOG_NAME, FORMAL_COMMAND_SHA256_NAME)
    }
    assert first["created"] is True
    assert second["created"] is False
    assert second["state_before"] is FormalRuntimeState.BOOTSTRAP_ONLY
    assert before == after

    transition = transition_bootstrap_run_lock(
        root, _contract(root), mode="fresh"
    )
    assert transition["is_resume"] is False
    assert transition["state_after"] is FormalRuntimeState.RESUMABLE


def test_command_canonicalization_builder_and_sha_are_deterministic(
    tmp_path: Path,
) -> None:
    argv = ["python", "fixture runner.py", "--mode", "fresh"]
    expected = b"python 'fixture runner.py' --mode fresh\n"
    assert canonical_formal_command(argv) == expected
    assert canonical_formal_command(expected.decode().removesuffix("\n")) == expected
    assert formal_command_sha256(argv) == hashlib.sha256(expected).hexdigest()
    for invalid in ("", " leading", "trailing ", "two\nlines", "carriage\rreturn"):
        with pytest.raises(ValueError):
            canonical_formal_command(invalid)

    repository = tmp_path / "fixture-harness"
    manifest = repository / "frozen_assets/fixture_manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}\n", encoding="utf-8")
    runtime = tmp_path / "qualification-runtime"
    command = build_formal_runner_command(
        repository=repository,
        manifest_path=manifest,
        run_id="bootstrap-fixture",
        runtime_root=runtime,
        workers=2,
        mode="fresh",
    )
    assert command == build_formal_runner_command(
        repository=repository,
        manifest_path=manifest,
        run_id="bootstrap-fixture",
        runtime_root=runtime,
        workers=2,
        mode="fresh",
    )
    assert "--manifest frozen_assets/fixture_manifest.json" in command
    assert f"--runtime-root {runtime}" in command
    assert "--run-id bootstrap-fixture" in command
    assert "--workers 2 --mode fresh" in command
    assert "\n" not in command
    assert formal_command_sha256(command) == hashlib.sha256(
        canonical_formal_command(command)
    ).hexdigest()


def test_command_log_and_sidecar_bind_exact_bytes(tmp_path: Path) -> None:
    root = tmp_path / "qualification-runtime"
    report = _bootstrap(root)
    payload = canonical_formal_command(FIXTURE_COMMAND)
    assert (root / FORMAL_COMMAND_LOG_NAME).read_bytes() == payload
    assert report["command_binding"] == {
        "command_log_path": FORMAL_COMMAND_LOG_NAME,
        "command_log_sha256": hashlib.sha256(payload).hexdigest(),
        "command_log_size_bytes": len(payload),
        "schema_version": FORMAL_COMMAND_SHA256_SCHEMA,
    }
    assert verify_formal_command_binding(root, FIXTURE_COMMAND) == report[
        "command_binding"
    ]


def test_valid_lock_allows_explicit_resume_and_seed_entry_gate_is_metadata_only(
    tmp_path: Path,
) -> None:
    root = tmp_path / "qualification-runtime"
    contract, fresh = _make_resumable(root)
    resumed = transition_bootstrap_run_lock(root, contract, mode="resume")
    seed_gate = assert_seed_entry_lock(root, contract)
    assert fresh["is_resume"] is False
    assert resumed["is_resume"] is True
    assert resumed["state_before"] is FormalRuntimeState.RESUMABLE
    assert resumed["state_after"] is FormalRuntimeState.RESUMABLE
    assert resumed["lock"] == fresh["lock"]
    assert seed_gate["seed_entry_lock_gate_pass"] is True
    assert seed_gate["state"] is FormalRuntimeState.RESUMABLE


def test_lock_payload_tamper_is_invalid_and_never_reaches_seed_gate(
    tmp_path: Path,
) -> None:
    root = tmp_path / "qualification-runtime"
    contract, _report = _make_resumable(root)
    lock_path = root / IMMUTABLE_RUN_LOCK_NAME
    lock = read_canonical_json(lock_path)
    lock["contract"]["workers"] = 99
    atomic_replace_canonical_json(lock_path, lock)
    assert classify_formal_runtime(root) is FormalRuntimeState.INVALID
    with pytest.raises(InvalidFormalRuntimeError):
        assert_seed_entry_lock(root, contract)


def test_recursive_symlink_is_invalid_even_below_allowed_directory(
    tmp_path: Path,
) -> None:
    root = tmp_path / "qualification-runtime"
    _make_resumable(root)
    analysis = root / "analysis"
    analysis.mkdir()
    target = tmp_path / "outside"
    target.write_bytes(b"outside")
    (analysis / "escape").symlink_to(target)
    inspection = inspect_formal_runtime(root)
    assert inspection["state"] is FormalRuntimeState.INVALID
    assert any("symbolic link" in reason for reason in inspection["reasons"])


def test_interrupted_atomic_temporary_lock_is_rejected_without_cleanup(
    tmp_path: Path,
) -> None:
    root = tmp_path / "qualification-runtime"
    _bootstrap(root)
    partial = root / ".immutable_run_lock.json.tmp-interrupted"
    partial.write_bytes(b'{"partial":')
    assert not (root / IMMUTABLE_RUN_LOCK_NAME).exists()
    assert classify_formal_runtime(root) is FormalRuntimeState.INVALID
    with pytest.raises(InvalidFormalRuntimeError):
        transition_bootstrap_run_lock(root, _contract(root), mode="fresh")
    assert partial.read_bytes() == b'{"partial":'
    assert not (root / IMMUTABLE_RUN_LOCK_NAME).exists()


def test_before_lock_rename_failure_leaves_official_lock_absent_and_bootstrap_only(
    tmp_path: Path,
) -> None:
    root = tmp_path / "qualification-runtime"
    _bootstrap(root)
    observed: dict[str, Any] = {}

    class InjectedPreRenameInterruption(RuntimeError):
        pass

    def interrupt(temporary: Path, destination: Path) -> None:
        observed["temporary"] = temporary
        observed["destination"] = destination
        observed["payload"] = temporary.read_bytes()
        assert temporary.parent == root
        assert destination == root / IMMUTABLE_RUN_LOCK_NAME
        assert not destination.exists()
        raise InjectedPreRenameInterruption("qualification-only interruption")

    with pytest.raises(
        InjectedPreRenameInterruption, match="qualification-only interruption"
    ):
        transition_bootstrap_run_lock(
            root,
            _contract(root),
            mode="fresh",
            before_lock_rename=interrupt,
        )

    assert observed["payload"]
    assert not (root / IMMUTABLE_RUN_LOCK_NAME).exists()
    assert not observed["temporary"].exists()
    assert classify_formal_runtime(root) is FormalRuntimeState.BOOTSTRAP_ONLY
    assert set(path.name for path in root.iterdir()) == {
        FORMAL_COMMAND_LOG_NAME,
        FORMAL_COMMAND_SHA256_NAME,
    }


def test_bootstrap_only_root_rejects_internal_single_writer_lease(
    tmp_path: Path,
) -> None:
    root = tmp_path / "qualification-runtime"
    _bootstrap(root)
    (root / SINGLE_WRITER_LEASE_NAME).touch()
    inspection = inspect_formal_runtime(root)
    assert inspection["state"] is FormalRuntimeState.INVALID
    assert any(
        SINGLE_WRITER_LEASE_NAME in reason for reason in inspection["reasons"]
    )


def test_resumable_root_rejects_unbound_internal_single_writer_lease(
    tmp_path: Path,
) -> None:
    root = tmp_path / "qualification-runtime"
    _make_resumable(root)
    (root / SINGLE_WRITER_LEASE_NAME).touch()
    inspection = inspect_formal_runtime(root)
    assert inspection["state"] is FormalRuntimeState.INVALID
    assert any(
        SINGLE_WRITER_LEASE_NAME in reason for reason in inspection["reasons"]
    )


INVALID_CASES = (
    "unknown_file_without_lock",
    "empty_snapshot_cache_without_lock",
    "command_log_missing",
    "command_sha_missing",
    "command_log_tampered",
    "command_sha_tampered",
    "command_profile_mismatch",
    "lock_json_corrupt",
    "lock_manifest_sha_mismatch",
    "lock_commit_mismatch",
    "lock_run_id_mismatch",
    "lock_workers_mismatch",
    "lock_runtime_root_mismatch",
    "lock_command_sha_mismatch",
    "lock_symlink",
    "root_symlink_component",
    "unknown_temporary_file",
    "multiple_lock_files",
    "snapshot_payload_without_lock",
    "trial_payload_without_lock",
)


def _classify_rejected(root: Path) -> None:
    inspection = inspect_formal_runtime(root)
    assert inspection["state"] is FormalRuntimeState.INVALID
    assert inspection["reasons"]


def _wrong_contract_is_rejected(
    root: Path,
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    expected = _contract(root)
    wrong = _contract(root)
    mutate(wrong)
    _make_resumable(root, contract=wrong)
    with pytest.raises(InvalidFormalRuntimeError):
        assert_seed_entry_lock(root, expected)


@pytest.mark.parametrize("case", INVALID_CASES)
def test_exact_twenty_invalid_runtime_states_fail_closed(
    tmp_path: Path, case: str
) -> None:
    assert len(INVALID_CASES) == 20
    root = tmp_path / "qualification-runtime"

    if case == "unknown_file_without_lock":
        root.mkdir()
        (root / "unknown.bin").write_bytes(b"unknown")
        _classify_rejected(root)
    elif case == "empty_snapshot_cache_without_lock":
        _bootstrap(root)
        (root / "snapshot_cache").mkdir()
        _classify_rejected(root)
    elif case == "command_log_missing":
        _bootstrap(root)
        (root / FORMAL_COMMAND_LOG_NAME).unlink()
        _classify_rejected(root)
    elif case == "command_sha_missing":
        _bootstrap(root)
        (root / FORMAL_COMMAND_SHA256_NAME).unlink()
        _classify_rejected(root)
    elif case == "command_log_tampered":
        _bootstrap(root)
        (root / FORMAL_COMMAND_LOG_NAME).write_bytes(
            canonical_formal_command(ALTERNATE_COMMAND)
        )
        _classify_rejected(root)
    elif case == "command_sha_tampered":
        _bootstrap(root)
        sidecar = read_canonical_json(root / FORMAL_COMMAND_SHA256_NAME)
        sidecar["command_log_sha256"] = "0" * 64
        atomic_replace_canonical_json(root / FORMAL_COMMAND_SHA256_NAME, sidecar)
        _classify_rejected(root)
    elif case == "command_profile_mismatch":
        _bootstrap(root)
        with pytest.raises(FormalCommandBindingError):
            verify_formal_command_binding(root, ALTERNATE_COMMAND)
    elif case == "lock_json_corrupt":
        _bootstrap(root)
        (root / IMMUTABLE_RUN_LOCK_NAME).write_bytes(b'{"broken":')
        _classify_rejected(root)
    elif case == "lock_manifest_sha_mismatch":
        _wrong_contract_is_rejected(
            root, lambda value: value.update(manifest_sha256="a" * 64)
        )
    elif case == "lock_commit_mismatch":
        _wrong_contract_is_rejected(
            root, lambda value: value.update(expected_commit="b" * 40)
        )
    elif case == "lock_run_id_mismatch":
        _wrong_contract_is_rejected(
            root, lambda value: value.update(run_id="different-fixture-run")
        )
    elif case == "lock_workers_mismatch":
        _wrong_contract_is_rejected(root, lambda value: value.update(workers=1))
    elif case == "lock_runtime_root_mismatch":
        _wrong_contract_is_rejected(
            root,
            lambda value: value.update(runtime_root=str(tmp_path / "other-runtime")),
        )
    elif case == "lock_command_sha_mismatch":
        contract, _report = _make_resumable(root)
        _write_command_pair(root, ALTERNATE_COMMAND)
        assert classify_formal_runtime(root) is FormalRuntimeState.INVALID
        with pytest.raises(InvalidFormalRuntimeError):
            assert_seed_entry_lock(root, contract)
    elif case == "lock_symlink":
        _bootstrap(root)
        target = tmp_path / "outside-lock.json"
        target.write_bytes(canonical_json_bytes(build_immutable_run_lock(_contract(root))))
        (root / IMMUTABLE_RUN_LOCK_NAME).symlink_to(target)
        _classify_rejected(root)
    elif case == "root_symlink_component":
        target = tmp_path / "real-runtime"
        _bootstrap(target)
        root.symlink_to(target, target_is_directory=True)
        _classify_rejected(root)
    elif case == "unknown_temporary_file":
        _bootstrap(root)
        (root / ".immutable_run_lock.json.tmp-orphan").write_bytes(b"partial")
        _classify_rejected(root)
    elif case == "multiple_lock_files":
        _make_resumable(root)
        (root / "immutable_run_lock.copy.json").write_bytes(b"copy")
        _classify_rejected(root)
    elif case == "snapshot_payload_without_lock":
        _bootstrap(root)
        partial = root / "snapshot_cache/partial-snapshot"
        partial.mkdir(parents=True)
        (partial / "metadata.json").write_bytes(b"{}\n")
        _classify_rejected(root)
    elif case == "trial_payload_without_lock":
        _bootstrap(root)
        partial = root / "raw_results/partial-trial.json"
        partial.parent.mkdir()
        partial.write_bytes(b"{}\n")
        _classify_rejected(root)
    else:  # pragma: no cover - guards the exact case inventory above.
        raise AssertionError(case)


def test_invalid_inventory_is_exactly_the_required_twenty_cases() -> None:
    assert len(INVALID_CASES) == 20
    assert len(set(INVALID_CASES)) == 20


def test_mode_transitions_reject_implicit_or_wrong_actions(tmp_path: Path) -> None:
    root = tmp_path / "qualification-runtime"
    with pytest.raises(FormalBootstrapError):
        bootstrap_formal_runtime(root, FIXTURE_COMMAND, mode="resume")
    root.mkdir()
    assert classify_formal_runtime(root) is FormalRuntimeState.INVALID
    with pytest.raises(FormalBootstrapError):
        bootstrap_formal_runtime(root, FIXTURE_COMMAND, mode="fresh")


def test_historical_v3_manifest_stays_frozen_after_execution_path_repair() -> None:
    repository = Path(__file__).resolve().parents[1]
    from phase_a_harness.contracts import file_sha256
    from phase_a_harness.synthetic_confirmatory_v3_contract import (
        MANIFEST_RELATIVE,
        load_v3_contract,
    )

    manifest_path = repository / MANIFEST_RELATIVE
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    binding = manifest["bound_files"]["formal_runtime_state_machine"]
    assert binding["path"] == "src/phase_a_harness/formal_runtime_state_machine.py"
    assert binding["sha256"] == file_sha256(repository / binding["path"])
    assert manifest["formal_bootstrap_contract"]["implementation_revision"] == (
        "synthetic_confirmatory_v3_bootstrap_repair_r1"
    )
    # This task deliberately preserves the failed v3 manifest byte-for-byte.
    # Its execution-adapter bindings must therefore detect, not silently
    # authorize, the newly qualified reader/runner/contract implementation.
    for name in ("v3_contract", "v3_runner", "v3_snapshot_builder"):
        entry = manifest["bound_files"][name]
        assert entry["sha256"] != file_sha256(repository / entry["path"])
    with pytest.raises(ValueError, match="exact live bindings"):
        load_v3_contract(manifest_path)


def test_old_v3_manifest_cannot_authorize_the_repair_implementation() -> None:
    repository = Path(__file__).resolve().parents[1]
    from phase_a_harness.synthetic_confirmatory_v3_contract import load_v3_contract

    old_manifest = (
        repository / "frozen_assets/synthetic_confirmatory_formal_manifest_v3.json"
    )
    with pytest.raises(ValueError):
        load_v3_contract(old_manifest)
