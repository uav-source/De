import numpy as np

from pcl_backend_v2_test_support import DATA, fixture_manifest, read_ascii_xyz_pcd


def test_v2_fixture_is_unique_finite_three_dimensional_and_bytewise_identical():
    source_path = DATA / "nondegenerate_source.pcd"
    target_path = DATA / "nondegenerate_target.pcd"
    source = read_ascii_xyz_pcd(source_path)
    target = read_ascii_xyz_pcd(target_path)
    assert len(source) >= 300
    assert len(source) == len(np.unique(source, axis=0))
    assert np.all(np.isfinite(source))
    assert np.array_equal(source, target)
    assert source_path.read_bytes() == target_path.read_bytes()
    assert np.linalg.matrix_rank(np.cov(source, rowvar=False, bias=True)) == 3


def test_v2_constructive_point_to_plane_geometry_is_full_rank_without_rng():
    manifest = fixture_manifest()
    assert manifest["point_count"] == 806
    assert manifest["point_cloud_rank"] == 3
    assert manifest["analytic_surface_normal_direction_rank"] == 3
    assert manifest["analytic_point_to_plane_jacobian_rank"] == 6
    assert manifest["rank_deficient"] is False
    assert manifest["surface_construction"] == {
        "mutually_perpendicular_planes": 3,
        "off_centre_cuboid_exposed_faces": 5,
        "random_seed_used": False,
    }
