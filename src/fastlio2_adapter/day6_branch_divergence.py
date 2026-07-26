"""Authorization, identity and gate helpers for the Day 6 branch audit."""

from __future__ import annotations

import hashlib
import json
import tarfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


DAY6_AUDIT_PRE_PERMISSION_NORMALIZATION_SHA256 = (
    "bf15339f89860438e842b8e37cdfe9ed693fe942e8dac13ed54aa4134413f61f"
)
DAY6_AUDIT_FINAL_DELIVERY_SHA256 = (
    "a6fad908751adf527812ad2cad5ed497c1f2190dff20f5549e41ef3c36eab61a"
)
EXPECTED_OBSERVATION_SHA256 = (
    "f84f5255742525d6cb0aafa9a93169de09b3ab31d4db45c3bdf6680e3f1681e1",
    "b030458403bee4d703b935c24e3fa8123c59df9db17b7386b7f0f775374d7317",
    "09c34ad6ed4d214df394e0e11ec54382292ccfa56b01946ee218a7097115f6ab",
)
EXPECTED_ADAPTER_SHA256 = (
    "186add45e53113deae872be55e67c6b884e85fe146610b210cfc9bb1bb045729",
    "bffdf60b9bbd6322c4828b0abad64bf26561fcf7a4a46508758d0f834625df7c",
    "553a88a20aeb82fe872df6ad8ada8dbe37b37786e8e220a76d8f9196fd01b696",
)
EXPECTED_DIRECT_SHA256 = (
    "986573f0a90d80b9707993b06831dd38b283b5f4c6e40340ee107f5e4d66726b",
    "5d83b89abad5603074778bd521e616e2b47075392537f32bd24d67a0e0fcdf8c",
    "c667da5b0f4fecf061aa104b90b46061579edbcfd2b4dcd7b564f0685ea189bb",
)
EXPECTED_DEGEN_BRANCH = "spike/harmful-bias-multihyp-dev"
EXPECTED_DEGEN_HEAD = "711ac05ccc683263446fb8656c0054048832f54c"
EXPECTED_FAST_BRANCH = "spike/readonly-observation-tap-v1"
EXPECTED_FAST_HEAD = "f19b4c42a77dc11793c912d67b9e56dcafa279dc"
ROOT_CAUSE_REQUIRED_GATES = (
    "DAY6_INPUT_ARCHIVE_IDENTITY_PASS",
    "DAY6_INTERNAL_HASH_PASS",
    "THREE_OBSERVATION_BINARY_IDENTITY_PASS",
    "THREE_RECORD_INDEX_PASS",
    "THREE_LIFECYCLE_PASS",
    "SEMANTIC_OBSERVATION_CONTRACT_PASS",
    "PAIRWISE_SEMANTIC_COMPARISON_PASS",
    "FIRST_DIVERGENCE_LOCALIZATION_PASS",
    "PREVIOUS_RECORD_IDENTITY_CHECK_COMPLETE",
    "DIVERGENCE_ORDER_CLASSIFICATION_COMPLETE",
    "EVIDENCE_GRANULARITY_AUDIT_PASS",
    "FAST_SOURCE_PATH_AUDIT_PASS",
    "RUNTIME_ENVIRONMENT_AUDIT_PASS",
    "INFORMATION_MATRIX_RECONSTRUCTION_PASS",
    "EIGENSYSTEM_RECONSTRUCTION_PASS",
    "SIGN_INVARIANT_DIRECTION_ANALYSIS_PASS",
    "WEAK_SUBSPACE_PRINCIPAL_ANGLE_ANALYSIS_PASS",
    "GAP_AND_PERTURBATION_ANALYSIS_PASS",
    "TIME_CONTINUITY_ASSOCIATION_ANALYSIS_PASS",
    "CROSS_RUN_EIGENSPACE_ANALYSIS_PASS",
    "HYPOTHESIS_MATRIX_COMPLETE",
    "ROOT_CAUSE_LIMITATION_DISCLOSED",
    "NEXT_MINIMAL_EXPERIMENT_DESIGN_COMPLETE",
    "PLOTS_COMPLETE",
    "DEGEN_TARGETED_TEST_PASS",
    "DEGEN_FULL_TEST_PASS",
    "DIFF_SCOPE_PASS",
    "AUDIT_PACKAGE_SCOPE_PASS",
)


class Day6BranchAuditError(ValueError):
    """The branch-audit authorization or gate failed closed."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def authorization_lineage() -> dict[str, Any]:
    return {
        "schema_version": "day6_audit_authorization_lineage_v1",
        "pre_permission_normalization_sha256": (
            DAY6_AUDIT_PRE_PERMISSION_NORMALIZATION_SHA256
        ),
        "final_delivery_sha256": DAY6_AUDIT_FINAL_DELIVERY_SHA256,
        "change_classification": "ARCHIVE_ROOT_PERMISSION_NORMALIZATION",
        "old_root_mode": "0775",
        "required_final_root_mode": "0755",
        "scientific_payload_change_authorized": False,
        "old_archive_required_locally": False,
        "authorization_status": (
            "FINAL_DELIVERY_SHA_ACCEPTED_WITH_INVARIANT_CHECKS"
        ),
    }


def validate_archive_identity(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise Day6BranchAuditError("final Day 6 audit is missing")
    actual = sha256_file(path)
    if actual != DAY6_AUDIT_FINAL_DELIVERY_SHA256:
        raise Day6BranchAuditError("final Day 6 audit SHA mismatch")
    with tarfile.open(path, "r:gz") as handle:
        members = handle.getmembers()
    roots = sorted(
        {
            Path(member.name).parts[0]
            for member in members
            if member.name and Path(member.name).parts
        }
    )
    root_members = [
        member for member in members if member.name == roots[0]
    ]
    if len(roots) != 1 or not root_members:
        raise Day6BranchAuditError("archive root is ambiguous")
    root_mode = int(root_members[0].mode)
    bad_directories = [
        member.name
        for member in members
        if member.isdir() and member.mode != 0o755
    ]
    bad_files = [
        member.name
        for member in members
        if member.isfile()
        and not member.name.endswith("/restore_and_verify.sh")
        and member.mode != 0o644
    ]
    bad_restore = [
        member.name
        for member in members
        if member.isfile()
        and member.name.endswith("/restore_and_verify.sh")
        and member.mode != 0o755
    ]
    links = [
        member.name for member in members if member.issym() or member.islnk()
    ]
    if (
        root_mode != 0o755
        or bad_directories
        or bad_files
        or bad_restore
        or links
    ):
        raise Day6BranchAuditError("archive permissions or links invalid")
    return {
        "archive_sha256": actual,
        "archive_root": roots[0],
        "archive_root_mode": "0755",
        "member_count": len(members),
        "bad_directory_mode_count": 0,
        "bad_regular_file_mode_count": 0,
        "bad_restore_mode_count": 0,
        "symlink_count": 0,
        "archive_identity_pass": True,
    }


def verify_internal_sha256s(root: Path) -> dict[str, Any]:
    checksum = root / "SHA256SUMS"
    if not checksum.is_file():
        raise Day6BranchAuditError("SHA256SUMS missing")
    failures = []
    checked = 0
    for line in checksum.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        digest, relative = line.split("  ", 1)
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            failures.append(relative)
            continue
        checked += 1
        if not candidate.is_file() or sha256_file(candidate) != digest:
            failures.append(relative)
    if failures:
        raise Day6BranchAuditError(
            f"internal hash failures: {failures[:10]}"
        )
    return {
        "checked_file_count": checked,
        "internal_hash_failure_count": 0,
        "internal_hash_pass": True,
    }


def validate_source_lock(
    root: Path,
    source_hashes: Mapping[str, str],
) -> list[str]:
    mismatches = []
    for relative, expected in source_hashes.items():
        path = root / relative
        actual = sha256_file(path) if path.is_file() else "MISSING"
        if actual != expected:
            mismatches.append(relative)
    return mismatches


def evaluate_root_cause_gate(
    facts: Mapping[str, Any],
) -> dict[str, Any]:
    gates = {
        name: bool(facts.get(name, False))
        for name in ROOT_CAUSE_REQUIRED_GATES
    }
    gates.update(
        {
            "BRANCH_DIVERGENCE_LOCALIZED_PASS": bool(
                facts.get("BRANCH_DIVERGENCE_LOCALIZED_PASS", False)
            ),
            "FAST_BRANCH_ROOT_CAUSE_PROVEN": bool(
                facts.get("FAST_BRANCH_ROOT_CAUSE_PROVEN", False)
            ),
            "NEXT_DIAGNOSTIC_EXPERIMENT_RECOMMENDED": bool(
                facts.get("NEXT_DIAGNOSTIC_EXPERIMENT_RECOMMENDED", True)
            ),
            "NEXT_DIAGNOSTIC_EXPERIMENT_AUTHORIZED": False,
            "STAGE2_GATE": "FAIL",
            "TRANSITION": "PIVOT",
            "STAGE3_START_AUTHORIZED": False,
            "STAGE4_START_AUTHORIZED": False,
            "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
            "CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE": "NOT_PROVEN",
            "HARMFUL_BIAS_DETECTABILITY_STATUS": (
                "NOT_EVALUATED_DAY6_BRANCH_DIVERGENCE_ROOT_CAUSE"
            ),
        }
    )
    gates["DAY6_BRANCH_DIVERGENCE_ROOT_CAUSE_AUDIT_PASS"] = all(
        gates[name] for name in ROOT_CAUSE_REQUIRED_GATES
    )
    return gates


def ensure_root_cause_not_overclaimed(
    *,
    fast_branch_root_cause_proven: bool,
    missing_direct_evidence: Sequence[str],
) -> None:
    if fast_branch_root_cause_proven and missing_direct_evidence:
        raise Day6BranchAuditError(
            "FAST root cause cannot be proven with missing direct evidence"
        )


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
