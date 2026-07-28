#!/usr/bin/env python3
"""Build the complete Phase A Stage-1 Formal Execution Lock v1.1."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_perturbation.phase_a_formal_execution_lock_schema import (
    FORMAL_LOCK_RELATIVE_PATH,
    IMPLEMENTATION_MANIFEST_RELATIVE_PATH,
    PROTOCOL_LOCK_RELATIVE_PATH,
    SNAPSHOT_LOCK_RELATIVE_PATH,
    build_phase_a_formal_execution_lock,
    validate_phase_a_formal_execution_lock_strict,
)
from zero_perturbation.phase_a_trial_result_schema import canonical_json_bytes, file_sha256
from zero_perturbation.phase_a_trial_result_writer import atomic_write_bytes


AUDIT_ROOT = ROOT / "artifacts/current/zero_perturbation_phase_a_execution_chain_audit_v1_1"


def _json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise ValueError(f"expected JSON object: {path}")
    return value


def _require_execution_chain_v1_1_pass() -> None:
    decision = _json(AUDIT_ROOT / "final_decision.json")
    verification = _json(AUDIT_ROOT / "artifact_verification.json")
    if (
        decision.get("PHASE_A_EXECUTION_CHAIN_AUDIT_PASS") is not True
        or verification.get("PHASE_A_EXECUTION_CHAIN_ARTIFACT_VERIFICATION_PASS") is not True
    ):
        raise PermissionError("execution-chain audit v1.1 must pass before formal lock construction")


def _head_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Formal Execution Lock v1.1")
    parser.add_argument("--output", type=Path, default=ROOT / FORMAL_LOCK_RELATIVE_PATH)
    parser.add_argument(
        "--implementation-manifest",
        type=Path,
        default=ROOT / IMPLEMENTATION_MANIFEST_RELATIVE_PATH,
    )
    parser.add_argument("--created-from-commit", default=None)
    parser.add_argument("--created-at-utc", default=None)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    _require_execution_chain_v1_1_pass()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"formal lock already exists: {output}")
    created_at = args.created_at_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    value = build_phase_a_formal_execution_lock(
        root=ROOT,
        implementation_manifest_path=args.implementation_manifest,
        created_from_commit=args.created_from_commit or _head_commit(),
        created_at_utc=created_at,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(output, canonical_json_bytes(value))
    validated = validate_phase_a_formal_execution_lock_strict(
        output,
        root=ROOT,
        protocol_lock=ROOT / PROTOCOL_LOCK_RELATIVE_PATH,
        snapshot_lock=ROOT / SNAPSHOT_LOCK_RELATIVE_PATH,
        implementation_manifest_path=args.implementation_manifest,
    )
    result = {
        **validated["validation"],
        "formal_lock_path": str(output),
        "formal_lock_sha256": file_sha256(output),
        "implementation_binding_count": len(validated["implementation_bindings"]),
        "schema_version": "phase_a_formal_execution_lock_builder_result_v1_1",
    }
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
