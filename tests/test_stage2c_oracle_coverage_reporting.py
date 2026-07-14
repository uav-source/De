from eval.weak_update_stage2c import index_rows, oracle_gap


def test_oracle_report_keeps_positive_and_nonpositive_pairs():
    rows = []
    for process_seed, full, projected, oracle in [
        (1, 1.0, 0.8, 0.7),
        (2, 1.0, 1.1, 1.2),
    ]:
        for method, axis in [
            ("huber_full", full),
            ("huber_projected_gain", projected),
            ("huber_oracle_projected_gain", oracle),
        ]:
            rows.append({
                "sweep": "geometry", "level": "L3",
                "stress": "coherent_subhuber_slip", "geometry_seed": 1,
                "sensor_seed": 1, "process_seed": process_seed,
                "method": method, "axis_rmse": axis,
            })
    report = oracle_gap(rows, index_rows(rows, include_method=True))[0]
    assert report["total_pair_count"] == 2
    assert report["oracle_positive_pair_count"] == 1
    assert report["oracle_nonpositive_pair_count"] == 1
    assert report["conditional_eligible_pair_count"] == 1
    assert report["conditional_coverage_fraction"] == 0.5
