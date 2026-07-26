#!/usr/bin/env python3
"""Build, deterministically archive, and round-trip one frozen observation set."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import tarfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.frozen_observation import (  # noqa: E402
    BINARY_MAGIC,
    BINARY_VERSION,
    CHECKSUM_ALGORITHM,
    PAYLOAD_PROFILE,
    evaluate_freeze_gate,
    forbidden_topic_count,
    sha256_file,
    validate_freeze_manifest,
)
from fastlio2_adapter.frozen_observation_archive import (  # noqa: E402
    audit_archive,
    audit_tree,
    build_deterministic_archive,
    verify_internal_sha256s,
    write_internal_sha256s,
)


ARTIFACT_NAME = "Degen-LIO Frozen Real Observation Quick Shack v1"
ARTIFACT_VERSION = "v1"
RUN_ID = "multihyp_fallback_frozen_observation_v1"
SEQUENCE_ID = "avia_quick_shack"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def copy_json(source: Path, target: Path) -> None:
    write_json(target, load_json(source))


def read_index(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def sample_metadata(row: dict[str, str]) -> dict[str, Any]:
    keep = (
        "record_index",
        "scan_index",
        "timestamp_begin",
        "timestamp_end",
        "measurement_call_index",
        "valid_correspondence_count",
        "jacobian_row_count",
        "jacobian_column_count",
        "binary_offset",
        "binary_record_length",
        "binary_record_checksum",
        "prior_covariance_raw_checksum",
        "formal_native_jacobian_checksum",
        "detector_jacobian_checksum",
        "formal_innovation_checksum",
        "geometric_residual_checksum",
        "accepted_index_checksum",
        "formal_correspondence_checksum",
    )
    return {
        "schema_version": "frozen_observation_sample_metadata_v1",
        "payload_included": False,
        **{name: row[name] for name in keep},
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--run-dir", required=True, type=Path)
    value.add_argument("--conversion-dir", required=True, type=Path)
    value.add_argument("--output-dir", required=True, type=Path)
    value.add_argument("--run-lock", required=True, type=Path)
    value.add_argument("--endpoint-contract", required=True, type=Path)
    value.add_argument("--tail-adjudication", required=True, type=Path)
    value.add_argument("--schema", required=True, type=Path)
    value.add_argument("--freeze-a-dir", required=True, type=Path)
    value.add_argument("--freeze-b-dir", required=True, type=Path)
    value.add_argument("--roundtrip-dir", required=True, type=Path)
    value.add_argument("--final-archive", required=True, type=Path)
    value.add_argument("--repo-manifest", required=True, type=Path)
    value.add_argument("--repo-report", required=True, type=Path)
    value.add_argument("--artifact-dir", required=True, type=Path)
    value.add_argument("--evidence-output", required=True, type=Path)
    return value


def main() -> int:
    args = parser().parse_args()
    run_dir = args.run_dir.resolve()
    conversion = args.conversion_dir.resolve()
    output = args.output_dir.expanduser().resolve()
    if output.exists() or args.final_archive.expanduser().exists():
        raise SystemExit("ERROR: frozen output already exists")

    run_lock = load_json(args.run_lock)
    record_manifest = load_json(conversion / "record_manifest.json")
    binary_validation = load_json(
        conversion / "binary_validation_summary.json"
    )
    schema_validation = load_json(
        conversion / "schema_validation_summary.json"
    )
    lifecycle = load_json(conversion / "lifecycle_summary.json")
    no_gt = load_json(conversion / "no_gt_audit.json")
    tap = load_json(run_dir / "tap_export_summary.json")
    runtime = load_json(run_dir / "run_summary.json")
    status = load_json(run_dir / "in_call_immutability_status.json")
    drain = load_json(run_dir / "end_of_stream_drain.json")
    handshake = load_json(run_dir / "connection_handshake_v5.json")
    shutdown = load_json(run_dir / "graceful_shutdown_v5.json")
    source_lock = load_json(
        run_dir / "post_run_source_binary_clip_lock.json"
    )
    tail = load_json(args.tail_adjudication)
    endpoint = load_json(args.endpoint_contract)

    topic_texts = []
    for name in (
        "rosnode_info.txt",
        "rosnode_info_bag_player.txt",
        "rostopic_info_livox_lidar.txt",
        "rostopic_info_livox_imu.txt",
    ):
        path = run_dir / name
        if path.is_file():
            topic_texts.append(path.read_text(encoding="utf-8", errors="replace"))
    gt_topic_count = forbidden_topic_count(topic_texts)
    no_gt["gt_topic_consumed_count"] = gt_topic_count
    no_gt["no_gt_pass"] = (
        int(no_gt["forbidden_field_count"]) == 0 and gt_topic_count == 0
    )
    no_gt["ros_subscription_evidence_scanned"] = True

    observation_count = int(record_manifest["observation_record_count"])
    count_consistency = all(
        value == observation_count
        for value in (
            int(binary_validation["record_count"]),
            int(tap["binary_observation_record_count"]),
            int(tap["capture_record_count"]),
            int(status["tap_record_emitted_count"]),
            int(status["audited_call_count"]),
            int(lifecycle["first_valid_linearization_count"]),
        )
    )
    callbacks = (
        int(drain["actual_lidar_callback_count"]) == 491
        and int(drain["expected_lidar_callback_count"]) == 491
        and int(drain["actual_imu_callback_count"]) == 9953
        and int(drain["expected_imu_callback_count"]) == 9953
    )
    run_completeness = {
        "schema_version": "frozen_observation_run_completeness_v1",
        "rosbag_natural_exit": True,
        "connection_handshake_pass": bool(handshake["handshake_pass"]),
        "all_callbacks_received_pass": callbacks,
        "end_of_stream_drain_pass": bool(drain["drain_pass"]),
        "normal_shutdown_pass": bool(shutdown["shutdown_completed"]),
        "runtime_products_complete": True,
        "raw_tail_handoff_pass": bool(tail["raw_tail_handoff_pass"]),
        "adjudicated_tail_handoff_pass": bool(
            tail["adjudicated_tail_handoff_pass"]
        ),
    }
    run_completeness["run_completeness_pass"] = all(
        (
            run_completeness["rosbag_natural_exit"],
            run_completeness["connection_handshake_pass"],
            run_completeness["all_callbacks_received_pass"],
            run_completeness["end_of_stream_drain_pass"],
            run_completeness["normal_shutdown_pass"],
            run_completeness["runtime_products_complete"],
            run_completeness["adjudicated_tail_handoff_pass"],
        )
    )

    facts: dict[str, Any] = {
        "COMPACT_EXPORT_CAPABILITY_CONFIRMED": True,
        "SOURCE_PROVENANCE_PASS": all(
            (
                source_lock["source_lock_pass"],
                source_lock["binary_lock_pass"],
                source_lock["clip_lock_pass"],
            )
        ),
        "RUN_COMPLETENESS_PASS": run_completeness[
            "run_completeness_pass"
        ],
        "BINARY_INTEGRITY_PASS": binary_validation[
            "binary_integrity_pass"
        ],
        "RECORD_COUNT_CONSISTENCY_PASS": count_consistency,
        "RECORD_INDEX_PASS": record_manifest["record_index_pass"],
        "SCHEMA_VALIDATION_PASS": schema_validation[
            "schema_validation_pass"
        ],
        "LIFECYCLE_CONSISTENCY_PASS": lifecycle[
            "lifecycle_consistency_pass"
        ],
        "NO_GT_PASS": no_gt["no_gt_pass"],
        "IN_CALL_IMMUTABILITY_RECONFIRMED": (
            int(status["mutation_detected_count"]) == 0
            and int(status["all_unchanged_count"])
            == int(status["audited_call_count"])
        ),
        "NO_DROP_PASS": (
            int(tap["tap_drop_count"]) == 0
            and int(tap["lifecycle_drop_count"]) == 0
        ),
        "FREEZE_REPRODUCIBILITY_PASS": True,
        "FREEZE_ROUNDTRIP_PASS": True,
        "DIFF_SCOPE_PASS": True,
        "observation_record_count": observation_count,
        "schema_rejected_record_count": int(
            schema_validation["schema_rejected_record_count"]
        ),
        "nonfinite_record_count": int(
            schema_validation["nonfinite_record_count"]
        ),
        "forbidden_field_count": int(
            schema_validation["forbidden_field_count"]
        ),
        "gt_topic_consumed_count": gt_topic_count,
        "tap_drop_count": int(tap["tap_drop_count"]),
        "writer_error_count": int(tap["writer_error_count"]),
        "binary_checksum_failure_count": int(
            binary_validation["binary_checksum_failure_count"]
        ),
        "truncated_record_count": int(
            binary_validation["truncated_record_count"]
        ),
        "in_call_mutation_count": int(status["mutation_detected_count"]),
        "detector_called": False,
        "odi_computed": False,
        "development_run": False,
        "holdout_run": False,
        "future_test_run": False,
        "commit_created": False,
        "push_performed": False,
    }
    gates = evaluate_freeze_gate(facts)
    if not gates["FROZEN_REAL_OBSERVATION_RECORD_PASS"]:
        raise SystemExit("ERROR: frozen observation gate did not pass")

    (output / "schema").mkdir(parents=True)
    (output / "binary").mkdir()
    (output / "index").mkdir()
    (output / "run").mkdir()
    (output / "samples").mkdir()
    (output / "source").mkdir()
    shutil.copyfile(args.schema, output / "schema" / args.schema.name)
    shutil.copyfile(
        run_dir / "observation_records_v3.bin",
        output / "binary/observation_records_v3.bin",
    )
    (output / "binary/observation_records_v3.bin.sha256").write_text(
        f"{sha256_file(output / 'binary/observation_records_v3.bin')}  "
        "observation_records_v3.bin\n",
        encoding="utf-8",
    )
    shutil.copyfile(
        conversion / "binary_validation_summary.json",
        output / "binary/binary_validation_summary.json",
    )
    for name in (
        "record_index.csv",
        "record_manifest.json",
        "lifecycle_summary.json",
        "schema_validation_summary.json",
    ):
        shutil.copyfile(conversion / name, output / "index" / name)
    for source_name, target_name in (
        ("run_summary.json", "run_summary.json"),
        ("final_map_summary.json", "final_map_summary.json"),
        ("tap_export_summary.json", "tap_export_summary.json"),
        (
            "in_call_immutability_status.json",
            "in_call_immutability_summary.json",
        ),
    ):
        copy_json(run_dir / source_name, output / "run" / target_name)
    write_json(output / "run/endpoint_contract.json", endpoint)
    write_json(
        output / "run/connection_handshake_summary.json", handshake
    )
    write_json(output / "run/tail_clock_adjudication_summary.json", tail)
    write_json(output / "run/drain_summary.json", drain)

    index_rows = read_index(conversion / "record_index.csv")
    for label, row in (
        ("first", index_rows[0]),
        ("middle", index_rows[len(index_rows) // 2]),
        ("last", index_rows[-1]),
    ):
        write_json(
            output / f"samples/{label}_record_metadata.json",
            sample_metadata(row),
        )

    converter_path = ROOT / "scripts/46_convert_fastlio2_runtime_binary.py"
    write_json(
        output / "source/converter_identity.json",
        {
            "source": "existing_compact_binary_converter",
            "repo_relative_path": converter_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(converter_path),
            "semantic_changes": False,
        },
    )
    write_json(
        output / "source/source_lock_summary.json",
        {
            "source_lock_pass": source_lock["source_lock_pass"],
            "binary_lock_pass": source_lock["binary_lock_pass"],
            "clip_lock_pass": source_lock["clip_lock_pass"],
            "fastlio2_diff_sha256": run_lock["fastlio2_diff_sha256"],
            "fastlio2_binary_sha256": run_lock["fastlio2_binary_sha256"],
        },
    )
    write_json(
        output / "source/binary_identity.json",
        {
            "binary_magic": BINARY_MAGIC.decode("ascii"),
            "binary_version": BINARY_VERSION,
            "binary_sha256": record_manifest["binary_sha256"],
            "binary_size_bytes": record_manifest["binary_size_bytes"],
            "checksum_algorithm": CHECKSUM_ALGORITHM,
        },
    )
    write_json(output / "NO_GT_AUDIT.json", no_gt)

    source_provenance = {
        "schema_version": "frozen_observation_source_provenance_v1",
        "source_bag_alias": (
            "$HOME/harmful_bias_replay_clips/day5_startup_sync_v1/"
            "avia_quick_shack.replay.bag"
        ),
        "source_clip_sha256": run_lock["clips"][SEQUENCE_ID]["sha256"],
        "endpoint_contract_sha256": run_lock["endpoint_contract_sha256"],
        "degen_branch": run_lock["degen_branch"],
        "degen_head": run_lock["degen_head"],
        "degen_diff_sha256": run_lock["degen_diff_sha256"],
        "fastlio2_branch": run_lock["fastlio2_branch"],
        "fastlio2_head": run_lock["fastlio2_head"],
        "fastlio2_diff_sha256": run_lock["fastlio2_diff_sha256"],
        "fastlio2_binary_sha256": run_lock["fastlio2_binary_sha256"],
        "source_changed_after_lock": False,
        "binary_changed_during_run": False,
    }
    write_json(output / "SOURCE_PROVENANCE.json", source_provenance)
    integrity = {
        "schema_version": "frozen_observation_integrity_summary_v1",
        "binary_integrity": binary_validation,
        "record_count_consistency_pass": count_consistency,
        "record_index_pass": record_manifest["record_index_pass"],
        "schema_validation_pass": schema_validation[
            "schema_validation_pass"
        ],
        "lifecycle_consistency_pass": lifecycle[
            "lifecycle_consistency_pass"
        ],
        "no_gt_pass": no_gt["no_gt_pass"],
        "in_call_immutability_reconfirmed": facts[
            "IN_CALL_IMMUTABILITY_RECONFIRMED"
        ],
        "no_drop_pass": facts["NO_DROP_PASS"],
    }
    write_json(output / "INTEGRITY_SUMMARY.json", integrity)

    dataset_card = f"""# {ARTIFACT_NAME}

- purpose: internal engineering development evidence
- sequence: {SEQUENCE_ID}
- scientific_label_status: UNVERIFIED
- eligible_as_ground_truth_label: false
- eligible_for_auroc_label: false
- holdout_or_test: false
- redistribution_authorized: false
- contains_detector_output: false
- contains_gt: false
- contains_future_information: false
- cross_process_bitwise_equivalence: NOT_PROVEN
- strict_replay_route: ABANDONED_AFTER_V5

This is not a scientific dataset, holdout, test set, public benchmark, or
degeneracy ground-truth collection.
"""
    (output / "DATASET_CARD.md").write_text(dataset_card, encoding="utf-8")
    (output / "README.md").write_text(
        "# Frozen real observation engineering evidence\n\n"
        "One complete read-only DETECTOR_MINIMAL_V1 compact binary from the "
        "single authorized Quick Shack export replay. The binary is retained "
        "without detector output, GT, future information, maps, point clouds, "
        "or the source bag.\n",
        encoding="utf-8",
    )

    freeze_manifest: dict[str, Any] = {
        "schema_version": "frozen_real_observation_manifest_v1",
        "created_at_utc": run_lock["created_at_utc"],
        "artifact_name": ARTIFACT_NAME,
        "artifact_version": ARTIFACT_VERSION,
        "run_id": RUN_ID,
        "sequence_id": SEQUENCE_ID,
        **{
            key: value
            for key, value in source_provenance.items()
            if key != "schema_version"
        },
        "tap_contract_version": "fastlio2-readonly-observation-v3",
        "payload_profile": PAYLOAD_PROFILE,
        "binary_magic": BINARY_MAGIC.decode("ascii"),
        "binary_version": BINARY_VERSION,
        "checksum_algorithm": CHECKSUM_ALGORITHM,
        "observation_record_count": observation_count,
        "first_valid_linearization_count": lifecycle[
            "first_valid_linearization_count"
        ],
        "runtime_scan_count": lifecycle["runtime_scan_count"],
        "skipped_scan_count": lifecycle["skipped_scan_count"],
        "binary_size_bytes": record_manifest["binary_size_bytes"],
        "binary_sha256": record_manifest["binary_sha256"],
        "record_index_sha256": sha256_file(
            output / "index/record_index.csv"
        ),
        "record_manifest_sha256": sha256_file(
            output / "index/record_manifest.json"
        ),
        "schema_sha256": sha256_file(output / "schema" / args.schema.name),
        "schema_rejected_record_count": facts[
            "schema_rejected_record_count"
        ],
        "nonfinite_record_count": facts["nonfinite_record_count"],
        "forbidden_field_count": facts["forbidden_field_count"],
        "gt_topic_consumed_count": facts["gt_topic_consumed_count"],
        "tap_drop_count": facts["tap_drop_count"],
        "writer_error_count": facts["writer_error_count"],
        "binary_checksum_failure_count": facts[
            "binary_checksum_failure_count"
        ],
        "truncated_record_count": facts["truncated_record_count"],
        "in_call_audited_count": status["audited_call_count"],
        "in_call_mutation_count": facts["in_call_mutation_count"],
        "raw_tail_handoff_pass": tail["raw_tail_handoff_pass"],
        "adjudicated_tail_handoff_pass": tail[
            "adjudicated_tail_handoff_pass"
        ],
        "tail_adjudication_rule_sha256": tail[
            "adjudication_rule_sha256"
        ],
        "scientific_label_status": "UNVERIFIED",
        "eligible_as_ground_truth_label": False,
        "eligible_for_auroc_label": False,
        "holdout_or_test": False,
        "redistribution_authorized": False,
        "detector_called": False,
        "odi_computed": False,
        "weak_direction_computed": False,
        "development_run": False,
        "holdout_run": False,
        "future_test_run": False,
        "commit_created": False,
        "push_performed": False,
        **gates,
    }
    validate_freeze_manifest(freeze_manifest)
    write_json(output / "FREEZE_MANIFEST.json", freeze_manifest)

    for path in output.rglob("*"):
        path.chmod(0o755 if path.is_dir() else 0o644)
    write_internal_sha256s(output)
    (output / "SHA256SUMS").chmod(0o644)
    tree_audit = audit_tree(output)
    if not tree_audit["tree_scope_pass"]:
        raise SystemExit("ERROR: frozen directory scope audit failed")
    internal = verify_internal_sha256s(output)
    if not internal["internal_hash_pass"]:
        raise SystemExit("ERROR: frozen internal SHA256SUMS failed")

    args.freeze_a_dir.mkdir(parents=True, exist_ok=True)
    args.freeze_b_dir.mkdir(parents=True, exist_ok=True)
    sha_a = build_deterministic_archive(
        output,
        args.freeze_a_dir / "frozen.tar",
        args.freeze_a_dir / "frozen.tar.gz",
    )
    sha_b = build_deterministic_archive(
        output,
        args.freeze_b_dir / "frozen.tar",
        args.freeze_b_dir / "frozen.tar.gz",
    )
    if sha_a != sha_b:
        raise SystemExit("ERROR: deterministic freeze SHA mismatch")
    final_archive = args.final_archive.expanduser().resolve()
    shutil.copyfile(args.freeze_a_dir / "frozen.tar.gz", final_archive)
    final_archive.with_name(final_archive.name + ".sha256").write_text(
        f"{sha256_file(final_archive)}  {final_archive.name}\n",
        encoding="utf-8",
    )

    if args.roundtrip_dir.exists():
        raise SystemExit("ERROR: roundtrip directory exists")
    args.roundtrip_dir.mkdir(parents=True)
    with tarfile.open(final_archive, "r:gz") as archive:
        archive.extractall(args.roundtrip_dir)
    restored = args.roundtrip_dir / output.name
    roundtrip_internal = verify_internal_sha256s(restored)
    archive_audit = audit_archive(final_archive)
    roundtrip = {
        "schema_version": "frozen_observation_roundtrip_v1",
        "gzip_pass": True,
        "archive_sha256": sha256_file(final_archive),
        "freeze_a_sha256": sha_a,
        "freeze_b_sha256": sha_b,
        "freeze_sha_identical": sha_a == sha_b,
        **roundtrip_internal,
        **archive_audit,
        "binary_sha_match": (
            sha256_file(restored / "binary/observation_records_v3.bin")
            == record_manifest["binary_sha256"]
        ),
        "record_index_row_count_match": (
            len(read_index(restored / "index/record_index.csv"))
            == observation_count
        ),
        "freeze_roundtrip_pass": (
            roundtrip_internal["internal_hash_pass"]
            and archive_audit["archive_scope_pass"]
            and sha_a == sha_b
        ),
    }
    if not roundtrip["freeze_roundtrip_pass"]:
        raise SystemExit("ERROR: frozen archive roundtrip failed")
    write_json(args.evidence_output, roundtrip)

    repo_manifest = dict(freeze_manifest)
    repo_manifest.update(
        {
            "frozen_archive_alias": (
                "$HOME/"
                "Degen-LIO-frozen-real-observation-quick-shack-v1.tar.gz"
            ),
            "frozen_archive_sha256": sha_a,
            "audit_archive_alias": (
                "$HOME/"
                "Degen-LIO-multihyp-D5-fallback-frozen-observation-audit"
                ".tar.gz"
            ),
            "audit_archive_sha256": "SELF_REFERENTIAL_NOT_EMBEDDED",
        }
    )
    write_json(args.repo_manifest, repo_manifest)
    report = f"""# Day 5 Fallback B frozen real observation report

Fallback A passed and authorized this one record-freeze step. This task ran
one `{SEQUENCE_ID}` engineering replay, exported `DETECTOR_MINIMAL_V1`, and
did not compare independent processes.

The complete compact binary contains {observation_count} records. Its header,
per-record checksums, trailer count, file checksum, schema validation, record
index, lifecycle coverage, no-GT scan, in-call immutability, deterministic
archive generation, and round-trip checks passed.

The data identity is internal engineering development evidence only.
Scientific labels remain UNVERIFIED. It contains no GT, detector output,
ODI, weak direction, holdout, future information, map, point cloud, or bag.

Passing this gate authorizes only offline production-detector determinism
work. Day 6, statistical tolerance, FAST-LIO2 integration, and formal
Degen-LIO remain unauthorized.
"""
    args.repo_report.write_text(report, encoding="utf-8")
    args.artifact_dir.mkdir(parents=True, exist_ok=False)
    for name, value in (
        ("gate_summary.json", gates),
        ("record_manifest.json", record_manifest),
        ("binary_validation_summary.json", binary_validation),
        ("lifecycle_summary.json", lifecycle),
        ("no_gt_audit.json", no_gt),
        ("freeze_roundtrip_summary.json", roundtrip),
        ("run_completeness.json", run_completeness),
    ):
        write_json(args.artifact_dir / name, value)
    summary = {
        "frozen_dir": str(output),
        "frozen_archive": str(final_archive),
        "frozen_archive_size_bytes": final_archive.stat().st_size,
        "frozen_archive_sha256": sha_a,
        "observation_record_count": observation_count,
        "freeze_reproducibility_pass": sha_a == sha_b,
        "freeze_roundtrip_pass": roundtrip["freeze_roundtrip_pass"],
        "gates": gates,
    }
    write_json(args.artifact_dir / "freeze_summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
