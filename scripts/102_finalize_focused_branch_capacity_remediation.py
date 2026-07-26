#!/usr/bin/env python3
"""Finalize the capacity-remediated focused branch localization Gate."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
RUN_IDS = tuple(
    f"multihyp_day6_focused_capacity_r{index}" for index in range(1, 5)
)


def _load(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def augment_gate(
    gate: Mapping[str, Any],
    capacity_gate: Mapping[str, Any],
) -> dict[str, Any]:
    value = dict(gate)
    value.update({
        "schema_version":
            "focused_stage_hash_capacity_remediation_final_gate_v1",
        "focused_stage_hash_capacity_remediation_pass":
            capacity_gate.get(
                "focused_stage_hash_capacity_remediation_pass"
            ) is True,
        "focused_stage_155_205_replay_authorized":
            capacity_gate.get(
                "focused_stage_155_205_replay_authorized"
            ) is True,
        "maximum_stage_record_count": 51,
        "offline_analysis_code_changed_after_runtime_lock": False,
        "STAGE2_GATE": "FAIL",
        "TRANSITION": "PIVOT",
        "DAY7_AUTHORIZED": False,
        "STAGE3_START_AUTHORIZED": False,
        "STAGE4_START_AUTHORIZED": False,
        "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
        "HARMFUL_BIAS_DETECTABILITY_STATUS":
            "NOT_EVALUATED_DAY6_FOCUSED_STAGE_CAPACITY_REMEDIATION",
        "detector_called": False,
        "odi_computed": False,
        "weak_direction_computed": False,
        "additional_replay_recommended": False,
        "additional_replay_authorized": False,
    })
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--comparison-dir", required=True, type=Path)
    parser.add_argument("--capacity-gate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    capacity_gate = json.loads(
        args.capacity_gate.read_text(encoding="utf-8")
    )
    if not all(
        capacity_gate.get(name) is True for name in (
            "focused_stage_hash_capacity_remediation_pass",
            "focused_stage_155_205_replay_authorized",
        )
    ):
        raise RuntimeError("capacity remediation Gate is not open")
    frozen = _load(
        ROOT / "scripts/99_finalize_focused_branch_stage_localization.py",
        "focused_capacity_remediation_frozen_finalizer",
    )
    frozen.RUN_IDS = RUN_IDS
    sys.argv = [
        sys.argv[0],
        "--runtime-root", str(args.runtime_root),
        "--comparison-dir", str(args.comparison_dir),
        "--output", str(args.output),
    ]
    result = int(frozen.main())
    gate = json.loads(args.output.read_text(encoding="utf-8"))
    value = augment_gate(gate, capacity_gate)
    args.output.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(value, sort_keys=True))
    return result


if __name__ == "__main__":
    raise SystemExit(main())
