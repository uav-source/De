import hashlib

import pytest

from fastlio2_adapter.day6_branch_divergence import (
    ROOT_CAUSE_REQUIRED_GATES,
    Day6BranchAuditError,
    ensure_root_cause_not_overclaimed,
    evaluate_root_cause_gate,
    validate_archive_identity,
    verify_internal_sha256s,
)


def test_archive_sha_mismatch_fails_closed(tmp_path):
    path = tmp_path / "audit.tar.gz"
    path.write_bytes(b"wrong archive")
    with pytest.raises(Day6BranchAuditError, match="SHA mismatch"):
        validate_archive_identity(path)


def test_internal_hash_mismatch_fails_closed(tmp_path):
    (tmp_path / "evidence.txt").write_text("changed", encoding="utf-8")
    (tmp_path / "SHA256SUMS").write_text(
        f"{'0' * 64}  evidence.txt\n", encoding="utf-8"
    )
    with pytest.raises(Day6BranchAuditError, match="internal hash failures"):
        verify_internal_sha256s(tmp_path)


def test_internal_hash_success(tmp_path):
    payload = b"frozen"
    (tmp_path / "evidence.bin").write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    (tmp_path / "SHA256SUMS").write_text(
        f"{digest}  evidence.bin\n", encoding="utf-8"
    )
    assert verify_internal_sha256s(tmp_path)["internal_hash_pass"] is True


def test_missing_direct_evidence_forces_root_cause_false():
    with pytest.raises(Day6BranchAuditError, match="cannot be proven"):
        ensure_root_cause_not_overclaimed(
            fast_branch_root_cause_proven=True,
            missing_direct_evidence=["raw payload checksum"],
        )


def test_complete_audit_does_not_authorize_next_experiment_or_integration():
    facts = {name: True for name in ROOT_CAUSE_REQUIRED_GATES}
    facts["BRANCH_DIVERGENCE_LOCALIZED_PASS"] = True
    facts["FAST_BRANCH_ROOT_CAUSE_PROVEN"] = False
    result = evaluate_root_cause_gate(facts)
    assert result["DAY6_BRANCH_DIVERGENCE_ROOT_CAUSE_AUDIT_PASS"] is True
    assert result["FAST_BRANCH_ROOT_CAUSE_PROVEN"] is False
    assert result["NEXT_DIAGNOSTIC_EXPERIMENT_AUTHORIZED"] is False
    assert result["STAGE3_START_AUTHORIZED"] is False
    assert result["FAST_LIO2_INTEGRATION_AUTHORIZED"] is False
