#!/usr/bin/env python3
"""Independent command-line verifier for Formal Execution Lock release v1.2."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_perturbation.phase_a_formal_execution_lock_schema import (
    FORMAL_LOCK_RELATIVE_PATH,
    IMPLEMENTATION_MANIFEST_RELATIVE_PATH,
    PROTOCOL_LOCK_RELATIVE_PATH,
    SNAPSHOT_LOCK_RELATIVE_PATH,
    validate_phase_a_formal_execution_lock_strict,
)
from zero_perturbation.phase_a_trial_result_schema import file_sha256


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify Formal Execution Lock release v1.2")
    parser.add_argument(
        "--formal-execution-lock", type=Path, default=ROOT / FORMAL_LOCK_RELATIVE_PATH
    )
    parser.add_argument("--protocol-lock", type=Path, default=ROOT / PROTOCOL_LOCK_RELATIVE_PATH)
    parser.add_argument("--snapshot-lock", type=Path, default=ROOT / SNAPSHOT_LOCK_RELATIVE_PATH)
    parser.add_argument(
        "--implementation-manifest",
        type=Path,
        default=ROOT / IMPLEMENTATION_MANIFEST_RELATIVE_PATH,
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    value = validate_phase_a_formal_execution_lock_strict(
        args.formal_execution_lock,
        root=ROOT,
        protocol_lock=args.protocol_lock,
        snapshot_lock=args.snapshot_lock,
        implementation_manifest_path=args.implementation_manifest,
    )
    output = {
        **value["validation"],
        "FORMAL_LOCK_V1_1_ARTIFACT_VERIFICATION_PASS": True,
        "formal_lock_sha256": file_sha256(args.formal_execution_lock),
        "implementation_binding_count": len(value["implementation_bindings"]),
        "schema_version": "phase_a_formal_execution_lock_verification_v1_2",
    }
    print(json.dumps(output, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
