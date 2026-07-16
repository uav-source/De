import numpy as np
import pytest

from eval.stage2_failure_day11b_provenance import (
    canonical_array_sequence_sha256,
    canonical_ndarray_sha256,
)


def test_canonical_checksum_known_vector():
    value = np.array([[1.0, -2.5], [3.25, 4.0]], dtype="<f8")
    assert canonical_ndarray_sha256(value) == (
        "b7c527707aae10e27726c002ca87016c1fb8fc471d060d09b170044de346e3d2"
    )


def test_checksum_is_sensitive_to_dtype_shape_and_value():
    value = np.arange(6, dtype=np.int32)
    original = canonical_ndarray_sha256(value)
    assert canonical_ndarray_sha256(value.astype(np.int64)) != original
    assert canonical_ndarray_sha256(value.reshape(2, 3)) != original
    changed = value.copy()
    changed[0] = 99
    assert canonical_ndarray_sha256(changed) != original


def test_sequence_checksum_is_sensitive_to_frame_order():
    first = np.array([1, 2], dtype=np.int16)
    second = np.array([3, 4], dtype=np.int16)
    assert canonical_array_sequence_sha256([first, second]) != canonical_array_sequence_sha256(
        [second, first]
    )


def test_non_contiguous_view_matches_its_contiguous_copy_without_mutation():
    source = np.arange(12, dtype=np.float64).reshape(3, 4)
    view = source[:, ::2]
    before = source.copy()
    assert not view.flags.c_contiguous
    assert canonical_ndarray_sha256(view) == canonical_ndarray_sha256(np.ascontiguousarray(view))
    assert np.array_equal(source, before)


def test_object_dtype_is_rejected():
    with pytest.raises(TypeError, match="object dtype"):
        canonical_ndarray_sha256(np.array([object()], dtype=object))
