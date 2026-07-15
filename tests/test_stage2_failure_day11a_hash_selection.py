import builtins
import hashlib

import pytest

from eval.stage2_failure_deterministic_case import deterministic_case_index


def test_sha256_selection_matches_independent_known_vector():
    label = "Degen-LIO-Day11R1|known-vector"
    digest_bytes = hashlib.sha256(label.encode("utf-8")).digest()
    expected_digest = digest_bytes.hex()
    expected_index = int.from_bytes(digest_bytes, "big", signed=False) % 800
    assert deterministic_case_index(label, 800) == (expected_digest, expected_index)


def test_empty_candidate_pool_is_rejected():
    with pytest.raises(ValueError, match="greater than zero"):
        deterministic_case_index("label", 0)


def test_python_hash_does_not_affect_selection(monkeypatch):
    expected = deterministic_case_index("fixed-label", 37)

    def fail_hash(value):
        raise AssertionError(f"builtins.hash was called with {value!r}")

    with monkeypatch.context() as context:
        context.setattr(builtins, "hash", fail_hash)
        actual = deterministic_case_index("fixed-label", 37)
    assert actual == expected
