from zero_perturbation_test_support import development_snapshot


def test_snapshot_has_one_backend_input_checksum_for_all_methods():
    snapshot = development_snapshot("FULL_NOISE")
    supplied = [snapshot.checksums["backend_input_checksum"] for _ in range(3)]
    assert len(set(supplied)) == 1
    assert not snapshot.scan_points.flags.writeable
    assert not snapshot.map_points.flags.writeable
