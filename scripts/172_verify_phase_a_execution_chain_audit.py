#!/usr/bin/env python3
"""Independently verify a fixture execution-chain run from raw disk results."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_perturbation.phase_a_execution_chain_fixture import FIXTURE_LOCK_RELATIVE, FIXTURE_PLAN_RELATIVE
from zero_perturbation.phase_a_stage1_independent_verifier import independently_verify_phase_a_stage1_fixture
from zero_perturbation.phase_a_trial_result_schema import canonical_json_bytes
from zero_perturbation.phase_a_trial_result_writer import atomic_write_bytes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--fixture-plan", type=Path, default=ROOT / FIXTURE_PLAN_RELATIVE)
    parser.add_argument("--fixture-lock", type=Path, default=ROOT / FIXTURE_LOCK_RELATIVE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    analysis = json.loads(args.analysis.read_text(encoding="utf-8"))
    result = independently_verify_phase_a_stage1_fixture(
        run_dir=args.run_dir,
        fixture_plan=args.fixture_plan,
        fixture_lock=args.fixture_lock,
        analysis_output=analysis,
    )
    if args.output:
        atomic_write_bytes(args.output, canonical_json_bytes(result))
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0 if result["PHASE_A_EXECUTION_CHAIN_INDEPENDENT_VERIFIER_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
