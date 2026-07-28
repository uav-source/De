"""Shared constructors for strict Formal Execution Lock rejection tests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from zero_perturbation.phase_a_execution_chain_audit import implementation_manifest
from zero_perturbation.phase_a_formal_execution_lock_schema import (
    PROTOCOL_LOCK_RELATIVE_PATH,
    SNAPSHOT_LOCK_RELATIVE_PATH,
    build_phase_a_formal_execution_lock,
    validate_phase_a_formal_execution_lock_strict,
)
from zero_perturbation.phase_a_trial_result_schema import (
    canonical_json_bytes,
    canonical_json_sha256,
)


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class FormalLockCase:
    lock_path: Path
    manifest_path: Path
    value: dict


def write_json(path: Path, value: dict) -> None:
    path.write_bytes(canonical_json_bytes(value))


def make_valid_formal_lock(tmp_path: Path) -> FormalLockCase:
    manifest_path = tmp_path / "implementation_manifest.json"
    write_json(manifest_path, implementation_manifest(ROOT))
    value = build_phase_a_formal_execution_lock(
        root=ROOT,
        implementation_manifest_path=manifest_path,
        created_from_commit="0" * 40,
        created_at_utc="2026-07-28T00:00:00Z",
    )
    lock_path = tmp_path / "formal_execution_lock.json"
    write_json(lock_path, value)
    return FormalLockCase(lock_path, manifest_path, value)


def rewrite_payload_sha(value: dict) -> dict:
    payload = {name: item for name, item in value.items() if name != "lock_payload_sha256"}
    value["lock_payload_sha256"] = canonical_json_sha256(payload)
    return value


def validate_case(case: FormalLockCase, path: Path | None = None) -> dict:
    return validate_phase_a_formal_execution_lock_strict(
        path or case.lock_path,
        root=ROOT,
        protocol_lock=ROOT / PROTOCOL_LOCK_RELATIVE_PATH,
        snapshot_lock=ROOT / SNAPSHOT_LOCK_RELATIVE_PATH,
        implementation_manifest_path=case.manifest_path,
    )


def wrong_binding_error(tmp_path: Path, binding: str) -> str:
    case = make_valid_formal_lock(tmp_path)
    value = json.loads(json.dumps(case.value))
    value["implementation_bindings"][binding] = "0" * 64
    rewrite_payload_sha(value)
    path = tmp_path / f"wrong-{binding}.json"
    write_json(path, value)
    try:
        validate_case(case, path)
    except ValueError as error:
        return str(error)
    raise AssertionError(f"wrong binding was accepted: {binding}")
