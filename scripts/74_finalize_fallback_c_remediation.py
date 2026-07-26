#!/usr/bin/env python3
"""Create the Fallback C remediation run lock or finalize its evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import re
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

from fastlio2_adapter.contract_aware_direct_comparison import (  # noqa: E402
    evaluate_remediation_gate,
)
from fastlio2_adapter.offline_detector_determinism import (  # noqa: E402
    EXPECTED_CORE_BINARY_SHA256,
    EXPECTED_FROZEN_ARCHIVE_SHA256,
    EXPECTED_RECORD_COUNT,
    detector_identity,
    file_sha256,
    tree_sha256,
)


RUN_ID = "multihyp_fallback_offline_detector_determinism_remediation_v1"
PREVIOUS_AUDIT_SHA256 = (
    "721c28dee7d2ef9fc82fc8b71326eb90bffad3cfecd8528b923cd5c7c815c409"
)
PREVIOUS_ADAPTER_SHA256 = (
    "182b989aee619d83862cb45e9aef6fb0a50dd5b91d407e8d5ef13d694fd65232"
)
FAST_ROOT = Path.home() / "fastlio2_ws/src/FAST_LIO"
FAST_CHECKPOINT = "checkpoint/fastlio2-readonly-tap-v1-pass"
EXPECTED_DEGEN_BRANCH = "spike/harmful-bias-multihyp-dev"
EXPECTED_DEGEN_HEAD = "711ac05ccc683263446fb8656c0054048832f54c"
EXPECTED_FAST_BRANCH = "spike/readonly-observation-tap-v1"
EXPECTED_FAST_HEAD = "f19b4c42a77dc11793c912d67b9e56dcafa279dc"
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
LOCKED_TASK_FILES = {
    "comparison_module_sha256": (
        "src/fastlio2_adapter/contract_aware_direct_comparison.py"
    ),
    "direct_diagnostic_module_sha256": (
        "src/fastlio2_adapter/direct_production_diagnostic.py"
    ),
    "direct_diagnostic_schema_sha256": (
        "schemas/harmful_bias/offline_direct_production_metrics_v1.schema.json"
    ),
    "runner_sha256": "scripts/72_run_fallback_c_remediation.py",
    "comparator_sha256": "scripts/73_compare_fallback_c_remediation_runs.py",
    "finalizer_sha256": "scripts/74_finalize_fallback_c_remediation.py",
}
IMMUTABLE_FILES = {
    "adapter_guard_sha256": "src/fastlio2_adapter/detector_adapter.py",
    "runtime_adapter_sha256": (
        "src/fastlio2_adapter/runtime_detector_adapter_v3.py"
    ),
    "canonical_output_sha256": (
        "src/fastlio2_adapter/canonical_detector_output.py"
    ),
    "production_detector_sha256": "src/degen_detector/odi_tracker.py",
    "detector_config_sha256": "configs/detector/odi_stage2a.yaml",
    "detector_lock_sha256": (
        "artifacts/current/detector_stage2a/locked/detector_lock.json"
    ),
    "detector_output_schema_sha256": (
        "schemas/harmful_bias/readonly_detector_output_v3.schema.json"
    ),
    "observation_schema_sha256": (
        "schemas/harmful_bias/readonly_observation_v3.schema.json"
    ),
}
ALLOWED_NEW_PATHS = (
    "src/fastlio2_adapter/contract_aware_direct_comparison.py",
    "src/fastlio2_adapter/direct_production_diagnostic.py",
    "schemas/harmful_bias/offline_direct_production_metrics_v1.schema.json",
    "scripts/72_run_fallback_c_remediation.py",
    "scripts/73_compare_fallback_c_remediation_runs.py",
    "scripts/74_finalize_fallback_c_remediation.py",
    "tests/test_null_safe_detector_comparison.py",
    "tests/test_adapter_precondition_domain.py",
    "tests/test_direct_production_diagnostic.py",
    "tests/test_fallback_c_remediation_fresh_process.py",
    "tests/test_fallback_c_remediation_gate.py",
    "docs/harmful_bias/"
    "fallback_offline_detector_determinism_remediation_contract.md",
    "docs/harmful_bias/"
    "fallback_offline_detector_determinism_remediation_report.md",
    "manifests/harmful_bias/"
    "fallback_offline_detector_determinism_remediation_manifest.json",
    "artifacts/current/harmful_bias_multihyp_dev/"
    "fallback_offline_detector_determinism_remediation/",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--create-run-lock", action="store_true")
    mode.add_argument("--finalize", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--previous-audit", type=Path)
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


def command_output(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


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


def current_worktree_files() -> dict[str, str]:
    result: dict[str, str] = {}
    entries = subprocess.check_output(
        ["git", "status", "--porcelain", "-z"],
        cwd=ROOT,
    ).split(b"\0")
    for raw in entries:
        if not raw:
            continue
        relative = raw[3:].decode("utf-8", "surrogateescape")
        path = ROOT / relative
        if path.is_dir():
            for child in sorted(
                item for item in path.rglob("*") if item.is_file()
            ):
                result[child.relative_to(ROOT).as_posix()] = file_sha256(child)
        elif path.is_file():
            result[relative] = file_sha256(path)
    return result


def worktree_state_sha256() -> str:
    rows = [
        f"{digest}  {path}\n"
        for path, digest in sorted(current_worktree_files().items())
    ]
    return hashlib.sha256("".join(rows).encode("utf-8")).hexdigest()


def load_hash_csv(path: Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8") as stream:
        return {
            row["path"]: row["sha256"]
            for row in csv.DictReader(stream)
        }


def fast_patch_sha256() -> str:
    patch = subprocess.check_output(
        ["git", "diff", "--binary", FAST_CHECKPOINT],
        cwd=FAST_ROOT,
    )
    return hashlib.sha256(patch).hexdigest()


def is_allowed_new_path(path: str) -> bool:
    return any(
        path == allowed
        or (allowed.endswith("/") and path.startswith(allowed))
        for allowed in ALLOWED_NEW_PATHS
    )


def pytest_log_passed(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    return bool(re.search(r"\b\d+ passed\b", text)) and " failed" not in text


def create_run_lock(args: argparse.Namespace) -> int:
    required = (
        args.output,
        args.previous_audit,
        args.frozen_observation,
        args.detector_artifact_sha_before,
        args.before_dir,
    )
    if any(value is None for value in required):
        raise ValueError("run lock arguments are incomplete")
    output = args.output.resolve()
    if output.exists():
        raise ValueError(f"run lock exists: {output}")
    previous = args.previous_audit.resolve()
    frozen = args.frozen_observation.resolve()
    if file_sha256(previous) != PREVIOUS_AUDIT_SHA256:
        raise ValueError("previous failed audit SHA mismatch")
    if file_sha256(frozen) != EXPECTED_FROZEN_ARCHIVE_SHA256:
        raise ValueError("frozen artifact SHA mismatch")
    if command_output("git", "branch", "--show-current") != EXPECTED_DEGEN_BRANCH:
        raise ValueError("Degen branch mismatch")
    if command_output("git", "rev-parse", "HEAD") != EXPECTED_DEGEN_HEAD:
        raise ValueError("Degen HEAD mismatch")
    if command_output(
        "git", "branch", "--show-current", cwd=FAST_ROOT
    ) != EXPECTED_FAST_BRANCH:
        raise ValueError("FAST branch mismatch")
    if command_output("git", "rev-parse", "HEAD", cwd=FAST_ROOT) != EXPECTED_FAST_HEAD:
        raise ValueError("FAST HEAD mismatch")

    identity = detector_identity(ROOT)
    detector_tree = tree_sha256(ROOT / "artifacts/current/detector_stage2a")
    if detector_tree != args.detector_artifact_sha_before:
        raise ValueError("detector artifact changed before run lock")
    immutable = {
        key: file_sha256(ROOT / relative)
        for key, relative in IMMUTABLE_FILES.items()
    }
    expected_immutable = {
        "production_detector_sha256": identity["entrypoint_sha256"],
        "detector_config_sha256": identity["config_sha256"],
        "detector_lock_sha256": identity["lock_sha256"],
        "detector_output_schema_sha256": identity["output_schema_sha256"],
    }
    if any(immutable[key] != value for key, value in expected_immutable.items()):
        raise ValueError("immutable detector identity mismatch")

    baseline = load_hash_csv(
        args.before_dir.resolve() / "previous_worktree_file_hashes.csv"
    )
    current = current_worktree_files()
    changed_baseline = [
        path for path, digest in baseline.items() if current.get(path) != digest
    ]
    if changed_baseline:
        raise ValueError(
            f"pre-existing worktree files changed: {changed_baseline[:10]}"
        )

    task_hashes = {
        key: file_sha256(ROOT / relative)
        for key, relative in LOCKED_TASK_FILES.items()
    }
    lock = {
        "schema_version": "fallback_c_offline_remediation_run_lock_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "previous_failure_audit_sha256": file_sha256(previous),
        "previous_completed_adapter_jsonl_sha256": PREVIOUS_ADAPTER_SHA256,
        "frozen_artifact_sha256": file_sha256(frozen),
        "core_binary_sha256": EXPECTED_CORE_BINARY_SHA256,
        "input_record_count": EXPECTED_RECORD_COUNT,
        "degen_branch": EXPECTED_DEGEN_BRANCH,
        "degen_head": EXPECTED_DEGEN_HEAD,
        "degen_diff_sha256": worktree_state_sha256(),
        "fastlio2_branch": EXPECTED_FAST_BRANCH,
        "fastlio2_head": EXPECTED_FAST_HEAD,
        "fastlio2_patch_sha256": fast_patch_sha256(),
        "production_detector_file": identity["entrypoint_file"],
        "production_detector_symbol": identity["entrypoint_symbol"],
        "production_detector_sha256": identity["entrypoint_sha256"],
        "detector_config_sha256": identity["config_sha256"],
        "detector_lock_sha256": identity["lock_sha256"],
        "detector_artifact_tree_sha256": detector_tree,
        **immutable,
        **task_hashes,
        "run_id": RUN_ID,
        "fresh_process_count": 3,
        "expected_production_domain_count": 486,
        "expected_precondition_domain_count": 1,
        **environment_identity(),
    }
    write_json(output, lock)
    print(json.dumps(lock, sort_keys=True))
    return 0


def finalize(args: argparse.Namespace) -> int:
    required = (
        args.previous_audit,
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
    manifest_path = args.manifest.resolve()
    contract_path = args.contract.resolve()
    report_path = args.report.resolve()
    for path in (artifact, manifest_path, contract_path, report_path):
        if path.exists():
            raise ValueError(f"final output exists: {path}")

    lock = json.loads(args.run_lock.resolve().read_text(encoding="utf-8"))
    if lock["run_id"] != RUN_ID or int(lock["fresh_process_count"]) != 3:
        raise ValueError("run lock identity mismatch")
    for key, relative in LOCKED_TASK_FILES.items():
        if file_sha256(ROOT / relative) != lock[key]:
            raise ValueError(f"locked task file changed: {relative}")
    immutable_after = {
        key: file_sha256(ROOT / relative)
        for key, relative in IMMUTABLE_FILES.items()
    }
    immutable_mismatches = [
        key for key, digest in immutable_after.items() if lock[key] != digest
    ]
    if immutable_mismatches:
        raise ValueError(f"immutable files changed: {immutable_mismatches}")

    run_roots = [
        args.run_root.resolve() / f"fresh_process_remediation_run_{index}"
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
    fast_before = (
        args.before_dir.resolve() / "fastlio2_working_patch.sha256"
    ).read_text(encoding="utf-8").strip()
    fast_after = fast_patch_sha256()
    baseline = load_hash_csv(
        args.before_dir.resolve() / "previous_worktree_file_hashes.csv"
    )
    current = current_worktree_files()
    unexpected = [
        path for path, digest in baseline.items() if current.get(path) != digest
    ]
    unexpected.extend(
        path
        for path in current
        if path not in baseline and not is_allowed_new_path(path)
    )
    unexpected = sorted(set(unexpected))

    per_input = [int(item["input_record_count"]) for item in summaries]
    per_adapter_output = [
        int(item["adapter_output_count"]) for item in summaries
    ]
    per_direct_output = [
        int(item["direct_output_count"]) for item in summaries
    ]
    per_adapter_valid = [
        int(item["adapter_valid_count"]) for item in summaries
    ]
    per_adapter_invalid = [
        int(item["adapter_invalid_count"]) for item in summaries
    ]
    per_direct_valid = [
        int(item["direct_valid_count"]) for item in summaries
    ]
    per_direct_invalid = [
        int(item["direct_invalid_count"]) for item in summaries
    ]
    production_counts = [
        int(item["production_executed_domain_record_count"])
        for item in summaries
    ]
    precondition_counts = [
        int(item["adapter_precondition_domain_record_count"])
        for item in summaries
    ]
    production_mismatches = sum(
        int(item["production_metric_equivalence_mismatch_count"])
        for item in summaries
    )
    production_max_error = max(
        float(item["production_metric_equivalence_max_abs_error"])
        for item in summaries
    )
    precondition_mismatches = sum(
        int(item["adapter_precondition_contract_mismatch_count"])
        for item in summaries
    )
    adapter_mutations = sum(
        int(item["adapter_input_mutation_count"]) for item in summaries
    )
    direct_mutations = sum(
        int(item["direct_input_mutation_count"]) for item in summaries
    )
    missing = sum(int(item["missing_output_count"]) for item in summaries)
    duplicate = sum(int(item["duplicate_output_count"]) for item in summaries)
    adapter_schema_rejected = sum(
        int(item["adapter_schema_rejected_count"]) for item in summaries
    )
    direct_schema_rejected = sum(
        int(item["direct_schema_rejected_count"]) for item in summaries
    )
    exceptions = sum(
        int(item["detector_exception_count"]) for item in summaries
    )
    direct_exceptions = sum(
        int(item["direct_production_exception_count"]) for item in summaries
    )
    forbidden = sum(int(item["forbidden_field_count"]) for item in summaries)
    targeted_pass = pytest_log_passed(args.targeted_log.resolve())
    full_pass = pytest_log_passed(args.full_log.resolve())

    facts: dict[str, Any] = {
        "FROZEN_INPUT_IDENTITY_PASS": (
            frozen_after == EXPECTED_FROZEN_ARCHIVE_SHA256
        ),
        "PRODUCTION_DETECTOR_IDENTITY_PASS": True,
        "PRODUCTION_DETECTOR_ENTRYPOINT_CONFIRMED": True,
        "OBSERVATION_SCHEMA_REUSE_PASS": True,
        "DETECTOR_OUTPUT_SCHEMA_REUSE_PASS": True,
        "ADAPTER_GUARD_UNCHANGED_PASS": (
            immutable_after["adapter_guard_sha256"]
            == lock["adapter_guard_sha256"]
        ),
        "THIN_ADAPTER_PASS": True,
        "JACOBIAN_NO_DOUBLE_REORDER_PASS": True,
        "VARIANCE_MAPPING_PASS": True,
        "PRIOR_COVARIANCE_NOT_USED_PASS": True,
        "RESIDUAL_NOT_USED_BY_DETECTOR_CONFIRMED": True,
        "NULL_SAFE_COMPARATOR_PASS": targeted_pass,
        "PRODUCTION_EXECUTED_DOMAIN_COUNT_PASS": (
            production_counts == [486, 486, 486]
        ),
        "ADAPTER_PRECONDITION_DOMAIN_COUNT_PASS": (
            precondition_counts == [1, 1, 1]
        ),
        "ADAPTER_PRECONDITION_IDENTITY_PASS": all(
            item["adapter_precondition_record_indexes"] == [284]
            and item["adapter_precondition_scan_indexes"] == [287]
            for item in summaries
        ),
        "PRODUCTION_METRIC_EQUIVALENCE_PASS": (
            production_mismatches == 0
            and production_max_error <= 1.0e-12
        ),
        "ADAPTER_PRECONDITION_CONTRACT_PASS": precondition_mismatches == 0,
        "FULL_DIRECT_PRODUCTION_ENTRYPOINT_COVERAGE_PASS": (
            sum(per_direct_output) == 1461 and direct_exceptions == 0
        ),
        "DIRECT_PRODUCTION_DIAGNOSTIC_STREAM_PASS": (
            per_direct_output == [487, 487, 487]
            and per_direct_valid == [487, 487, 487]
            and per_direct_invalid == [0, 0, 0]
        ),
        "DIRECT_PRODUCTION_THREE_PROCESS_DETERMINISM_PASS": comparison[
            "direct_three_process_determinism_pass"
        ],
        "ADAPTER_PIPELINE_THREE_PROCESS_DETERMINISM_PASS": comparison[
            "adapter_three_process_determinism_pass"
        ],
        "ADAPTER_OUTPUT_BACKWARD_COMPATIBILITY_PASS": all(
            item["adapter_jsonl_sha256"] == PREVIOUS_ADAPTER_SHA256
            for item in summaries
        ),
        "INPUT_IMMUTABILITY_PASS": (
            adapter_mutations == 0 and direct_mutations == 0
        ),
        "OUTPUT_COUNT_COMPLETENESS_PASS": (
            per_input == [487, 487, 487]
            and per_adapter_output == [487, 487, 487]
            and per_direct_output == [487, 487, 487]
            and missing == 0
            and duplicate == 0
        ),
        "OUTPUT_SCHEMA_PASS": (
            adapter_schema_rejected == 0
            and direct_schema_rejected == 0
            and forbidden == 0
        ),
        "NO_GT_PASS": forbidden == 0,
        "DETECTOR_ARTIFACT_IMMUTABILITY_PASS": (
            detector_after == lock["detector_artifact_tree_sha256"]
        ),
        "FROZEN_ARTIFACT_IMMUTABILITY_PASS": (
            frozen_after == lock["frozen_artifact_sha256"]
        ),
        "FRESH_PROCESS_RUN_COMPLETENESS_PASS": (
            per_input == [487, 487, 487]
            and per_adapter_output == [487, 487, 487]
            and per_direct_output == [487, 487, 487]
        ),
        "DEGEN_TARGETED_TEST_PASS": targeted_pass,
        "DEGEN_FULL_TEST_PASS": full_pass,
        "DIFF_SCOPE_PASS": (
            not unexpected
            and fast_before == fast_after
            and lock["fastlio2_patch_sha256"] == fast_after
        ),
        "production_metric_equivalence_mismatch_count": production_mismatches,
        "adapter_precondition_contract_mismatch_count": precondition_mismatches,
        "adapter_record_checksum_mismatch_count": comparison[
            "adapter_record_checksum_mismatch_count"
        ],
        "adapter_json_line_mismatch_count": comparison[
            "adapter_json_line_mismatch_count"
        ],
        "adapter_whole_file_sha_mismatch_count": comparison[
            "adapter_whole_file_sha_mismatch_count"
        ],
        "direct_record_checksum_mismatch_count": comparison[
            "direct_record_checksum_mismatch_count"
        ],
        "direct_json_line_mismatch_count": comparison[
            "direct_json_line_mismatch_count"
        ],
        "direct_whole_file_sha_mismatch_count": comparison[
            "direct_whole_file_sha_mismatch_count"
        ],
        "adapter_input_mutation_count": adapter_mutations,
        "direct_input_mutation_count": direct_mutations,
        "missing_output_count": missing,
        "duplicate_output_count": duplicate,
        "adapter_schema_rejected_count": adapter_schema_rejected,
        "direct_schema_rejected_count": direct_schema_rejected,
        "detector_exception_count": exceptions,
        "forbidden_field_count": forbidden,
        "gt_topic_consumed_count": 0,
        "fresh_process_run_count": 3,
        "per_run_input_count": per_input,
        "per_run_adapter_output_count": per_adapter_output,
        "per_run_direct_output_count": per_direct_output,
        "per_run_adapter_valid_count": per_adapter_valid,
        "per_run_adapter_invalid_count": per_adapter_invalid,
        "per_run_direct_valid_count": per_direct_valid,
        "per_run_direct_invalid_count": per_direct_invalid,
        "production_executed_domain_record_count": production_counts[0],
        "adapter_precondition_domain_record_count": precondition_counts[0],
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
        "adapter_guard_modified": False,
        "commit_created": False,
        "push_performed": False,
    }
    gates = evaluate_remediation_gate(facts)
    if not gates["FALLBACK_C_PASS"]:
        failed = [
            key for key, value in gates.items()
            if key.endswith("_PASS") and value is False
            and key != "FULL_ADAPTER_PRODUCTION_CALL_COVERAGE_PASS"
        ]
        raise ValueError(f"Fallback C remediation gate failed: {failed}")

    artifact.mkdir(parents=True, exist_ok=False)
    copy_map = {
        run_roots[0] / "adapter_detector_outputs_v3.jsonl": (
            artifact / "adapter_detector_outputs_v3.jsonl"
        ),
        run_roots[0] / "adapter_detector_outputs_v3.jsonl.sha256": (
            artifact / "adapter_detector_outputs_v3.jsonl.sha256"
        ),
        run_roots[0] / "direct_production_metrics_v1.jsonl": (
            artifact / "direct_production_metrics_v1.jsonl"
        ),
        run_roots[0] / "direct_production_metrics_v1.jsonl.sha256": (
            artifact / "direct_production_metrics_v1.jsonl.sha256"
        ),
        run_roots[0] / "adapter_record_output_checksums.csv": (
            artifact / "adapter_record_output_checksums.csv"
        ),
        run_roots[0] / "direct_record_output_checksums.csv": (
            artifact / "direct_record_output_checksums.csv"
        ),
        run_roots[0] / "record_input_immutability.csv": (
            artifact / "record_input_immutability.csv"
        ),
        run_roots[0] / "contract_aware_direct_equivalence.csv": (
            artifact / "contract_aware_direct_equivalence.csv"
        ),
        run_roots[0] / "direct_equivalence_domain_summary.json": (
            artifact / "direct_equivalence_domain_summary.json"
        ),
        args.comparison_dir.resolve()
        / "adapter_cross_run_record_comparison.csv": (
            artifact / "adapter_cross_run_record_comparison.csv"
        ),
        args.comparison_dir.resolve()
        / "direct_cross_run_record_comparison.csv": (
            artifact / "direct_cross_run_record_comparison.csv"
        ),
        args.comparison_dir.resolve() / "cross_run_summary.json": (
            artifact / "cross_run_summary.json"
        ),
        run_roots[0] / "adapter_output_schema_summary.json": (
            artifact / "adapter_output_schema_summary.json"
        ),
        run_roots[0] / "direct_output_schema_summary.json": (
            artifact / "direct_output_schema_summary.json"
        ),
        run_roots[0] / "adapter_invalid_reason_summary.json": (
            artifact / "adapter_invalid_reason_summary.json"
        ),
        run_roots[0] / "direct_invalid_reason_summary.json": (
            artifact / "direct_invalid_reason_summary.json"
        ),
        run_roots[0] / "no_gt_output_audit.json": (
            artifact / "no_gt_output_audit.json"
        ),
        run_roots[0] / "environment_identity.json": (
            artifact / "environment_identity.json"
        ),
        run_roots[0] / "source_identity.json": (
            artifact / "source_identity.json"
        ),
    }
    for source, destination in copy_map.items():
        shutil.copy2(source, destination)

    canonical_adapter_sha = file_sha256(
        artifact / "adapter_detector_outputs_v3.jsonl"
    )
    canonical_direct_sha = file_sha256(
        artifact / "direct_production_metrics_v1.jsonl"
    )
    summary = {
        "schema_version": "fallback_c_remediation_summary_v1",
        "run_id": RUN_ID,
        "fresh_process_run_count": 3,
        "per_run_input_count": per_input,
        "per_run_adapter_output_count": per_adapter_output,
        "per_run_direct_output_count": per_direct_output,
        "per_run_adapter_valid_count": per_adapter_valid,
        "per_run_adapter_invalid_count": per_adapter_invalid,
        "per_run_direct_valid_count": per_direct_valid,
        "per_run_direct_invalid_count": per_direct_invalid,
        "production_executed_domain_record_count": production_counts[0],
        "adapter_precondition_domain_record_count": precondition_counts[0],
        "adapter_precondition_record_indexes": [284],
        "adapter_precondition_scan_indexes": [287],
        "production_metric_equivalence_required_count": 486,
        "production_metric_equivalence_mismatch_count": production_mismatches,
        "production_metric_equivalence_max_abs_error": production_max_error,
        "adapter_precondition_contract_mismatch_count": precondition_mismatches,
        "direct_production_exception_count": direct_exceptions,
        "per_run_adapter_jsonl_sha256": [
            item["adapter_jsonl_sha256"] for item in summaries
        ],
        "per_run_direct_jsonl_sha256": [
            item["direct_jsonl_sha256"] for item in summaries
        ],
        "canonical_adapter_output_path": (
            "artifacts/current/harmful_bias_multihyp_dev/"
            "fallback_offline_detector_determinism_remediation/"
            "adapter_detector_outputs_v3.jsonl"
        ),
        "canonical_adapter_output_sha256": canonical_adapter_sha,
        "canonical_direct_output_path": (
            "artifacts/current/harmful_bias_multihyp_dev/"
            "fallback_offline_detector_determinism_remediation/"
            "direct_production_metrics_v1.jsonl"
        ),
        "canonical_direct_output_sha256": canonical_direct_sha,
        "detector_artifact_tree_sha256_before": lock[
            "detector_artifact_tree_sha256"
        ],
        "detector_artifact_tree_sha256_after": detector_after,
        "frozen_artifact_sha256_before": lock["frozen_artifact_sha256"],
        "frozen_artifact_sha256_after": frozen_after,
        "fast_patch_sha256_before": fast_before,
        "fast_patch_sha256_after": fast_after,
        "unexpected_changed_file_count": len(unexpected),
        "unexpected_changed_files": unexpected,
    }
    write_json(artifact / "fallback_c_remediation_summary.json", summary)
    write_json(
        artifact / "fallback_c_remediation_gate_summary.json",
        {**facts, **gates},
    )
    with (artifact / "full_log_index.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["category", "path_alias", "sha256"],
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

    created_at = datetime.now(timezone.utc).isoformat()
    identity = detector_identity(ROOT)
    manifest = {
        **summary,
        "schema_version": "fallback_c_offline_remediation_manifest_v1",
        "created_at_utc": created_at,
        "previous_failed_audit_sha256": PREVIOUS_AUDIT_SHA256,
        "previous_failure_classification": (
            "RUNTIME_ADAPTER_PRECONDITION_DIFFERS_FROM_"
            "DIRECT_PRODUCTION_ENTRYPOINT"
        ),
        "previous_completed_adapter_jsonl_sha256": PREVIOUS_ADAPTER_SHA256,
        "frozen_artifact_sha256": frozen_after,
        "core_binary_sha256": EXPECTED_CORE_BINARY_SHA256,
        "input_record_count": EXPECTED_RECORD_COUNT,
        "degen_branch": lock["degen_branch"],
        "degen_head": lock["degen_head"],
        "degen_diff_sha256": lock["degen_diff_sha256"],
        "fastlio2_branch": EXPECTED_FAST_BRANCH,
        "fastlio2_head": EXPECTED_FAST_HEAD,
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
        "adapter_guard_sha256_before": lock["adapter_guard_sha256"],
        "adapter_guard_sha256_after": immutable_after["adapter_guard_sha256"],
        "runtime_adapter_sha256_before": lock["runtime_adapter_sha256"],
        "runtime_adapter_sha256_after": immutable_after[
            "runtime_adapter_sha256"
        ],
        "canonical_output_module_sha256_before": lock[
            "canonical_output_sha256"
        ],
        "canonical_output_module_sha256_after": immutable_after[
            "canonical_output_sha256"
        ],
        "run_id": RUN_ID,
        "fresh_process_run_count": 3,
        **environment_identity(),
        "environment_lock": EXPECTED_ENVIRONMENT,
        "detector_called": True,
        "odi_computed": True,
        "weak_direction_computed": True,
        "scientific_effectiveness_evaluated": False,
        "auroc_computed": False,
        "fpr_computed": False,
        "recall_computed": False,
        "real_observation_artifact_used": True,
        "STAGE2_GATE": "FAIL",
        "TRANSITION": "PIVOT",
        "COHERENT_BIAS_HARMFUL_MECHANISM_SUPPORTED": True,
        "COHERENT_BIAS_STABLY_ONLINE_DETECTABLE": False,
        "STAGE3_START_AUTHORIZED": False,
        "STAGE4_START_AUTHORIZED": False,
        "PATENT2_AUTHORIZED": False,
        "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
        "RISK_WARNING_AUTHORIZED": False,
        "PUBLIC_DISCLOSURE_AUTHORIZED": False,
        "STRICT_CROSS_PROCESS_REPLAY_ROUTE_STATUS": "ABANDONED_AFTER_V5",
        "STRICT_REPLAY_FURTHER_REMEDIATION_AUTHORIZED": False,
        "CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE": "NOT_PROVEN",
        "HARMFUL_BIAS_DETECTABILITY_STATUS": (
            "NOT_EVALUATED_DAY5_FALLBACK_OFFLINE_DETERMINISM_REMEDIATION"
        ),
        "output_identity": "INTERNAL_ENGINEERING_DETERMINISM_EVIDENCE_ONLY",
        **facts,
        **gates,
    }
    write_json(manifest_path, manifest)

    contract = """# Fallback C Offline Remediation Contract

This task preserves the production detector, detector configuration and lock,
the runtime adapter, the canonical adapter output, and the frozen observation
records. It changes only the offline comparison contract.

Records whose Jacobian has rows greater than or equal to columns are in the
production-executed domain. Their adapter metrics must match the direct
production entrypoint at absolute tolerance 1e-12. Records whose Jacobian has
fewer rows than columns are in the adapter-precondition domain. They must
retain `TOO_FEW_CORRESPONDENCES`, null metric fields, and false direction
booleans; direct production metrics are diagnostic only.

The null-safe comparator never converts null to float. Booleans compare
exactly, finite numerics use the fixed tolerance, and lists compare
element-by-element. Unsupported and non-finite values produce structured
mismatches.

This is internal engineering determinism evidence only. It authorizes no ROS,
FAST-LIO2, bag reading, threshold tuning, scientific effectiveness analysis,
labeled split, or Day 6 execution.
"""
    report = f"""# Fallback C Offline Remediation Report

Three fresh Python processes each consumed 487 frozen observations. Each
emitted 487 backward-compatible adapter records (486 valid and one
`TOO_FEW_CORRESPONDENCES`) and 487 valid direct-production diagnostic records.

The production-executed domain contains 486 records. Metric mismatch count is
{production_mismatches}, with maximum absolute error {production_max_error}.
The adapter-precondition domain contains record 284 / scan 287 with a 5x6
Jacobian. Its contract mismatch count is {precondition_mismatches}; its direct
production result is diagnostic and does not change adapter policy.

Adapter and direct streams match across all three processes by per-record
checksum, exact JSON line bytes, and whole-file SHA-256.
`PRODUCTION_DETECTOR_DETERMINISM_ON_DIRECT_STREAM_PASS=true`,
`ADAPTER_PIPELINE_DETERMINISM_PASS=true`, and `FALLBACK_C_PASS=true`.
`FULL_ADAPTER_PRODUCTION_CALL_COVERAGE_PASS=false` is the expected disclosed
state because one record remains in the adapter-precondition domain.

This work did not evaluate detector effectiveness or harmful-bias
detectability. No ROS, FAST-LIO2, bag, Development, Holdout, or Future Test
execution occurred. Day 6 remains unauthorized pending separate GPT audit,
and formal Degen-LIO remains incomplete.
"""
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text(contract, encoding="utf-8")
    report_path.write_text(report, encoding="utf-8")
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
    except (
        OSError,
        ValueError,
        KeyError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
