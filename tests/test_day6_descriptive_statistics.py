from fastlio2_adapter.day6_statistical_characterization import (
    describe,
    detector_metric_statistics,
    latency_statistics,
)


def output(valid, value):
    return {
        "valid": valid,
        "odi_trans": value,
        "ais_trans": value,
        "lambda_min_trans": value,
        "condition_number_trans": value,
        "primary_eigengap_ratio": value,
        "translation_eigenvalues_ascending": (
            [value, value + 1, value + 2] if value is not None else None
        ),
    }


def test_describe_has_requested_quantiles():
    summary = describe(range(1, 101))
    assert summary["count"] == 100
    assert summary["median"] == 50.5
    assert set(("p01", "p05", "p25", "p75", "p95", "p99")) <= set(summary)


def test_invalid_records_remain_in_total_count():
    rows, summary = detector_metric_statistics(
        [output(True, 1.0), output(False, None)]
    )
    assert summary["total_record_count"] == 2
    assert summary["invalid_record_count"] == 1
    assert all(row["total_record_count"] == 2 for row in rows)


def test_latency_has_all_and_warmup_excluded_views():
    rows = [
        {
            "adapter_total_call_latency_ns": index + 1,
            "direct_production_call_latency_ns": index + 2,
        }
        for index in range(20)
    ]
    summary = latency_statistics(rows)
    assert summary["adapter_total_call_latency_ns"]["all_records"]["count"] == 20
    assert (
        summary["adapter_total_call_latency_ns"][
            "excluding_first_10_records"
        ]["count"]
        == 10
    )
    assert summary["online_end_to_end_latency_evaluated"] is False
