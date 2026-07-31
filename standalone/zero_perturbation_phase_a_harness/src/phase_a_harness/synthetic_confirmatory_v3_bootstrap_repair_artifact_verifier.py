"""Independent verifier for the compact v3 bootstrap-repair pre-run package."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any


PAYLOAD_FILES = (
    "old_v3_prerun_invalidation_binding.json",
    "old_v3_tag_preservation.json",
    "v3_seed_status.json",
    "bootstrap_root_cause_binding.json",
    "bootstrap_state_machine_contract.json",
    "runtime_state_transition_matrix.csv",
    "formal_command_contract.json",
    "immutable_run_lock_contract.json",
    "command_log_prelock_interruption_report.json",
    "lock_atomic_interruption_report.json",
    "invalid_state_rejection_report.json",
    "fresh_fixture_report.json",
    "resume_fixture_report.json",
    "git_gate_report.json",
    "primary_independent_difference.json",
    "publisher_inventory.json",
    "artifact_verification.json",
    "scientific_core_binding.json",
    "h1_h6_semantics_binding.json",
    "frozen_model_binding.json",
    "backend_binding.json",
    "v3_seed_binding.json",
    "formal_manifest_binding.json",
    "formal_plan_audit.json",
    "formal_dry_run_report.json",
    "test_report.json",
    "implementation_manifest.json",
    "formal_execution_profile.json",
    "formal_run_commands.sh",
    "final_binding_audit.json",
    "final_decision.json",
    "run_manifest.json",
    "pre_run_report.md",
)
INVENTORY_FILES = ("MANIFEST.csv", "SHA256SUMS")
EXPECTED_FILES = frozenset((*PAYLOAD_FILES, *INVENTORY_FILES))
FORMAL_RUNTIME_ROOT = Path(
    "/home/lj/zero_perturbation_runtime/confirmatory/synthetic_confirmatory_v3"
)


class BootstrapRepairArtifactError(RuntimeError):
    """The compact pre-run package is incomplete, unsafe, or inconsistent."""


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _strict_object(path: Path) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=pairs,
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    if type(value) is not dict:
        raise ValueError(f"JSON root is not an object: {path.name}")
    return value


def _symlink_components(path: Path) -> list[str]:
    current = Path(path.anchor)
    result: list[str] = []
    for part in path.parts[1:]:
        current = current / part
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(metadata.st_mode):
            result.append(str(current))
    return result


def _inventory(root: Path) -> tuple[set[str], list[str]]:
    files: set[str] = set()
    unsafe: list[str] = []
    with os.scandir(root) as iterator:
        entries = list(iterator)
    for entry in entries:
        metadata = entry.stat(follow_symlinks=False)
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            unsafe.append(entry.name)
        else:
            files.add(entry.name)
    return files, unsafe


def _verify_manifest(root: Path) -> tuple[int, list[str]]:
    with (root / "MANIFEST.csv").open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    errors: list[str] = []
    if not rows or set(rows[0]) != {"path", "size_bytes", "sha256"}:
        return len(rows), ["MANIFEST.csv schema mismatch"]
    seen: set[str] = set()
    for row in rows:
        relative = row["path"]
        path = root / relative
        if relative in seen or relative not in PAYLOAD_FILES:
            errors.append(f"invalid MANIFEST path: {relative}")
            continue
        seen.add(relative)
        try:
            size = int(row["size_bytes"])
        except ValueError:
            errors.append(f"invalid MANIFEST size: {relative}")
            continue
        if not path.is_file() or path.is_symlink():
            errors.append(f"missing MANIFEST payload: {relative}")
        elif path.stat().st_size != size or _sha(path) != row["sha256"]:
            errors.append(f"MANIFEST payload mismatch: {relative}")
    if seen != set(PAYLOAD_FILES):
        errors.append("MANIFEST payload inventory mismatch")
    return len(rows), errors


def _verify_sha256sums(root: Path) -> tuple[int, list[str]]:
    expected = EXPECTED_FILES - {"SHA256SUMS"}
    seen: set[str] = set()
    errors: list[str] = []
    for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        if len(line) < 67 or line[64:66] != "  ":
            errors.append("malformed SHA256SUMS row")
            continue
        digest, relative = line[:64], line[66:]
        path = root / relative
        if (
            relative in seen
            or relative not in expected
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            errors.append(f"unsafe SHA256SUMS row: {relative}")
            continue
        seen.add(relative)
        if not path.is_file() or path.is_symlink() or _sha(path) != digest:
            errors.append(f"SHA256SUMS mismatch: {relative}")
    if seen != expected:
        errors.append("SHA256SUMS inventory mismatch")
    return len(seen), errors


def verify_bootstrap_repair_prerun_artifact(
    path: str | Path,
    *,
    require_formal_runtime_absent: bool = True,
) -> dict[str, Any]:
    root = Path(os.path.abspath(os.fspath(path)))
    if _symlink_components(root) or root.is_symlink() or not root.is_dir():
        raise BootstrapRepairArtifactError("artifact root is absent or linked")
    files, unsafe = _inventory(root)
    missing = sorted(EXPECTED_FILES - files)
    extra = sorted(files - EXPECTED_FILES)
    manifest_count, manifest_errors = _verify_manifest(root)
    sha_count, sha_errors = _verify_sha256sums(root)
    invalid_json: list[str] = []
    objects: dict[str, dict[str, Any]] = {}
    for name in PAYLOAD_FILES:
        if name.endswith(".json"):
            try:
                objects[name] = _strict_object(root / name)
            except (OSError, UnicodeError, ValueError) as error:
                invalid_json.append(f"{name}: {error}")

    decision = objects.get("final_decision.json", {})
    required_decision = {
        "FINAL_GIT_BINDING_PASS": True,
        "FORMAL_BOOTSTRAP_STATE_MACHINE_QUALIFICATION_PASS": True,
        "SYNTHETIC_CONFIRMATORY_V3_BOOTSTRAP_REPAIR_PRE_RUN_QUALIFICATION_PASS": True,
        "SYNTHETIC_CONFIRMATORY_V3_COMPLETE": False,
        "SYNTHETIC_CONFIRMATORY_V3_EXECUTED": False,
        "SYNTHETIC_CONFIRMATORY_V3_PASS": "NOT_EVALUATED",
        "V3_SEED_SET_REUSE_AUTHORIZED": True,
        "CONFIRMATORY_V3_RUN_AUTHORIZED": True,
        "REAL_DATA_RUN_AUTHORIZED": False,
        "MEASUREMENT_PAPER_MAINLINE_AUTHORIZED": False,
    }
    decision_pass = all(decision.get(key) == value for key, value in required_decision.items())
    state = objects.get("bootstrap_state_machine_contract.json", {})
    interruption = objects.get("command_log_prelock_interruption_report.json", {})
    lock_interruption = objects.get("lock_atomic_interruption_report.json", {})
    invalid = objects.get("invalid_state_rejection_report.json", {})
    fresh = objects.get("fresh_fixture_report.json", {})
    resume = objects.get("resume_fixture_report.json", {})
    gates = objects.get("git_gate_report.json", {})
    difference = objects.get("primary_independent_difference.json", {})
    publisher = objects.get("publisher_inventory.json", {})
    fixture_artifact = objects.get("artifact_verification.json", {})
    science = objects.get("scientific_core_binding.json", {})
    h1_h6 = objects.get("h1_h6_semantics_binding.json", {})
    model = objects.get("frozen_model_binding.json", {})
    backend = objects.get("backend_binding.json", {})
    seed = objects.get("v3_seed_binding.json", {})
    plan = objects.get("formal_plan_audit.json", {})
    dry = objects.get("formal_dry_run_report.json", {})
    tests = objects.get("test_report.json", {})
    final_binding = objects.get("final_binding_audit.json", {})
    semantic_pass = bool(
        decision_pass
        and state.get("FORMAL_BOOTSTRAP_STATE_MACHINE_IMPLEMENTED") is True
        and all(
            state.get(name) is True
            for name in (
                "ABSENT_STATE_PASS",
                "BOOTSTRAP_ONLY_STATE_PASS",
                "RESUMABLE_STATE_PASS",
                "INVALID_STATE_PASS",
            )
        )
        and interruption.get("COMMAND_LOG_PRELOCK_INTERRUPTION_PASS") is True
        and interruption.get("BOOTSTRAP_ONLY_RECOVERY_PASS") is True
        and lock_interruption.get("LOCK_ATOMIC_INTERRUPTION_PASS") is True
        and lock_interruption.get("PARTIAL_LOCK_ACCEPTED_COUNT") == 0
        and invalid.get("INVALID_RUNTIME_STATE_REJECTION_COUNT") == 20
        and invalid.get("INVALID_RUNTIME_STATE_FALSE_ACCEPT_COUNT") == 0
        and fresh.get("FRESH_FIXTURE_EXECUTION_PASS") is True
        and resume.get("RESUME_FIXTURE_EXECUTION_PASS") is True
        and resume.get("VALID_SNAPSHOT_REEXECUTION_COUNT") == 0
        and resume.get("VALID_TRIAL_REEXECUTION_COUNT") == 0
        and resume.get("SNAPSHOT_CHECKSUM_CHANGE_AFTER_RESUME") == 0
        and resume.get("TRIAL_CHECKSUM_CHANGE_AFTER_RESUME") == 0
        and gates.get("ALL_GIT_GATES_PASS") is True
        and difference.get("leaf_difference_count") == 0
        and publisher.get("PUBLISHER_INVENTORY_PASS") is True
        and fixture_artifact.get("ARTIFACT_VERIFIER_PASS") is True
        and science.get("SCIENTIFIC_CORE_FILE_CHANGE_COUNT") == 0
        and h1_h6.get("H1_H6_SEMANTICS_CHANGE_COUNT") == 0
        and model.get("FROZEN_MODEL_CHANGE_COUNT") == 0
        and backend.get("BACKEND_BINDING_CHANGE_COUNT") == 0
        and seed.get("V3_SEED_VALUE_CHANGE_COUNT") == 0
        and seed.get("V3_SEED_ACCESS_COUNT") == 0
        and seed.get("V3_RNG_INSTANTIATION_COUNT") == 0
        and seed.get("V3_SNAPSHOT_CONSTRUCTION_COUNT") == 0
        and seed.get("V3_BACKEND_EXECUTION_COUNT") == 0
        and plan.get("V3_FORMAL_PLAN_PASS") is True
        and dry.get("V3_DRY_RUN_PASS") is True
        and dry.get("V3_FORMAL_RUNTIME_ROOT_NOT_CREATED") is True
        and tests.get("TEST_SUITE_PASS") is True
        and final_binding.get("FINAL_GIT_BINDING_PASS") is True
    )
    formal_absent = not FORMAL_RUNTIME_ROOT.exists()
    passed = bool(
        not missing
        and not extra
        and not unsafe
        and not manifest_errors
        and not sha_errors
        and not invalid_json
        and semantic_pass
        and (formal_absent or not require_formal_runtime_absent)
    )
    return {
        "PRE_RUN_ARTIFACT_VERIFICATION_PASS": passed,
        "actual_file_count": len(files),
        "decision_semantics_pass": decision_pass,
        "expected_file_count": len(EXPECTED_FILES),
        "extra_files": extra,
        "formal_runtime_root_absent": formal_absent,
        "invalid_json_files": invalid_json,
        "manifest_entry_count": manifest_count,
        "manifest_errors": manifest_errors,
        "missing_files": missing,
        "schema_version": "synthetic_confirmatory_v3_bootstrap_repair_artifact_verification_v1",
        "semantic_gate_pass": semantic_pass,
        "sha256_entry_count": sha_count,
        "sha256_errors": sha_errors,
        "unsafe_entries": unsafe,
    }


__all__ = [
    "BootstrapRepairArtifactError",
    "EXPECTED_FILES",
    "PAYLOAD_FILES",
    "verify_bootstrap_repair_prerun_artifact",
]
