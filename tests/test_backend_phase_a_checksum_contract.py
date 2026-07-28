import hashlib

import numpy as np

from zero_perturbation.backend_phase_a_metrics import canonical_backend_inputs


def test_backend_checksums_cover_exact_canonical_raw_bytes():
    target = np.arange(60, dtype=np.float64).reshape(20, 3)
    source = target[::2]
    bundle = canonical_backend_inputs(source, target, np.eye(4))
    assert bundle["source_checksum"] == hashlib.sha256(
        bundle["source_points"].tobytes(order="C")
    ).hexdigest()
    assert bundle["target_checksum"] == hashlib.sha256(
        bundle["target_points"].tobytes(order="C")
    ).hexdigest()
    assert bundle["reference_pose_checksum"] == hashlib.sha256(
        bundle["reference_pose"].tobytes(order="C")
    ).hexdigest()
