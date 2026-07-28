import numpy as np

from zero_perturbation_test_support import development_snapshot


def test_ideal_matched_scan_is_exact_range_filtered_map_subset():
    snapshot = development_snapshot("IDEAL_MATCHED")
    scan_world = snapshot.scan_points + snapshot.reference_pose[1:4]
    resolution = 1.0e-9
    map_rows = {tuple(row) for row in np.rint(snapshot.map_points / resolution).astype(np.int64)}
    scan_rows = np.rint(scan_world / resolution).astype(np.int64)
    assert all(tuple(row) in map_rows for row in scan_rows)
    assert np.allclose(
        scan_world - snapshot.reference_pose[1:4], snapshot.scan_points, atol=1.0e-15
    )
