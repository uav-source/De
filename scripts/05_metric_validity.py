#!/usr/bin/env python3
"""Compare Day 10 metric validity against drift targets."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np
import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eval.stats import (  # noqa: E402
    bootstrap_ci_corr,
    leave_one_sequence_out_correlation,
    make_high_axis_drift_flag,
    pearson_corr,
    rank_metrics_by_correlation,
    safe_auc_if_binary_available,
    spearman_corr,
)


DEFAULT_SEQUENCES = [
    "OC-L0-S01-M1",
    "ST-L3-S01-M1",
    "CT-L2-S01-M2",
    "RT-L4-S01-M1",
]

METRIC_FIELDS = {
    "ODI": "mean_ODI",
    "condition_number": "median_condition_number",
    "lambda_min_clamped": "median_lambda_min_clamped",
    "AIS": "mean_AIS",
}

TARGET_FIELDS = [
    "axis_drift_rate",
    "cross_drift_rate",
    "weak_drift_alignment",
    "high_axis_drift_flag",
]

MERGED_FIELDNAMES = [
    "scope",
    "metric_name",
    "target_name",
    "spearman_rho",
    "spearman_p",
    "pearson_r",
    "bootstrap_ci_low",
    "bootstrap_ci_high",
    "auc_if_available",
    "valid_sample_count",
    "reason",
]

PER_SEQUENCE_FIELDNAMES = [
    "sequence_id",
    "metric_name",
    "target_name",
    "spearman_rho",
    "spearman_p",
    "pearson_r",
    "valid_sample_count",
    "reason",
]

LOSO_FIELDNAMES = [
    "held_out_sequence",
    "metric_name",
    "target_name",
    "train_spearman_rho",
    "test_spearman_rho_or_auc",
    "valid_train_sample_count",
    "valid_test_sample_count",
    "reason",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="Detector config path for reproducibility record.")
    parser.add_argument("--results", type=Path, default=ROOT / "results/day14", help="Day 14 results directory.")
    parser.add_argument("--n-boot", type=int, default=1000, help="Bootstrap samples for merged confidence intervals.")
    return parser.parse_args()


def load_config(path: Path | None) -> Dict[str, object]:
    if path is None:
        return {}
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError(f"Config must be a mapping: {path}")
    return config


def load_metric_rows(results_dir: Path) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for sequence_id in DEFAULT_SEQUENCES:
        metrics_path = results_dir / "metrics" / f"{sequence_id}_metrics.csv"
        raw_path = results_dir / "raw" / f"{sequence_id}_odi.csv"
        if not metrics_path.exists():
            raise FileNotFoundError(f"Missing metrics CSV: {metrics_path}")
        if not raw_path.exists():
            raise FileNotFoundError(f"Missing raw ODI CSV: {raw_path}")
        validate_raw_odi(raw_path)
        with metrics_path.open("r", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                parsed = {"sequence_id": sequence_id}
                for key, value in row.items():
                    parsed[key] = parse_float_or_string(value)
                for metric_name, column in METRIC_FIELDS.items():
                    parsed[metric_name] = float(parsed[column])
                rows.append(parsed)
    if not rows:
        raise ValueError("No metric rows loaded")
    add_high_axis_drift_flag(rows)
    return rows


def validate_raw_odi(path: Path) -> None:
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
    required = ["ODI", "AIS", "lambda_min_clamped", "condition_number"]
    missing = [name for name in required if name not in fieldnames]
    if missing:
        raise ValueError(f"Raw ODI CSV missing required fields {missing}: {path}")


def add_high_axis_drift_flag(rows: List[Dict[str, object]]) -> None:
    flags = make_high_axis_drift_flag([float(row["axis_drift_rate"]) for row in rows])
    for row, flag in zip(rows, flags):
        row["high_axis_drift_flag"] = int(flag)


def compute_merged_validity(rows: Sequence[Mapping[str, object]], random_seed: int, n_boot: int) -> List[Dict[str, object]]:
    outputs: List[Dict[str, object]] = []
    for metric_name in METRIC_FIELDS:
        metric = values(rows, metric_name)
        for target_name in TARGET_FIELDS:
            target = values(rows, target_name)
            outputs.append(compute_validity_row("merged_all_sequences", metric_name, target_name, metric, target, random_seed, n_boot))
    return outputs


def compute_per_sequence_validity(rows: Sequence[Mapping[str, object]]) -> List[Dict[str, object]]:
    outputs: List[Dict[str, object]] = []
    for sequence_id in DEFAULT_SEQUENCES:
        subset = [row for row in rows if row["sequence_id"] == sequence_id]
        for metric_name in METRIC_FIELDS:
            metric = values(subset, metric_name)
            for target_name in TARGET_FIELDS:
                target = values(subset, target_name)
                rho, p_value = spearman_corr(metric, target)
                pearson = pearson_corr(metric, target)
                count = valid_count(metric, target)
                outputs.append(
                    {
                        "sequence_id": sequence_id,
                        "metric_name": metric_name,
                        "target_name": target_name,
                        "spearman_rho": rho,
                        "spearman_p": p_value,
                        "pearson_r": pearson,
                        "valid_sample_count": count,
                        "reason": reason_for(metric, target, rho),
                    }
                )
    return outputs


def compute_loso_validity(rows: Sequence[Mapping[str, object]]) -> List[Dict[str, object]]:
    outputs: List[Dict[str, object]] = []
    for metric_name in METRIC_FIELDS:
        for target_name in TARGET_FIELDS:
            loso = leave_one_sequence_out_correlation(rows, metric_name, target_name)
            for row in loso:
                if target_name == "high_axis_drift_flag":
                    held_out = row["held_out_sequence"]
                    test = [r for r in rows if r["sequence_id"] == held_out]
                    row["test_spearman_rho_or_auc"] = safe_auc_if_binary_available(
                        values(test, metric_name),
                        values(test, target_name),
                    )
                row["reason"] = reason_for_loso(row)
                outputs.append(row)
    return outputs


def compute_validity_row(
    scope: str,
    metric_name: str,
    target_name: str,
    metric: np.ndarray,
    target: np.ndarray,
    random_seed: int,
    n_boot: int,
) -> Dict[str, object]:
    rho, p_value = spearman_corr(metric, target)
    pearson = pearson_corr(metric, target)
    ci_low, ci_high = bootstrap_ci_corr(metric, target, n_boot=int(n_boot), random_seed=random_seed)
    auc = safe_auc_if_binary_available(metric, target) if target_name.endswith("_flag") else float("nan")
    return {
        "scope": scope,
        "metric_name": metric_name,
        "target_name": target_name,
        "spearman_rho": rho,
        "spearman_p": p_value,
        "pearson_r": pearson,
        "bootstrap_ci_low": ci_low,
        "bootstrap_ci_high": ci_high,
        "auc_if_available": auc,
        "valid_sample_count": valid_count(metric, target),
        "reason": reason_for(metric, target, rho),
    }


def write_csv(path: Path, fieldnames: Sequence[str], rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def print_rank_summary(rows: Sequence[Mapping[str, object]]) -> None:
    axis_rank = rank_metrics_by_correlation(rows, "axis_drift_rate")
    weak_rank = rank_metrics_by_correlation(rows, "weak_drift_alignment")
    if axis_rank:
        top = axis_rank[0]
        print(
            f"merged axis_drift top={top['metric_name']} "
            f"rho={float(top['spearman_rho']):.6f}"
        )
    if weak_rank:
        top = weak_rank[0]
        print(
            f"merged weak_drift_alignment top={top['metric_name']} "
            f"rho={float(top['spearman_rho']):.6f}"
        )


def values(rows: Sequence[Mapping[str, object]], key: str) -> np.ndarray:
    return np.asarray([float(row.get(key, float("nan"))) for row in rows], dtype=float)


def valid_count(x: Iterable[float], y: Iterable[float]) -> int:
    x_arr = np.asarray(list(x), dtype=float)
    y_arr = np.asarray(list(y), dtype=float)
    return int(np.sum(np.isfinite(x_arr) & np.isfinite(y_arr)))


def reason_for(metric: Iterable[float], target: Iterable[float], rho: float) -> str:
    metric_arr = np.asarray(list(metric), dtype=float)
    target_arr = np.asarray(list(target), dtype=float)
    finite = np.isfinite(metric_arr) & np.isfinite(target_arr)
    if int(np.sum(finite)) < 3:
        return "insufficient_finite_samples"
    if np.max(metric_arr[finite]) - np.min(metric_arr[finite]) <= 1.0e-12:
        return "constant_metric"
    if np.max(target_arr[finite]) - np.min(target_arr[finite]) <= 1.0e-12:
        return "constant_target"
    if not np.isfinite(rho):
        return "undefined_correlation"
    return ""


def reason_for_loso(row: Mapping[str, object]) -> str:
    if int(row["valid_train_sample_count"]) < 3:
        return "insufficient_train_samples"
    if int(row["valid_test_sample_count"]) < 3:
        return "insufficient_test_samples"
    if not np.isfinite(float(row["train_spearman_rho"])):
        return "undefined_train_correlation"
    if not np.isfinite(float(row["test_spearman_rho_or_auc"])):
        return "undefined_test_score"
    return ""


def parse_float_or_string(value: str) -> object:
    try:
        return float(value)
    except ValueError:
        return value


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    random_seed = int(config.get("random_seed", 42))
    rows = load_metric_rows(args.results)

    merged = compute_merged_validity(rows, random_seed, int(args.n_boot))
    per_sequence = compute_per_sequence_validity(rows)
    loso = compute_loso_validity(rows)

    table_dir = args.results / "tables"
    write_csv(table_dir / "day10_metric_validity.csv", MERGED_FIELDNAMES, merged)
    write_csv(table_dir / "day10_metric_validity_per_sequence.csv", PER_SEQUENCE_FIELDNAMES, per_sequence)
    write_csv(table_dir / "day10_metric_validity_loso.csv", LOSO_FIELDNAMES, loso)

    print(
        f"metric validity: windows={len(rows)} merged_rows={len(merged)} "
        f"per_sequence_rows={len(per_sequence)} loso_rows={len(loso)} "
        f"n_boot={int(args.n_boot)} out={table_dir}"
    )
    print_rank_summary(merged)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
