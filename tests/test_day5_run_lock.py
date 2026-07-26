import hashlib

import pytest

from fastlio2_adapter.runtime_equivalence import verify_file_sha256, verify_run_lock


def test_run_lock_accepts_exact_values_and_rejects_change():
    lock = {"binary_sha256": "a", "runner_code_sha256": "b"}
    verify_run_lock(lock, dict(lock))
    with pytest.raises(ValueError, match="binary_sha256"):
        verify_run_lock(lock, {"binary_sha256": "changed"})


def test_bag_or_source_hash_mismatch_fails(tmp_path):
    path = tmp_path / "bag.manifest"
    path.write_bytes(b"frozen")
    expected = hashlib.sha256(b"frozen").hexdigest()
    assert verify_file_sha256(path, expected)
    assert not verify_file_sha256(path, "0" * 64)
