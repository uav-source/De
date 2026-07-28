from backend_phase_a_v1_2_test_support import target_points, transform
from zero_perturbation.backend_phase_a_v1_2 import raw_array_sha256, select_parent_indices, source_from_parent_indices


def test_frozen_hash_subset_produces_ten_unique_sources_without_rng():
    target = target_points(512)
    checksums = set()
    for measurement in (7711, 8821):
        for repeat in range(5):
            indices = select_parent_indices(target=target, reference_pose=transform(), scene_variant="SYNTHETIC", geometry_seed=6659, measurement_seed=measurement, repeat_index=repeat)
            source, _, _ = source_from_parent_indices(target, indices, transform())
            checksums.add(raw_array_sha256(source))
    assert len(checksums) == 10
