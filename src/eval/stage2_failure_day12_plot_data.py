"""Deterministic plot-data derivation from the frozen Day 11B v2 merged CSV."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence, Tuple

import numpy as np

from eval.stage2_failure_day12_schema import (
    DESCRIPTIVE_SUMMARY_FIELDS,
    FIGURE_DATA_FIELDS,
    write_csv,
)


METRIC_RULES = (
    ("abs_weak_innovation_z_huber", "weak_innovation_z_huber", "stat_input_valid"),
    ("abs_huber_window_mean", "huber_window_mean", "window_ready"),
    ("abs_huber_cusum_signed", "huber_cusum_signed", "window_ready"),
    ("huber_current_same_sign_run_length", "huber_current_same_sign_run_length", "stat_input_valid"),
)
SORT_ORDER = {"geometry": 0, "observation": 1, "huber_full": 0,
              "huber_projected_gain": 1, "clean": 0, "coherent_subhuber_slip": 1}


def read_merged_rows(path: Path) -> Tuple[Sequence[str], Sequence[Mapping[str, str]]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return tuple(reader.fieldnames or ()), list(reader)


def source_row_sha256(row: Mapping[str, Any], fields: Sequence[str]) -> str:
    payload = {field: row[field] for field in fields}
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_all_plot_data(
    merged_fields: Sequence[str], merged_rows: Sequence[Mapping[str, str]]
) -> Mapping[str, Sequence[Mapping[str, Any]]]:
    ordered = sorted(merged_rows, key=_sort_key)
    hashes = {id(row): source_row_sha256(row, merged_fields) for row in ordered}
    output: Dict[str, Sequence[Mapping[str, Any]]] = {}
    for figure_id in list(FIGURE_DATA_FIELDS)[:3]:
        fields = FIGURE_DATA_FIELDS[figure_id]
        rows = []
        for source in ordered:
            row = {field: source[field] for field in fields if field != "source_row_sha256"}
            row["source_row_sha256"] = hashes[id(source)]
            rows.append(row)
        output[figure_id] = rows
    distribution = []
    for source in ordered:
        for metric_name, source_field, gate_field in METRIC_RULES:
            value = float(source[source_field])
            included = _bool(source[gate_field]) and math.isfinite(value)
            if metric_name.startswith("abs_"):
                value = abs(value)
            distribution.append({
                "case_id": source["case_id"], "sweep": source["sweep"],
                "method": source["method"], "stress": source["stress"],
                "frame_index": source["frame_index"], "metric_name": metric_name,
                "metric_value": value, "inclusion_rule": f"{gate_field} == true and finite",
                "included": included,
                "deterministic_jitter": ((int(source["frame_index"]) % 7) - 3) * 0.035,
                "source_row_sha256": hashes[id(source)],
            })
    output["day12_fig04_clean_stress_distributions"] = distribution
    validate_plot_data(output, merged_fields, merged_rows)
    return output


def validate_plot_data(
    data: Mapping[str, Sequence[Mapping[str, Any]]],
    merged_fields: Sequence[str], merged_rows: Sequence[Mapping[str, str]],
) -> Mapping[str, Any]:
    source_index = {
        (row["case_id"], str(row["frame_index"])): row
        for row in merged_rows
    }
    audits = []
    for figure_id, fields in FIGURE_DATA_FIELDS.items():
        rows = list(data.get(figure_id, []))
        keys = []
        hash_mismatches = 0
        value_mismatches = 0
        nonfinite = 0
        for row in rows:
            if set(row) != set(fields):
                hash_mismatches += 1
                continue
            key = (str(row["case_id"]), str(row["frame_index"]))
            if figure_id.endswith("distributions"):
                duplicate_key = key + (str(row["metric_name"]),)
            else:
                duplicate_key = key
            keys.append(duplicate_key)
            source = source_index.get(key)
            expected_hash = source_row_sha256(source, merged_fields) if source is not None else None
            hash_mismatches += int(expected_hash != row["source_row_sha256"])
            value_mismatches += int(
                source is None or not _plot_row_matches_source(figure_id, row, source, fields)
            )
            for value in row.values():
                try:
                    nonfinite += int(math.isinf(float(value)))
                except (TypeError, ValueError):
                    pass
        duplicates = len(keys) - len(set(keys))
        expected = len(merged_rows) * (4 if figure_id.endswith("distributions") else 1)
        passed = (
            len(rows) == expected
            and duplicates == hash_mismatches == value_mismatches == nonfinite == 0
        )
        audits.append({
            "figure_id": figure_id, "row_count": len(rows),
            "duplicate_key_count": duplicates,
            "source_row_hash_mismatch_count": hash_mismatches,
            "source_value_mismatch_count": value_mismatches,
            "nonfinite_violation_count": nonfinite, "audit_pass": passed,
        })
    return {
        "audits": audits,
        "plot_data_audit_failure_count": sum(int(not row["audit_pass"]) for row in audits),
        "source_row_hash_mismatch_count": sum(row["source_row_hash_mismatch_count"] for row in audits),
        "source_value_mismatch_count": sum(row["source_value_mismatch_count"] for row in audits),
    }


def _plot_row_matches_source(
    figure_id: str,
    row: Mapping[str, Any],
    source: Mapping[str, str],
    fields: Sequence[str],
) -> bool:
    if not figure_id.endswith("distributions"):
        return all(
            str(row[field]) == str(source[field])
            for field in fields
            if field != "source_row_sha256"
        )
    rules = {metric: (source_field, gate) for metric, source_field, gate in METRIC_RULES}
    metric = str(row["metric_name"])
    if metric not in rules:
        return False
    source_field, gate = rules[metric]
    raw_value = float(source[source_field])
    expected_value = abs(raw_value) if metric.startswith("abs_") else raw_value
    expected_included = _bool(source[gate]) and math.isfinite(raw_value)
    expected_jitter = ((int(source["frame_index"]) % 7) - 3) * 0.035
    identity_ok = all(
        str(row[field]) == str(source[field])
        for field in ("case_id", "sweep", "method", "stress", "frame_index")
    )
    value_ok = (
        math.isnan(expected_value) and math.isnan(float(row["metric_value"]))
    ) or float(row["metric_value"]) == expected_value
    return bool(
        identity_ok
        and value_ok
        and _bool(row["included"]) == expected_included
        and str(row["inclusion_rule"]) == f"{gate} == true and finite"
        and float(row["deterministic_jitter"]) == expected_jitter
    )


def write_plot_data(output_dir: Path, data: Mapping[str, Sequence[Mapping[str, Any]]]) -> Mapping[str, Any]:
    records = []
    for figure_id, fields in FIGURE_DATA_FIELDS.items():
        path = Path(output_dir) / "figure_data" / f"{figure_id}.csv"
        write_csv(path, data[figure_id], fields)
        records.append({
            "figure_id": figure_id, "plot_data_path": str(path),
            "plot_data_sha256": _sha256(path), "row_count": len(data[figure_id]),
        })
    return {"plot_data_file_count": len(records), "files": records}


def build_descriptive_summary(merged_rows: Sequence[Mapping[str, str]]) -> Sequence[Mapping[str, Any]]:
    output = []
    for sweep in ("geometry", "observation"):
        for method in ("huber_full", "huber_projected_gain"):
            for stress in ("clean", "coherent_subhuber_slip"):
                rows = [row for row in merged_rows if row["sweep"] == sweep and row["method"] == method and row["stress"] == stress]
                innovations = _finite_abs(rows, "weak_innovation_z_huber", "stat_input_valid")
                means = _finite_abs(rows, "huber_window_mean", "window_ready")
                cusum = _finite_abs(rows, "huber_cusum_signed", "window_ready")
                runs = _finite(rows, "huber_current_same_sign_run_length", "stat_input_valid")
                prior = _finite(rows, "prior_axis_error_abs_m")
                posterior = _finite(rows, "posterior_axis_error_abs_m")
                reduction = _finite(rows, "axis_abs_error_reduction_m")
                output.append({
                    "sweep": sweep, "method": method, "stress": stress,
                    "frame_count": len(rows),
                    "valid_innovation_frame_count": sum(int(_bool(row["stat_input_valid"])) for row in rows),
                    "window_ready_frame_count": sum(int(_bool(row["window_ready"])) for row in rows),
                    "median_abs_weak_innovation_z_huber": _stat(innovations, 50),
                    "q25_abs_weak_innovation_z_huber": _stat(innovations, 25),
                    "q75_abs_weak_innovation_z_huber": _stat(innovations, 75),
                    "median_abs_huber_window_mean": _stat(means, 50),
                    "q25_abs_huber_window_mean": _stat(means, 25),
                    "q75_abs_huber_window_mean": _stat(means, 75),
                    "max_abs_huber_cusum_signed": max(cusum) if cusum else float("nan"),
                    "median_abs_huber_cusum_signed": _stat(cusum, 50),
                    "max_huber_same_sign_run_length": max(runs) if runs else float("nan"),
                    "median_huber_same_sign_run_length": _stat(runs, 50),
                    "median_prior_axis_error_abs_m": _stat(prior, 50),
                    "median_posterior_axis_error_abs_m": _stat(posterior, 50),
                    "median_axis_abs_error_reduction_m": _stat(reduction, 50),
                    "fraction_axis_error_reduced": float(np.mean(np.asarray(reduction) > 0.0)),
                })
    return output


def _sort_key(row: Mapping[str, str]) -> tuple:
    return (
        SORT_ORDER[row["sweep"]], SORT_ORDER[row["method"]], SORT_ORDER[row["stress"]],
        int(row["frame_index"]), float(row["timestamp"]), row["case_id"],
    )


def _finite(rows: Sequence[Mapping[str, str]], field: str, gate: str = "") -> list[float]:
    values = []
    for row in rows:
        value = float(row[field])
        if (not gate or _bool(row[gate])) and math.isfinite(value):
            values.append(value)
    return values


def _finite_abs(rows: Sequence[Mapping[str, str]], field: str, gate: str) -> list[float]:
    return [abs(value) for value in _finite(rows, field, gate)]


def _stat(values: Sequence[float], percentile: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=float), percentile)) if values else float("nan")


def _bool(value: Any) -> bool:
    return value is True or str(value) == "True"


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
