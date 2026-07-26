import csv
import json

from fastlio2_adapter.day7_map_update_events import (
    materialize_delta_accounting,
)


FIELDS = (
    "scan_index",
    "call_index",
    "batch_kind",
    "input_point_count",
    "map_count_before",
    "map_count_after",
    "event_count",
    "expected_logical_count_delta",
    "observed_logical_count_delta",
    "delta_accounting_pass",
)


def write_calls(directory, rows):
    with (
        directory / "day7_map_mutation_call_summaries.csv"
    ).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def row(expected=1, observed=1, passed=1):
    return {
        "scan_index": 150,
        "call_index": 0,
        "batch_kind": "DOWNSAMPLED",
        "input_point_count": 1,
        "map_count_before": 10,
        "map_count_after": 11,
        "event_count": 1,
        "expected_logical_count_delta": expected,
        "observed_logical_count_delta": observed,
        "delta_accounting_pass": passed,
    }


def test_closed_map_delta_passes(tmp_path):
    write_calls(tmp_path, [row()])
    summary = materialize_delta_accounting(tmp_path)
    assert summary["map_delta_accounting_pass"] is True
    assert summary["unexplained_map_count_delta_count"] == 0
    assert json.loads(
        (tmp_path / "map_mutation_delta_accounting_summary.json").read_text()
    ) == summary


def test_unclosed_map_delta_fails(tmp_path):
    write_calls(tmp_path, [row(expected=1, observed=0, passed=0)])
    summary = materialize_delta_accounting(tmp_path)
    assert summary["map_delta_accounting_pass"] is False
    assert summary["failure_count"] == 1
