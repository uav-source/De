from backend_qualification_test_support import qualification_protocol


def test_locked_ideal_source_is_an_exact_target_subset_without_noise():
    ideal = qualification_protocol()["ideal_matched_snapshot"]
    assert ideal["source_geometry"] == "exact_target_map_subset"
    assert ideal["subset_selection"]["algorithm"] == "pcg64_permutation_prefix_without_replacement"
    assert ideal["subset_selection"]["selected_rows_sorted_in_target_canonical_order"] is True
    assert ideal["scan_noise_sigma_m"] == 0.0
    assert ideal["map_noise_sigma_m"] == 0.0
    assert ideal["dropout_fraction"] == 0.0

