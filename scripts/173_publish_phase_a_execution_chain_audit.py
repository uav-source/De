#!/usr/bin/env python3
"""Publish a verified fixture execution-chain audit from an empty directory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_perturbation.phase_a_execution_chain_audit import AUDIT_LOCK_RELATIVE
from zero_perturbation.phase_a_stage1_publisher import publish_phase_a_execution_chain_audit


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--verification", type=Path, required=True)
    parser.add_argument("--fixture-run-manifest", type=Path, required=True)
    parser.add_argument("--resume-audit", type=Path, required=True)
    parser.add_argument("--tamper-audit", type=Path, required=True)
    parser.add_argument("--protocol-lock", type=Path, default=ROOT / AUDIT_LOCK_RELATIVE)
    args = parser.parse_args()
    result = publish_phase_a_execution_chain_audit(
        artifact_dir=args.artifact_dir,
        analysis=_load(args.analysis),
        verification=_load(args.verification),
        fixture_run_manifest=_load(args.fixture_run_manifest),
        resume_audit=_load(args.resume_audit),
        tamper_audit=_load(args.tamper_audit),
        audit_protocol_lock=args.protocol_lock,
    )
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
