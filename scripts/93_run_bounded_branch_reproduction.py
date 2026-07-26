#!/usr/bin/env python3
"""Run one of four authorized bounded formal-branch replays."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import tarfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MAIN_RUN_ID = "multihyp_day6_bounded_formal_branch_reproduction_v1"
SUB_RUN_IDS = tuple(
    f"multihyp_day6_branch_repro_r{index}" for index in range(1, 5)
)
AUTHORIZATION_SHA256 = (
    "d61591c1dfa89a17836b950e131b0052f8df25fbf209cc64dd930defa1bd0956"
)


def _load(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_authorization_archive(path: Path) -> dict[str, Any]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file() or _sha256(resolved) != AUTHORIZATION_SHA256:
        raise RuntimeError("bounded branch authorization identity mismatch")
    with tarfile.open(resolved, "r:gz") as archive:
        manifest_member = next(
            (
                member
                for member in archive.getmembers()
                if member.name.endswith(
                    "experiment_a_map_snapshot_coherence_manifest.json"
                )
            ),
            None,
        )
        if manifest_member is None:
            raise RuntimeError("coherence authorization manifest missing")
        stream = archive.extractfile(manifest_member)
        if stream is None:
            raise RuntimeError("coherence authorization manifest unreadable")
        manifest = json.load(stream)
    required = {
        "map_snapshot_coherence_pass": True,
        "map_snapshot_cross_scan_coherence_pass": True,
        "experiment_a_map_snapshot_remediation_execution_pass": True,
        "original_scan147_formal_branch_reproduced": False,
        "day7_recommended": False,
        "day7_authorized": False,
    }
    if any(manifest.get(key) is not expected for key, expected in required.items()):
        raise RuntimeError("coherence authorization scientific gate mismatch")
    return {
        "schema_version":
            "bounded_formal_branch_reproduction_authorization_v1",
        "authorization_audit_path": str(resolved),
        "authorization_audit_sha256": AUTHORIZATION_SHA256,
        **required,
        "experiment_a_stage_localization_pass": False,
        "experiment_a_pass": False,
        "overbroad_prior_experiment_a_pass_inherited": False,
        "bounded_four_replay_execution_authorized": True,
        "day7_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sequence", required=True)
    parser.add_argument("--clip", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--run-lock", required=True, type=Path)
    parser.add_argument("--endpoint-contract", required=True, type=Path)
    parser.add_argument("--authorization-audit", required=True, type=Path)
    parser.add_argument("--enable-readonly-tap", action="store_true")
    parser.add_argument("--enable-compact-export", action="store_true")
    parser.add_argument("--enable-in-call-audit", action="store_true")
    parser.add_argument("--enable-experiment-a-stage-hash", action="store_true")
    parser.add_argument("--enable-coherent-map-snapshot", action="store_true")
    parser.add_argument("--disable-runtime-detector", action="store_true")
    parser.add_argument("--use-frozen-tail-adjudication", action="store_true")
    args = parser.parse_args()
    if args.run_id not in SUB_RUN_IDS:
        raise RuntimeError("unauthorized bounded replay run id")
    if not all(
        (
            args.enable_readonly_tap,
            args.enable_compact_export,
            args.enable_in_call_audit,
            args.enable_experiment_a_stage_hash,
            args.enable_coherent_map_snapshot,
            args.disable_runtime_detector,
            args.use_frozen_tail_adjudication,
        )
    ):
        raise RuntimeError("all bounded replay safety flags are required")

    old = _load(
        ROOT / "scripts/89_run_experiment_a_map_snapshot_remediation.py",
        "bounded_branch_coherent_transport",
    )
    old.MAIN_RUN_ID = MAIN_RUN_ID
    old.SUB_RUN_IDS = SUB_RUN_IDS
    old.AUTHORIZATION_SHA256 = AUTHORIZATION_SHA256
    old.validate_authorization_archive = validate_authorization_archive
    forwarded = [sys.argv[0]]
    for name, value in (
        ("--sequence", args.sequence),
        ("--clip", str(args.clip)),
        ("--run-id", args.run_id),
        ("--output-dir", str(args.output_dir)),
        ("--run-lock", str(args.run_lock)),
        ("--endpoint-contract", str(args.endpoint_contract)),
        ("--authorization-audit", str(args.authorization_audit)),
    ):
        forwarded.extend((name, value))
    forwarded.extend(
        (
            "--enable-readonly-tap",
            "--enable-compact-export",
            "--enable-in-call-audit",
            "--enable-experiment-a-stage-hash",
            "--enable-coherent-map-snapshot",
            "--disable-runtime-detector",
            "--use-frozen-tail-adjudication",
        )
    )
    sys.argv = forwarded
    result = int(old.main())
    if result == 0:
        summary_path = args.output_dir.expanduser().resolve() / "run_summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary.update(
            {
                "schema_version":
                    "day6_bounded_formal_branch_replay_run_summary_v1",
                "wrapper_exit_code": 0,
                "wrapper_failure_classification": "NONE",
                "wrapper_pipeline_clean_exit_pass": True,
            }
        )
        summary_path.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return result


if __name__ == "__main__":
    raise SystemExit(main())

