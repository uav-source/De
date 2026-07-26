import hashlib

import pytest

from fastlio2_adapter.runtime_equivalence import verify_file_sha256, verify_run_lock


def test_remediation_lock_rejects_source_binary_or_environment_change():
    lock = {
        "binary_sha256": "a",
        "degen_diff_sha256": "b",
        "fastlio2_diff_sha256": "c",
        "playback_rate": 0.25,
        "runtime_modes": ["AUDIT_ONLY", "CAPTURE_ONLY", "COMPACT_EXPORT"],
    }
    verify_run_lock(lock, dict(lock))
    for field in lock:
        changed = dict(lock)
        changed[field] = "changed"
        with pytest.raises(ValueError, match=field):
            verify_run_lock(lock, changed)


def test_remediation_source_hash_is_fail_closed(tmp_path):
    path = tmp_path / "source"
    path.write_bytes(b"locked")
    expected = hashlib.sha256(b"locked").hexdigest()
    assert verify_file_sha256(path, expected)
    path.write_bytes(b"changed")
    assert not verify_file_sha256(path, expected)
