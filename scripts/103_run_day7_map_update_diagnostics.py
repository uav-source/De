#!/usr/bin/env python3
"""Run one authorized Day 7 Quick Shack map-update diagnostic replay."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
import tarfile
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter import experiment_a_map_snapshot_coherence as snapshots
from fastlio2_adapter import experiment_a_stage_hash as stage_hash
from fastlio2_adapter import focused_branch_stage_classifier as classifier
from fastlio2_adapter.day7_map_update_events import validate_run_trace


MAIN_RUN_ID = "multihyp_day7_map_update_rebuild_root_cause_v1"
SUB_RUN_IDS = tuple(
    f"multihyp_day7_map_update_r{index}" for index in range(1, 5)
)
SOURCE_AUDIT_SHA256 = (
    "53a956746e22748d345d2c0bb49c478a13aa2350e530f1ca8013f88e10e29ff9"
)
AMENDMENT_SHA256 = (
    "a69e159f1bc41ebd3bf04b929bed5944e516f08c76ffefb1ee0849133a0cc801"
)
SCAN_START = 150
SCAN_END = 170
EXPECTED_RECORD_COUNT = 21
EXPECTED_SNAPSHOT_COUNT = 42
DAY7_STATUS_SERVICE = "/harmful_bias/day7_map_update_status"

DAY7_RUNTIME_FILES = (
    "day7_map_mutation_events_v1.bin",
    "day7_map_mutation_events_v1.bin.sha256",
    "day7_map_mutation_event_index.csv",
    "day7_map_mutation_event_summary.json",
    "day7_map_mutation_call_summaries.json",
    "day7_map_mutation_call_summaries.csv",
    "day7_rebuild_logger_events_v1.bin",
    "day7_rebuild_logger_events_v1.bin.sha256",
    "day7_rebuild_logger_event_index.csv",
    "day7_rebuild_commit_summaries.json",
    "day7_rebuild_commit_summaries.csv",
    "map_point_identity_snapshots_v1.bin",
    "map_point_identity_snapshots_v1.bin.sha256",
    "map_point_identity_snapshot_index.csv",
    "map_point_identity_snapshot_hashes.csv",
    "day7_diagnostic_immutability_summary.json",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def validate_authorization(
    source_audit: Path, amendment: Path
) -> dict[str, Any]:
    source = source_audit.expanduser().resolve()
    amendment_path = amendment.expanduser().resolve()
    if not source.is_file() or sha256_file(source) != SOURCE_AUDIT_SHA256:
        raise RuntimeError("Day 6 source audit identity mismatch")
    if (
        not amendment_path.is_file()
        or sha256_file(amendment_path) != AMENDMENT_SHA256
    ):
        raise RuntimeError("Day 7 amendment identity mismatch")
    value = json.loads(amendment_path.read_text(encoding="utf-8"))
    required = {
        "source_audit_sha256": SOURCE_AUDIT_SHA256,
        "source_package_internal_gate_status": "FAIL",
        "source_package_internal_gate_superseded": True,
        "conflict_classification":
            "OVER_CONSTRAINED_SAME_SCAN_EQUALITY_RULE_FOR_MAP_INSERTION_STAGE",
        "day7_authorization_amendment_pass": True,
        "day7_authorized": True,
        "formal_branch_reproduced": True,
        "formal_branch_stage_localized": True,
        "first_localized_divergence_scan": 157,
        "first_localized_divergence_stage":
            "MAP_INSERTION_STAGE_DIVERGED",
        "experiment_a_pass": True,
        "stage3_start_authorized": False,
        "fast_lio2_integration_authorized": False,
        "scientific_payload_changed": False,
        "runtime_data_changed": False,
        "replay_rerun": False,
        "original_final_gate_sha256":
            "7a425b8ec1b3ba0bdfaf34c880ff6c2642e42e53c0c4748fdc0677b2b780c80e",
        "focused_stage_classification_sha256":
            "b9512d1555e9b4854303b1c0c399445411a302f8df9080c834fd9a551c2c93cb",
        "focused_first_divergence_sha256":
            "a0df66b1c534569360080461d8e5017226ad3aa2fccf5923a70591737a13cb7c",
        "full_stream_semantic_summary_sha256":
            "37fe2b5dfcf161702a54c97d0c0929d75326c19e64e27c00e675153c96676ec0",
        "source_manifest_sha256":
            "3ffaecfe5e313188060d3ed40fe088a26a410c04df4ad9f1b1ee65a07363e4d0",
        "focused_stage_localization_source_sha256":
            "be65e0c0b70659968b1056c38d0e731e1316883caeea59cf4a2482e16b87c440",
        "focused_stage_classifier_source_sha256":
            "740553d116a19ba002329969166a4e4c033eeca2031bed673430f1240ad9edb0",
        "original_finalizer_source_sha256":
            "38d7e782c53845754a07a71e1476498a28d23f0548f4a696419b39b927177fc3",
        "capacity_finalizer_source_sha256":
            "c051b0a74fb57e41fe2a30f6da1980b0fb0e0b0cccbc57c257f6097e81ffde88",
    }
    if not isinstance(value, dict) or any(
        value.get(name) != expected for name, expected in required.items()
    ):
        raise RuntimeError("Day 7 amendment authorization fields mismatch")
    member_hashes = {
        "evidence/small_results/"
        "focused_stage_hash_capacity_remediation_final_gate.json":
            required["original_final_gate_sha256"],
        "comparison/pairwise_focused_stage_classification.json":
            required["focused_stage_classification_sha256"],
        "comparison/pairwise_focused_first_divergence.json":
            required["focused_first_divergence_sha256"],
        "comparison/pairwise_full_stream_semantic_summary.json":
            required["full_stream_semantic_summary_sha256"],
        "repo/degen_overlay/manifests/harmful_bias/"
        "focused_stage_hash_capacity_remediation_manifest.json":
            required["source_manifest_sha256"],
        "repo/degen_overlay/src/fastlio2_adapter/"
        "focused_branch_stage_localization.py":
            required["focused_stage_localization_source_sha256"],
        "repo/degen_overlay/src/fastlio2_adapter/"
        "focused_branch_stage_classifier.py":
            required["focused_stage_classifier_source_sha256"],
        "repo/degen_overlay/scripts/"
        "99_finalize_focused_branch_stage_localization.py":
            required["original_finalizer_source_sha256"],
        "repo/degen_overlay/scripts/"
        "102_finalize_focused_branch_capacity_remediation.py":
            required["capacity_finalizer_source_sha256"],
    }
    with tarfile.open(source, "r:gz") as archive:
        members = archive.getmembers()
        for suffix, expected in member_hashes.items():
            matches = [
                member for member in members
                if member.isfile() and member.name.endswith(suffix)
            ]
            if len(matches) != 1:
                raise RuntimeError(
                    f"Day 7 source evidence member mismatch: {suffix}"
                )
            stream = archive.extractfile(matches[0])
            if stream is None or hashlib.sha256(
                stream.read()
            ).hexdigest() != expected:
                raise RuntimeError(
                    f"Day 7 source evidence SHA mismatch: {suffix}"
                )
    gate_results = value.get("gate_results")
    if (
        not isinstance(gate_results, dict)
        or not gate_results
        or not all(item is True for item in gate_results.values())
    ):
        raise RuntimeError("Day 7 amendment Gate results mismatch")
    return {
        "schema_version": "day7_authorization_identity_v1",
        "source_audit_sha256": SOURCE_AUDIT_SHA256,
        "amendment_sha256": AMENDMENT_SHA256,
        "source_day6_internal_gate_status": "FAIL",
        "day7_external_adjudication_applied": True,
        "day7_external_adjudication_reason":
            "OVER_CONSTRAINED_SAME_SCAN_EQUALITY_RULE_FOR_MAP_INSERTION_STAGE",
        "day7_authorization_amendment_pass": True,
        "day7_authorized": True,
        "stage3_start_authorized": False,
        "fast_lio2_integration_authorized": False,
    }


def validate_run_lock(path: Path, run_id: str) -> dict[str, Any]:
    value = json.loads(path.resolve().read_text(encoding="utf-8"))
    if value.get("main_run_id") != MAIN_RUN_ID:
        raise RuntimeError("Day 7 run-lock main identity mismatch")
    if value.get("sub_run_ids") != list(SUB_RUN_IDS):
        raise RuntimeError("Day 7 run-lock sub-run identities mismatch")
    if value.get("authorization_audit_sha256") != SOURCE_AUDIT_SHA256:
        raise RuntimeError("Day 7 run-lock source audit mismatch")
    if value.get("authorization_amendment_sha256") != AMENDMENT_SHA256:
        raise RuntimeError("Day 7 run-lock amendment mismatch")
    if (
        value.get("scan_start"),
        value.get("scan_end"),
        value.get("run_count"),
    ) != (SCAN_START, SCAN_END, 4):
        raise RuntimeError("Day 7 run-lock runtime contract mismatch")
    ports = value.get("ros_master_ports", {})
    if ports.get(run_id) != 20411 + SUB_RUN_IDS.index(run_id):
        raise RuntimeError("Day 7 ROS master port mismatch")
    return value


def configure_day7_transport(old: Any) -> None:
    prior_configure = old.configure_transport

    def configure_transport(
        base: Any, transport: Any, *, run_id: str, repeat_id: int
    ) -> None:
        prior_configure(
            base, transport, run_id=run_id, repeat_id=repeat_id
        )
        prior_run_command = transport.run_command

        def run_command(
            command: Sequence[str],
            *,
            environment: Mapping[str, str],
            output: Path | None = None,
            check: bool = True,
        ) -> Any:
            result = prior_run_command(
                command,
                environment=environment,
                output=output,
                check=check,
            )
            values = list(command)
            if values[:3] == [
                "rosparam",
                "set",
                "/harmful_bias/end_of_stream_audit_enabled",
            ]:
                for key, value in (
                    (
                        "/harmful_bias/day7_map_update_audit_enabled",
                        "true",
                    ),
                    ("/harmful_bias/day7_scan_start", str(SCAN_START)),
                    ("/harmful_bias/day7_scan_end", str(SCAN_END)),
                ):
                    prior_run_command(
                        ["rosparam", "set", key, value],
                        environment=environment,
                    )
            return result

        transport.run_command = run_command
        prior_shutdown = transport.graceful_shutdown

        def graceful_shutdown(
            roslaunch: Any,
            *,
            environment: Mapping[str, str],
            run_dir: Path,
        ) -> dict[str, Any]:
            poll = transport.bounded_trigger_call(
                DAY7_STATUS_SERVICE,
                environment=environment,
                timeout_sec=15.0,
            )
            transport.atomic_json(
                run_dir / "day7_map_update_service_evidence.json",
                dict(poll.evidence),
            )
            if (
                poll.snapshot is None
                or poll.evidence.get("service_success") is not True
            ):
                raise transport.RunFailure(
                    "RUNTIME_PRODUCT_MISSING",
                    "Day 7 map-update status service failed",
                )
            transport.atomic_json(
                run_dir / "day7_map_update_status.json",
                dict(poll.snapshot),
            )
            return prior_shutdown(
                roslaunch, environment=environment, run_dir=run_dir
            )

        transport.graceful_shutdown = graceful_shutdown

    old.configure_transport = configure_transport
    prior_materialize = old.materialize

    def materialize(*args: Any, **kwargs: Any) -> dict[str, Any]:
        summary = prior_materialize(*args, **kwargs)
        output = Path(kwargs["output"]).resolve()
        run_dir = Path(kwargs["run_dir"]).resolve()
        for name in DAY7_RUNTIME_FILES:
            source = run_dir / name
            if not source.is_file():
                raise RuntimeError(f"Day 7 runtime product missing: {name}")
            shutil.copy2(source, output / name)
        status_source = run_dir / "day7_map_update_status.json"
        shutil.copy2(
            status_source, output / "day7_map_update_pre_shutdown_status.json"
        )
        trace = validate_run_trace(output)
        status = json.loads(
            (
                output / "day7_map_mutation_event_summary.json"
            ).read_text(encoding="utf-8")
        )
        summary.update({
            "schema_version": "day7_map_update_replay_run_summary_v1",
            "day7_map_update_audit_enabled": True,
            "day7_stage_record_count": EXPECTED_RECORD_COUNT,
            "day7_snapshot_count": EXPECTED_SNAPSHOT_COUNT,
            "map_mutation_event_count": trace["event_count"],
            "event_overflow_count": trace["event_overflow_count"],
            "unclassified_event_count": trace[
                "unclassified_event_count"
            ],
            "logger_append_count": int(status["logger_append_count"]),
            "logger_apply_count": int(status["logger_apply_count"]),
            "rebuild_commit_count": int(status["rebuild_commit_count"]),
            "map_delta_accounting_failure_count": trace[
                "map_delta_accounting_failure_count"
            ],
            "map_point_identity_snapshot_count": trace["snapshot_count"],
            "day7_event_trace_schema_pass": True,
        })
        summary["complete"] = bool(summary["complete"]) and all((
            trace["event_count"] > 0,
            trace["event_overflow_count"] == 0,
            trace["unclassified_event_count"] == 0,
            trace["snapshot_count"] == EXPECTED_SNAPSHOT_COUNT,
            trace["map_delta_accounting_failure_count"] == 0,
        ))
        (output / "run_summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return summary

    old.materialize = materialize


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sequence", required=True)
    parser.add_argument("--clip", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--run-lock", required=True, type=Path)
    parser.add_argument("--endpoint-contract", required=True, type=Path)
    parser.add_argument("--authorization-audit", required=True, type=Path)
    parser.add_argument("--authorization-amendment", required=True, type=Path)
    parser.add_argument("--enable-readonly-tap", action="store_true")
    parser.add_argument("--enable-compact-export", action="store_true")
    parser.add_argument("--enable-in-call-audit", action="store_true")
    parser.add_argument("--enable-experiment-a-stage-hash", action="store_true")
    parser.add_argument("--enable-coherent-map-snapshot", action="store_true")
    parser.add_argument("--enable-day7-map-update-audit", action="store_true")
    parser.add_argument("--disable-runtime-detector", action="store_true")
    parser.add_argument("--use-frozen-tail-adjudication", action="store_true")
    args = parser.parse_args()
    if args.run_id not in SUB_RUN_IDS:
        raise RuntimeError("unauthorized Day 7 run id")
    if not all((
        args.enable_readonly_tap,
        args.enable_compact_export,
        args.enable_in_call_audit,
        args.enable_experiment_a_stage_hash,
        args.enable_coherent_map_snapshot,
        args.enable_day7_map_update_audit,
        args.disable_runtime_detector,
        args.use_frozen_tail_adjudication,
    )):
        raise RuntimeError("all Day 7 safety flags are required")
    validate_run_lock(args.run_lock, args.run_id)
    authorization = validate_authorization(
        args.authorization_audit, args.authorization_amendment
    )

    classifier.SCAN_START = SCAN_START
    classifier.SCAN_END = SCAN_END
    classifier.EXPECTED_RECORD_COUNT = EXPECTED_RECORD_COUNT
    classifier.EXPECTED_SNAPSHOTS_PER_RUN = EXPECTED_SNAPSHOT_COUNT
    stage_hash.SCAN_START = SCAN_START
    stage_hash.SCAN_END = SCAN_END
    stage_hash.EXPECTED_RECORD_COUNT = EXPECTED_RECORD_COUNT
    snapshots.SCAN_START = SCAN_START
    snapshots.SCAN_END = SCAN_END
    snapshots.EXPECTED_RECORD_COUNT = EXPECTED_RECORD_COUNT
    snapshots.EXPECTED_SNAPSHOTS_PER_RUN = EXPECTED_SNAPSHOT_COUNT
    snapshots.EXPECTED_TOTAL_SNAPSHOTS = 2 * EXPECTED_SNAPSHOT_COUNT

    focused = load_module(
        ROOT / "scripts/97_run_focused_branch_stage_localization.py",
        "day7_focused_transport",
    )
    focused.MAIN_RUN_ID = MAIN_RUN_ID
    focused.SUB_RUN_IDS = SUB_RUN_IDS
    focused.AUTHORIZATION_SHA256 = SOURCE_AUDIT_SHA256
    focused.SCAN_START = SCAN_START
    focused.SCAN_END = SCAN_END
    focused.EXPECTED_RECORD_COUNT = EXPECTED_RECORD_COUNT
    focused.EXPECTED_SNAPSHOTS_PER_RUN = EXPECTED_SNAPSHOT_COUNT
    focused.validate_authorization_archive = (
        lambda _path: dict(authorization)
    )
    prior_load = focused._load

    def patched_load(path: Path, name: str) -> Any:
        module = prior_load(path, name)
        if path.name == "85_run_experiment_a_stage_hash_pair.py":
            configure_day7_transport(module)
        return module

    focused._load = patched_load
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
    forwarded.extend((
        "--enable-readonly-tap",
        "--enable-compact-export",
        "--enable-in-call-audit",
        "--enable-experiment-a-stage-hash",
        "--enable-coherent-map-snapshot",
        "--disable-runtime-detector",
        "--use-frozen-tail-adjudication",
    ))
    sys.argv = forwarded
    return int(focused.main())


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
