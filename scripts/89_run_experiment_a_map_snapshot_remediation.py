#!/usr/bin/env python3
"""Run one of two authorized coherent-map Experiment A replays."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tarfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.experiment_a_map_snapshot_coherence import (  # noqa: E402
    materialize_snapshot_evidence,
)


MAIN_RUN_ID = "multihyp_day6_experiment_a_map_snapshot_coherence_v1"
SUB_RUN_IDS = (
    "multihyp_day6_experiment_a_map_snapshot_r1",
    "multihyp_day6_experiment_a_map_snapshot_r2",
)
AUTHORIZATION_SHA256 = (
    "1d5ab7f3e3ed44f8c9c77776ecb6504980e5e2abe92c618f829bb9b108130513"
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
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_authorization_archive(path: Path) -> dict[str, Any]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file() or _sha256(resolved) != AUTHORIZATION_SHA256:
        raise RuntimeError("Experiment A remediation authorization mismatch")
    with tarfile.open(resolved, "r:gz") as archive:
        names = archive.getnames()
        required = (
            "experiment_a_stage_classification.json",
            "day6_experiment_a_input_map_hash_manifest.json",
        )
        for fragment in required:
            if not any(name.endswith(fragment) for name in names):
                raise RuntimeError(
                    f"authorization evidence missing: {fragment}"
                )
    return {
        "schema_version":
            "experiment_a_map_snapshot_remediation_authorization_v1",
        "authorization_audit_sha256": AUTHORIZATION_SHA256,
        "experiment_a_replay_execution_pass": True,
        "experiment_a_hash_capture_infrastructure_pass": True,
        "map_snapshot_coherence_pass": False,
        "previous_map_insertion_stage_diverged_conclusion": "REVOKED",
        "experiment_a_map_snapshot_coherence_remediation_authorized": True,
        "day7_authorized": False,
        "experiment_b_authorized": False,
        "experiment_c_authorized": False,
        "stage3_start_authorized": False,
        "fast_lio2_integration_authorized": False,
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
    if not args.enable_coherent_map_snapshot:
        raise RuntimeError("coherent map snapshot flag is required")

    old = _load(
        ROOT / "scripts/85_run_experiment_a_stage_hash_pair.py",
        "experiment_a_coherent_map_transport",
    )
    old.MAIN_RUN_ID = MAIN_RUN_ID
    old.SUB_RUN_IDS = SUB_RUN_IDS
    old.EXPECTED_AUDIT_SHA256 = AUTHORIZATION_SHA256
    old.validate_authorization_archive = validate_authorization_archive
    prior_materialize = old.materialize

    def materialize(*materialize_args: Any, **materialize_kwargs: Any) -> Any:
        summary = prior_materialize(*materialize_args, **materialize_kwargs)
        output = Path(materialize_kwargs["output"])
        records = json.loads(
            (output / "experiment_a_stage_hash_records_v2.json").read_text(
                encoding="utf-8"
            )
        )
        snapshot = materialize_snapshot_evidence(records, output)
        summary.update(
            {
                "schema_version":
                    "day6_experiment_a_map_snapshot_replay_run_summary_v1",
                "stage_hash_v2_record_count":
                    summary["stage_hash_record_count"],
                "map_before_snapshot_count":
                    snapshot["map_before_snapshot_count"],
                "map_after_snapshot_count":
                    snapshot["map_after_snapshot_count"],
                "coherent_snapshot_count":
                    snapshot["coherent_snapshot_count"],
                "incoherent_snapshot_count":
                    snapshot["incoherent_snapshot_count"],
                "cross_scan_continuity_violation_count":
                    snapshot["cross_scan_continuity_violation_count"],
                "map_snapshot_coherence_pass":
                    snapshot["map_snapshot_coherence_pass"],
                "map_snapshot_cross_scan_coherence_pass":
                    snapshot["map_snapshot_cross_scan_coherence_pass"],
                "snapshot_lock_wait_statistics":
                    snapshot["lock_wait_ns"],
                "snapshot_copy_cost_statistics":
                    snapshot["locked_copy_ns"],
            }
        )
        summary["complete"] = bool(summary["complete"]) and all(
            (
                summary["map_before_snapshot_count"] == 26,
                summary["map_after_snapshot_count"] == 26,
                summary["coherent_snapshot_count"] == 52,
                summary["incoherent_snapshot_count"] == 0,
                summary["cross_scan_continuity_violation_count"] == 0,
            )
        )
        old_base = old.load_module(
            ROOT / "scripts/75_run_day6_fallback_real_replay.py",
            "experiment_a_coherent_map_output_helper",
        )
        old_base.write_json(output / "run_summary.json", summary)
        return summary

    old.materialize = materialize
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
            "--disable-runtime-detector",
            "--use-frozen-tail-adjudication",
        )
    )
    sys.argv = forwarded
    return int(old.main())


if __name__ == "__main__":
    raise SystemExit(main())
