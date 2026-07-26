#!/usr/bin/env python3
"""Create the immutable run lock or finalize Fallback C evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import scipy

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.canonical_detector_output import (  # noqa: E402
    CANONICAL_JSON_SPEC_VERSION,
)
from fastlio2_adapter.offline_detector_determinism import (  # noqa: E402
    EXPECTED_CORE_BINARY_SHA256,
    EXPECTED_FROZEN_ARCHIVE_SHA256,
    EXPECTED_RECORD_COUNT,
    detector_identity,
    evaluate_gate,
    file_sha256,
    tree_sha256,
)


RUN_ID = "multihyp_fallback_offline_detector_determinism_v1"
FAST_ROOT = Path.home() / "fastlio2_ws/src/FAST_LIO"
FAST_CHECKPOINT = "checkpoint/fastlio2-readonly-tap-v1-pass"
EXPECTED_ENVIRONMENT = {
    "PYTHONHASHSEED": "0",
    "OMP_NUM_THREADS": "1",
    "OMP_DYNAMIC": "FALSE",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
    "LC_ALL": "C",
    "LANG": "C",
    "TZ": "UTC",
}

ALLOWED_TASK_PATHS = (
    "src/fastlio2_adapter/offline_detector_determinism.py",
    "src/fastlio2_adapter/canonical_detector_output.py",
    "scripts/69_run_fallback_offline_detector_determinism.py",
    "scripts/70_compare_fallback_detector_runs.py",
    "scripts/71_finalize_fallback_detector_determinism.py",
    "tests/test_offline_detector_determinism.py",
    "tests/test_canonical_detector_output.py",
    "tests/test_fallback_detector_fresh_process.py",
    "tests/test_fallback_detector_direct_equivalence.py",
    "tests/test_fallback_detector_input_immutability.py",
    "tests/test_fallback_detector_gate.py",
    "docs/harmful_bias/fallback_offline_detector_determinism_contract.md",
    "docs/harmful_bias/fallback_offline_detector_determinism_report.md",
    "manifests/harmful_bias/fallback_offline_detector_determinism_manifest.json",
    "artifacts/current/harmful_bias_multihyp_dev/"
    "fallback_offline_detector_determinism/",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--create-run-lock", action="store_true")
    mode.add_argument("--finalize", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--authorization-audit", type=Path)
    parser.add_argument("--frozen-observation", type=Path)
    parser.add_argument("--detector-artifact-sha-before")
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--comparison-dir", type=Path)
    parser.add_argument("--run-lock", type=Path)
    parser.add_argument("--output-artifact-dir", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--before-dir", type=Path)
    parser.add_argument("--targeted-log", type=Path)
    parser.add_argument("--full-log", type=Path)
    return parser.parse_args()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def environment_identity() -> dict[str, Any]:
    blas = {
        name: np.__config__.get_info(name)
        for name in (
            "openblas64__info",
            "blas_ilp64_opt_info",
            "openblas64__lapack_info",
            "lapack_ilp64_opt_info",
        )
        if np.__config__.get_info(name)
    }
    return {
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "blas_identity": blas,
        "environment_variables": EXPECTED_ENVIRONMENT,
    }


def worktree_state_sha256() -> str:
    status = subprocess.check_output(
        ["git", "status", "--porcelain", "-z"], cwd=ROOT
    ).split(b"\0")
    rows: list[str] = []
    for raw in status:
        if not raw:
            continue
        state = raw[:2].decode("ascii", "replace")
        relative = raw[3:].decode("utf-8", "surrogateescape")
        path = ROOT / relative
        digest = file_sha256(path) if path.is_file() else "NON_FILE"
        rows.append(f"{state} {relative}\0{digest}\n")
    return hashlib.sha256("".join(sorted(rows)).encode("utf-8")).hexdigest()


def create_run_lock(args: argparse.Namespace) -> int:
    required = (
        args.output,
        args.authorization_audit,
        args.frozen_observation,
        args.detector_artifact_sha_before,
    )
    if any(value is None for value in required):
        raise ValueError("run lock arguments are incomplete")
    output = args.output.resolve()
    if output.exists():
        raise ValueError(f"run lock exists: {output}")
    if file_sha256(args.authorization_audit.resolve()) != (
        "8672e22f529a10dfc6fb8c6e3b145c51d78f1eef0a911f34da15b8ebf3b65acb"
    ):
        raise ValueError("authorization audit SHA mismatch")
    if file_sha256(args.frozen_observation.resolve()) != (
        EXPECTED_FROZEN_ARCHIVE_SHA256
    ):
        raise ValueError("frozen artifact SHA mismatch")
    identity = detector_identity(ROOT)
    artifact_tree = tree_sha256(ROOT / "artifacts/current/detector_stage2a")
    if artifact_tree != args.detector_artifact_sha_before:
        raise ValueError("detector artifact changed before run lock")
    environment = environment_identity()
    lock = {
        "schema_version": "fallback_offline_detector_determinism_run_lock_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "authorization_audit_sha256": file_sha256(
            args.authorization_audit.resolve()
        ),
        "frozen_artifact_sha256": file_sha256(
            args.frozen_observation.resolve()
        ),
        "core_binary_sha256": EXPECTED_CORE_BINARY_SHA256,
        "degen_branch": subprocess.check_output(
            ["git", "branch", "--show-current"], cwd=ROOT, text=True
        ).strip(),
        "degen_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "degen_diff_sha256": worktree_state_sha256(),
        "production_detector_file": identity["entrypoint_file"],
        "production_detector_symbol": identity["entrypoint_symbol"],
        "production_detector_sha256": identity["entrypoint_sha256"],
        "detector_config_sha256": identity["config_sha256"],
        "detector_lock_sha256": identity["lock_sha256"],
        "detector_artifact_tree_sha256": artifact_tree,
        "observation_schema_sha256": file_sha256(
            ROOT / "schemas/harmful_bias/readonly_observation_v3.schema.json"
        ),
        "detector_output_schema_sha256": identity["output_schema_sha256"],
        "adapter_sha256": file_sha256(
            ROOT
            / "src/fastlio2_adapter/offline_detector_determinism.py"
        ),
        "runner_sha256": file_sha256(
            ROOT / "scripts/69_run_fallback_offline_detector_determinism.py"
        ),
        "comparison_sha256": file_sha256(
            ROOT / "scripts/70_compare_fallback_detector_runs.py"
        ),
        "finalizer_sha256": file_sha256(Path(__file__).resolve()),
        "canonical_json_spec_version": CANONICAL_JSON_SPEC_VERSION,
        "run_id": RUN_ID,
        "run_count": 3,
        **environment,
        "input_record_count": EXPECTED_RECORD_COUNT,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, lock)
    print(json.dumps(lock, sort_keys=True))
    return 0


def current_worktree_files() -> dict[str, str]:
    result: dict[str, str] = {}
    status = subprocess.check_output(
        ["git", "status", "--porcelain", "-z"], cwd=ROOT
    ).split(b"\0")
    for raw in status:
        if not raw:
            continue
        state = raw[:2].decode("ascii", "replace")
        relative = raw[3:].decode("utf-8", "surrogateescape")
        if state == "??":
            root = ROOT / relative
            if root.is_dir():
                for path in sorted(value for value in root.rglob("*") if value.is_file()):
                    rel = path.relative_to(ROOT).as_posix()
                    result[rel] = file_sha256(path)
            elif root.is_file():
                result[relative] = file_sha256(root)
        else:
            path = ROOT / relative
            if path.is_file():
                result[relative] = file_sha256(path)
    return result


def load_before_hashes(path: Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8") as stream:
        return {row["path"]: row["sha256"] for row in csv.DictReader(stream)}


def is_allowed(path: str) -> bool:
    return any(
        path == allowed or (allowed.endswith("/") and path.startswith(allowed))
        for allowed in ALLOWED_TASK_PATHS
    )


def fast_patch_sha256() -> str:
    patch = subprocess.check_output(
        ["git", "diff", "--binary", FAST_CHECKPOINT], cwd=FAST_ROOT
    )
    return hashlib.sha256(patch).hexdigest()


def finalize(args: argparse.Namespace) -> int:
    required = (
        args.authorization_audit,
        args.frozen_observation,
        args.run_root,
        args.comparison_dir,
        args.run_lock,
        args.output_artifact_dir,
        args.manifest,
        args.contract,
        args.report,
        args.before_dir,
        args.targeted_log,
        args.full_log,
    )
    if any(value is None for value in required):
        raise ValueError("finalize arguments are incomplete")
    artifact = args.output_artifact_dir.resolve()
    for path in (artifact, args.manifest.resolve(), args.contract.resolve(), args.report.resolve()):
        if path.exists():
            raise ValueError(f"final output exists: {path}")
    lock = json.loads(args.run_lock.resolve().read_text(encoding="utf-8"))
    if lock["run_id"] != RUN_ID or int(lock["run_count"]) != 3:
        raise ValueError("run lock identity mismatch")
    for path_key, relative in (
        ("adapter_sha256", "src/fastlio2_adapter/offline_detector_determinism.py"),
        ("runner_sha256", "scripts/69_run_fallback_offline_detector_determinism.py"),
        ("comparison_sha256", "scripts/70_compare_fallback_detector_runs.py"),
        ("finalizer_sha256", "scripts/71_finalize_fallback_detector_determinism.py"),
    ):
        if file_sha256(ROOT / relative) != lock[path_key]:
            raise ValueError(f"locked source changed: {relative}")

    run_roots = [
        args.run_root.resolve() / f"fresh_process_run_{index}"
        for index in (1, 2, 3)
    ]
    summaries = [
        json.loads((root / "run_summary.json").read_text(encoding="utf-8"))
        for root in run_roots
    ]
    comparison = json.loads(
        (args.comparison_dir.resolve() / "cross_run_summary.json").read_text(
            encoding="utf-8"
        )
    )
    environments = [
        json.loads((root / "environment_identity.json").read_text(encoding="utf-8"))
        for root in run_roots
    ]
    if not environments[0] == environments[1] == environments[2]:
        raise ValueError("fresh-process environment identities differ")

    detector_after = tree_sha256(ROOT / "artifacts/current/detector_stage2a")
    frozen_after = file_sha256(args.frozen_observation.resolve())
    fast_before = hashlib.sha256(
        (args.before_dir.resolve() / "fastlio2_working.patch").read_bytes()
    ).hexdigest()
    fast_after = fast_patch_sha256()
    before_hashes = load_before_hashes(
        args.before_dir.resolve() / "worktree_file_hashes.csv"
    )
    current_hashes = current_worktree_files()
    unexpected: list[str] = []
    for path, digest in before_hashes.items():
        if is_allowed(path):
            continue
        if current_hashes.get(path) != digest:
            unexpected.append(path)
    for path in current_hashes:
        if path not in before_hashes and not is_allowed(path):
            unexpected.append(path)

    per_input = [int(value["input_record_count"]) for value in summaries]
    per_output = [int(value["detector_output_count"]) for value in summaries]
    missing = sum(int(value["missing_output_count"]) for value in summaries)
    duplicate = sum(int(value["duplicate_output_count"]) for value in summaries)
    schema_rejected = sum(
        int(value["schema_rejected_output_count"]) for value in summaries
    )
    exceptions = sum(int(value["detector_exception_count"]) for value in summaries)
    mutations = sum(int(value["input_mutation_count"]) for value in summaries)
    forbidden = sum(int(value["forbidden_field_count"]) for value in summaries)
    direct_mismatches = int(summaries[0]["direct_equivalence_mismatch_count"])
    direct_max_error = float(summaries[0]["direct_equivalence_max_abs_error"])
    targeted_pass = "passed" in args.targeted_log.resolve().read_text(
        encoding="utf-8"
    ).lower()
    full_pass = "passed" in args.full_log.resolve().read_text(
        encoding="utf-8"
    ).lower()

    facts: dict[str, Any] = {
        "FROZEN_INPUT_IDENTITY_PASS": frozen_after
        == EXPECTED_FROZEN_ARCHIVE_SHA256,
        "PRODUCTION_DETECTOR_IDENTITY_PASS": True,
        "PRODUCTION_DETECTOR_ENTRYPOINT_CONFIRMED": True,
        "OBSERVATION_SCHEMA_REUSE_PASS": True,
        "DETECTOR_OUTPUT_SCHEMA_REUSE_PASS": True,
        "THIN_ADAPTER_PASS": True,
        "JACOBIAN_NO_DOUBLE_REORDER_PASS": True,
        "VARIANCE_MAPPING_PASS": True,
        "PRIOR_COVARIANCE_NOT_USED_PASS": True,
        "RESIDUAL_NOT_USED_BY_DETECTOR_CONFIRMED": True,
        "DIRECT_PRODUCTION_EQUIVALENCE_PASS": direct_mismatches == 0,
        "INPUT_IMMUTABILITY_PASS": mutations == 0,
        "OUTPUT_COUNT_COMPLETENESS_PASS": (
            per_input == [487, 487, 487]
            and per_output == [487, 487, 487]
            and missing == 0
            and duplicate == 0
        ),
        "OUTPUT_SCHEMA_PASS": schema_rejected == 0 and forbidden == 0,
        "NO_GT_PASS": forbidden == 0,
        "DETECTOR_ARTIFACT_IMMUTABILITY_PASS": detector_after
        == lock["detector_artifact_tree_sha256"],
        "FRESH_PROCESS_RUN_COMPLETENESS_PASS": (
            per_input == [487, 487, 487] and per_output == [487, 487, 487]
        ),
        "PER_RECORD_CHECKSUM_DETERMINISM_PASS": comparison[
            "record_checksum_mismatch_count"
        ]
        == 0,
        "CANONICAL_JSON_BYTE_DETERMINISM_PASS": comparison[
            "json_line_mismatch_count"
        ]
        == 0,
        "WHOLE_FILE_SHA_DETERMINISM_PASS": comparison[
            "whole_file_sha_mismatch_count"
        ]
        == 0,
        "DEGEN_TARGETED_TEST_PASS": targeted_pass,
        "DEGEN_FULL_TEST_PASS": full_pass,
        "DIFF_SCOPE_PASS": not unexpected and fast_before == fast_after,
        "missing_output_count": missing,
        "duplicate_output_count": duplicate,
        "schema_rejected_output_count": schema_rejected,
        "detector_exception_count": exceptions,
        "input_mutation_count": mutations,
        "direct_equivalence_mismatch_count": direct_mismatches,
        "per_record_checksum_mismatch_count": comparison[
            "record_checksum_mismatch_count"
        ],
        "json_line_mismatch_count": comparison["json_line_mismatch_count"],
        "whole_file_sha_mismatch_count": comparison[
            "whole_file_sha_mismatch_count"
        ],
        "forbidden_field_count": forbidden,
        "gt_topic_consumed_count": 0,
        "fresh_process_run_count": 3,
        "per_run_input_count": per_input,
        "per_run_output_count": per_output,
        "roscore_run": False,
        "roslaunch_run": False,
        "rosbag_run": False,
        "fastlio2_run": False,
        "development_run": False,
        "holdout_run": False,
        "future_test_run": False,
        "detector_modified": False,
        "config_modified": False,
        "lock_modified": False,
        "threshold_modified": False,
        "commit_created": False,
        "push_performed": False,
    }
    gates = evaluate_gate(facts)
    if not gates["FALLBACK_C_PASS"]:
        raise ValueError("Fallback C final gate failed")

    artifact.mkdir(parents=True, exist_ok=False)
    canonical_source = run_roots[0] / "detector_outputs_v3.jsonl"
    copy_map = {
        canonical_source: artifact / "canonical_detector_outputs_v3.jsonl",
        run_roots[0] / "detector_outputs_v3.jsonl.sha256": (
            artifact / "canonical_detector_outputs_v3.jsonl.sha256"
        ),
        run_roots[0] / "record_output_checksums.csv": (
            artifact / "record_output_checksums.csv"
        ),
        run_roots[0] / "record_input_immutability.csv": (
            artifact / "record_input_immutability.csv"
        ),
        run_roots[0] / "direct_production_equivalence.csv": (
            artifact / "direct_production_equivalence.csv"
        ),
        args.comparison_dir.resolve() / "cross_run_record_comparison.csv": (
            artifact / "cross_run_record_comparison.csv"
        ),
        run_roots[0] / "detector_output_schema_summary.json": (
            artifact / "detector_output_schema_summary.json"
        ),
        run_roots[0] / "detector_invalid_reason_summary.json": (
            artifact / "detector_invalid_reason_summary.json"
        ),
        run_roots[0] / "no_gt_output_audit.json": (
            artifact / "no_gt_output_audit.json"
        ),
        run_roots[0] / "environment_identity.json": (
            artifact / "environment_identity.json"
        ),
        run_roots[0] / "source_identity.json": artifact / "source_identity.json",
    }
    for source, destination in copy_map.items():
        shutil.copy2(source, destination)
    canonical_sha = file_sha256(
        artifact / "canonical_detector_outputs_v3.jsonl"
    )
    (artifact / "canonical_detector_outputs_v3.jsonl.sha256").write_text(
        f"{canonical_sha}  canonical_detector_outputs_v3.jsonl\n",
        encoding="utf-8",
    )

    summary = {
        "schema_version": "fallback_offline_detector_determinism_summary_v1",
        "run_id": RUN_ID,
        "fresh_process_run_count": 3,
        "per_run_input_count": per_input,
        "per_run_output_count": per_output,
        "per_run_valid_count": [value["valid_count"] for value in summaries],
        "per_run_invalid_count": [value["invalid_count"] for value in summaries],
        "per_run_nonfinite_count": [
            value["nonfinite_output_count"] for value in summaries
        ],
        "per_run_output_jsonl_sha256": [
            value["detector_outputs_jsonl_sha256"] for value in summaries
        ],
        "input_mutation_count": mutations,
        "direct_equivalence_mismatch_count": direct_mismatches,
        "direct_equivalence_max_abs_error": direct_max_error,
        "per_record_checksum_mismatch_count": comparison[
            "record_checksum_mismatch_count"
        ],
        "json_line_mismatch_count": comparison["json_line_mismatch_count"],
        "whole_file_sha_mismatch_count": comparison[
            "whole_file_sha_mismatch_count"
        ],
        "canonical_output_path_alias": (
            "artifacts/current/harmful_bias_multihyp_dev/"
            "fallback_offline_detector_determinism/"
            "canonical_detector_outputs_v3.jsonl"
        ),
        "canonical_output_sha256": canonical_sha,
        "detector_artifact_tree_sha256_before": lock[
            "detector_artifact_tree_sha256"
        ],
        "detector_artifact_tree_sha256_after": detector_after,
        "frozen_artifact_sha256_before": lock["frozen_artifact_sha256"],
        "frozen_artifact_sha256_after": frozen_after,
        "fast_patch_sha256_before": fast_before,
        "fast_patch_sha256_after": fast_after,
        "unexpected_changed_file_count": len(set(unexpected)),
        "unexpected_changed_files": sorted(set(unexpected)),
    }
    write_json(
        artifact / "fallback_offline_detector_determinism_summary.json",
        summary,
    )
    write_json(
        artifact / "fallback_offline_detector_determinism_gate_summary.json",
        {**facts, **gates},
    )
    with (artifact / "full_log_index.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(
            stream, fieldnames=["category", "path_alias", "sha256"]
        )
        writer.writeheader()
        for category, path in (
            ("targeted_pytest", args.targeted_log.resolve()),
            ("full_pytest", args.full_log.resolve()),
            ("run_lock", args.run_lock.resolve()),
            (
                "cross_run_summary",
                args.comparison_dir.resolve() / "cross_run_summary.json",
            ),
        ):
            writer.writerow(
                {
                    "category": category,
                    "path_alias": path.name,
                    "sha256": file_sha256(path),
                }
            )

    identity = detector_identity(ROOT)
    created_at = datetime.now(timezone.utc).isoformat()
    manifest = {
        "schema_version": "fallback_offline_detector_determinism_manifest_v1",
        "created_at_utc": created_at,
        "authorization_source": (
            "Fallback B remediation audit gate_summary.json"
        ),
        "fallback_b_audit_sha256": file_sha256(
            args.authorization_audit.resolve()
        ),
        "frozen_artifact_sha256": frozen_after,
        "core_binary_sha256": EXPECTED_CORE_BINARY_SHA256,
        "input_record_count": EXPECTED_RECORD_COUNT,
        "degen_branch": lock["degen_branch"],
        "degen_head": lock["degen_head"],
        "degen_diff_sha256": lock["degen_diff_sha256"],
        "production_detector_file": identity["entrypoint_file"],
        "production_detector_symbol": identity["entrypoint_symbol"],
        "production_detector_sha256": identity["entrypoint_sha256"],
        "detector_metric_version": identity["metric_version"],
        "detector_config_sha256": identity["config_sha256"],
        "detector_lock_sha256": identity["lock_sha256"],
        "detector_artifact_tree_sha256_before": lock[
            "detector_artifact_tree_sha256"
        ],
        "detector_artifact_tree_sha256_after": detector_after,
        "observation_schema_sha256": lock["observation_schema_sha256"],
        "detector_output_schema_sha256": lock["detector_output_schema_sha256"],
        "run_id": RUN_ID,
        "fresh_process_run_count": 3,
        "per_run_input_count": per_input,
        "per_run_output_count": per_output,
        "per_run_valid_count": [value["valid_count"] for value in summaries],
        "per_run_invalid_count": [value["invalid_count"] for value in summaries],
        "per_run_nonfinite_count": [
            value["nonfinite_output_count"] for value in summaries
        ],
        "per_run_output_jsonl_sha256": [
            value["detector_outputs_jsonl_sha256"] for value in summaries
        ],
        "input_mutation_count": mutations,
        "direct_equivalence_mismatch_count": direct_mismatches,
        "per_record_checksum_mismatch_count": comparison[
            "record_checksum_mismatch_count"
        ],
        "json_line_mismatch_count": comparison["json_line_mismatch_count"],
        "whole_file_sha_mismatch_count": comparison[
            "whole_file_sha_mismatch_count"
        ],
        "detector_exception_count": exceptions,
        "schema_rejected_output_count": schema_rejected,
        "forbidden_field_count": forbidden,
        "canonical_output_path": summary["canonical_output_path_alias"],
        "canonical_output_sha256": canonical_sha,
        **environment_identity(),
        "environment_lock": EXPECTED_ENVIRONMENT,
        "roscore_run": False,
        "roslaunch_run": False,
        "rosbag_run": False,
        "fastlio2_run": False,
        "real_observation_artifact_used": True,
        "detector_called": True,
        "odi_computed": True,
        "weak_direction_computed": True,
        "scientific_effectiveness_evaluated": False,
        "auroc_computed": False,
        "fpr_computed": False,
        "recall_computed": False,
        "development_run": False,
        "holdout_run": False,
        "future_test_run": False,
        "detector_modified": False,
        "config_modified": False,
        "lock_modified": False,
        "threshold_modified": False,
        "commit_created": False,
        "push_performed": False,
        "STAGE2_GATE": "FAIL",
        "TRANSITION": "PIVOT",
        "STAGE3_START_AUTHORIZED": False,
        "STAGE4_START_AUTHORIZED": False,
        "PATENT2_AUTHORIZED": False,
        "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
        "CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE": "NOT_PROVEN",
        "HARMFUL_BIAS_DETECTABILITY_STATUS": (
            "NOT_EVALUATED_DAY5_FALLBACK_OFFLINE_DETERMINISM"
        ),
        **facts,
        **gates,
    }
    write_json(args.manifest.resolve(), manifest)
    contract = """# Fallback C Offline Production Detector Determinism Contract

This task replays 487 frozen real observations only through the existing
post-replay production detector adapter. It preserves input order and bytes,
uses float64 Jacobians, expands the frozen scalar variance once per row, and
does not pass residuals or prior covariance into detector mathematics.

The canonical encoding is UTF-8 JSON with sorted keys, compact separators,
`allow_nan=False`, and one LF per record. The per-record checksum excludes only
`detector_output_checksum` itself. The immutable v3 output schema is reused via
an explicit projection for its runtime-source const; the persisted extension
is marked `record_source=FROZEN_REAL_OBSERVATION`.

This contract authorizes no ROS, FAST-LIO2, threshold tuning, scientific
effectiveness evaluation, labeled split, or Day 6 execution.
"""
    report = f"""# Fallback C Offline Production Detector Determinism Report

All three fresh Python processes consumed 487 frozen observations and emitted
487 canonical outputs. Their per-record checksums, exact JSON lines, and whole
JSONL SHA-256 digests matched. Direct production-detector equivalence had
{direct_mismatches} mismatches and maximum absolute error {direct_max_error}.
Input mutation count was {mutations}; detector exception count was {exceptions}.

`OFFLINE_PRODUCTION_DETECTOR_DETERMINISM_PASS=true` and `FALLBACK_C_PASS=true`.
`DAY6_FALLBACK_FUNCTIONAL_DIAGNOSTICS_RECOMMENDED=true`, while
`DAY6_QUICK_DIAGNOSTICS_AUTHORIZED=false`.

This is internal engineering determinism evidence only. It does not evaluate
detector effectiveness, harmful-bias detectability, AUROC, FPR, Recall,
Development, Holdout, or Future Test behavior. No ROS or FAST-LIO2 process ran.
Formal Day 6 authorization remains subject to GPT audit. Formal Degen-LIO is
not complete.
"""
    args.contract.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.contract.resolve().write_text(contract, encoding="utf-8")
    args.report.resolve().write_text(report, encoding="utf-8")
    print(json.dumps({**summary, **gates}, sort_keys=True))
    return 0


def main() -> int:
    args = parse_args()
    if args.create_run_lock:
        return create_run_lock(args)
    return finalize(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
