from zero_perturbation_test_support import development_snapshot


def test_backend_input_checksum_binds_scan_map_and_reference():
    snapshot = development_snapshot("SCAN_NOISE_ONLY")
    checksum = snapshot.checksums["backend_input_checksum"]
    backend_inputs = {name: checksum for name in ("native_full", "native_frozen", "open3d_full")}
    assert len(set(backend_inputs.values())) == 1
    assert checksum not in {
        snapshot.checksums["scan_checksum"],
        snapshot.checksums["map_checksum"],
        snapshot.checksums["reference_pose_checksum"],
    }
