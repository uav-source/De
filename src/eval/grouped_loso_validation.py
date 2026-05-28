"""Day 19 grouped and leave-one-sequence-out metric validation."""

from __future__ import annotations

import csv
import json
import statistics
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_METRICS = [
    "ODI_median",
    "AIS_median",
    "lambda_min_clamped_median",
    "condition_number_median",
]
DEFAULT_TARGETS = ["axis_drift_rate", "weak_drift_alignment"]

GROUPED_FIELDNAMES = [
    "metric_name",
    "target_name",
    "n_sequences",
    "n_valid_sequences",
    "median_abs_rho",
    "mean_abs_rho",
    "sign_consistency",
    "n_positive",
    "n_negative",
    "n_undefined",
    "best_sequence_count",
    "interpretation",
]

LOSO_FIELDNAMES = [
    "held_out_sequence",
    "held_out_scene_family",
    "target_name",
    "selected_metric_from_train",
    "train_mean_abs_rho",
    "held_out_rho",
    "held_out_abs_rho",
    "held_out_validity_status",
    "ODI_held_out_rho",
    "AIS_held_out_rho",
    "lambda_min_clamped_held_out_rho",
    "condition_number_held_out_rho",
    "interpretation",
]

PASS_FAIL_FIELDNAMES = [
    "metric_name",
    "target_name",
    "passes_grouped_validity",
    "passes_loso_stability",
    "passes_sign_consistency",
    "beats_baselines",
    "final_day19_status",
    "reason",
]


def load_day18_inputs(day30_root: Path) -> Dict[str, Any]:
    """Read Day 18 output tables required by grouped / LOSO validation."""

    paths = {
        "window_metrics": day30_root / "tables/day18_window_metrics.csv",
        "within_sequence_correlations": day30_root / "tables/day18_within_sequence_correlations.csv",
        "sequence_validity_summary": day30_root / "tables/day18_sequence_validity_summary.csv",
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing required Day19 input file(s): "
            + "; ".join(missing)
            + ". Run scripts/11_within_sequence_validation.py before Day 19."
        )
    data = {name: read_csv_rows(path) for name, path in paths.items()}
    empty = [name for name, rows in data.items() if not rows]
    if empty:
        raise ValueError(f"Day18 input table(s) are empty: {', '.join(empty)}")
    data["input_paths"] = list(paths.values())
    return data


def compute_grouped_metric_summary(
    correlation_rows: Sequence[Mapping[str, str]],
    metrics: Sequence[str],
    targets: Sequence[str],
) -> List[Dict[str, str]]:
    """Summarize per-sequence correlations by metric and target."""

    sequences = sorted({row["sequence_id"] for row in correlation_rows})
    outputs: List[Dict[str, str]] = []
    for target in targets:
        best_counts = best_metric_counts(correlation_rows, metrics, target)
        for metric in metrics:
            rows = [
                row
                for row in correlation_rows
                if row["metric_name"] == metric and row["target_name"] == target
            ]
            valid_rhos = [
                to_float(row["spearman_rho"])
                for row in rows
                if row.get("validity_status") == "valid" and np.isfinite(to_float(row["spearman_rho"]))
            ]
            n_positive, n_negative, sign_consistency = compute_sign_consistency(valid_rhos)
            abs_rhos = [abs(value) for value in valid_rhos]
            outputs.append(
                {
                    "metric_name": metric,
                    "target_name": target,
                    "n_sequences": str(len(sequences)),
                    "n_valid_sequences": str(len(valid_rhos)),
                    "median_abs_rho": format_float(safe_median(abs_rhos)),
                    "mean_abs_rho": format_float(safe_mean(abs_rhos)),
                    "sign_consistency": format_float(sign_consistency),
                    "n_positive": str(n_positive),
                    "n_negative": str(n_negative),
                    "n_undefined": str(len(sequences) - len(valid_rhos)),
                    "best_sequence_count": str(best_counts.get(metric, 0)),
                    "interpretation": grouped_interpretation(
                        metric,
                        target,
                        len(valid_rhos),
                        sign_consistency,
                        best_counts.get(metric, 0),
                    ),
                }
            )
    return outputs


def compute_sign_consistency(rhos: Iterable[float]) -> Tuple[int, int, float]:
    """Return positive/negative counts and majority sign ratio."""

    finite = [float(value) for value in rhos if np.isfinite(value) and abs(float(value)) > 1.0e-12]
    if not finite:
        return 0, 0, float("nan")
    n_positive = sum(value > 0.0 for value in finite)
    n_negative = sum(value < 0.0 for value in finite)
    return int(n_positive), int(n_negative), float(max(n_positive, n_negative) / len(finite))


def run_leave_one_sequence_out_selection(
    correlation_rows: Sequence[Mapping[str, str]],
    metrics: Sequence[str],
    targets: Sequence[str],
    selection_rule: str = "mean_abs_spearman_on_train",
) -> List[Dict[str, str]]:
    """Select the best training metric and evaluate it on held-out sequence."""

    if selection_rule != "mean_abs_spearman_on_train":
        raise ValueError(f"Unsupported selection_rule: {selection_rule}")
    sequences = sorted({row["sequence_id"] for row in correlation_rows})
    scene_family = {
        row["sequence_id"]: row["scene_family"]
        for row in correlation_rows
    }
    outputs: List[Dict[str, str]] = []
    for target in targets:
        for held_out in sequences:
            train_rows = [row for row in correlation_rows if row["sequence_id"] != held_out and row["target_name"] == target]
            held_rows = [row for row in correlation_rows if row["sequence_id"] == held_out and row["target_name"] == target]
            train_scores = {
                metric: mean_abs_valid_rho([row for row in train_rows if row["metric_name"] == metric])
                for metric in metrics
            }
            selected_metric = select_best_metric(train_scores)
            selected_held = find_metric_row(held_rows, selected_metric) if selected_metric != "none" else None
            held_out_rho = to_float(selected_held.get("spearman_rho")) if selected_held else float("nan")
            held_out_status = selected_held.get("validity_status", "undefined") if selected_held else "undefined_no_train_metric"
            output = {
                "held_out_sequence": held_out,
                "held_out_scene_family": scene_family.get(held_out, "unknown"),
                "target_name": target,
                "selected_metric_from_train": selected_metric,
                "train_mean_abs_rho": format_float(train_scores.get(selected_metric, float("nan"))),
                "held_out_rho": format_float(held_out_rho),
                "held_out_abs_rho": format_float(abs(held_out_rho) if np.isfinite(held_out_rho) else float("nan")),
                "held_out_validity_status": held_out_status,
                "interpretation": loso_interpretation(selected_metric, held_out_status, train_scores.get(selected_metric, float("nan"))),
            }
            output.update(held_out_metric_columns(held_rows))
            outputs.append(output)
    return outputs


def compare_odi_against_baselines(
    grouped_rows: Sequence[Mapping[str, str]],
    loso_rows: Sequence[Mapping[str, str]],
    metrics: Sequence[str],
    targets: Sequence[str],
    min_valid_sequences: int,
) -> List[Dict[str, str]]:
    """Build pass/fail rows for each metric and target with strict ODI criteria."""

    grouped_by_key = {(row["metric_name"], row["target_name"]): row for row in grouped_rows}
    outputs: List[Dict[str, str]] = []
    for target in targets:
        target_grouped = [row for row in grouped_rows if row["target_name"] == target]
        best_mean = max(
            [to_float(row["mean_abs_rho"]) for row in target_grouped if np.isfinite(to_float(row["mean_abs_rho"]))],
            default=float("nan"),
        )
        for metric in metrics:
            row = grouped_by_key[(metric, target)]
            mean_abs = to_float(row["mean_abs_rho"])
            sign_consistency = to_float(row["sign_consistency"])
            n_valid = int(float(row["n_valid_sequences"]))
            best_count = int(float(row["best_sequence_count"]))
            if metric == "ODI_median":
                passes_grouped = n_valid >= int(min_valid_sequences) and best_count >= int(min_valid_sequences)
            else:
                passes_grouped = n_valid >= int(min_valid_sequences)
            passes_sign = np.isfinite(sign_consistency) and sign_consistency >= 0.75
            passes_loso = metric_loso_valid_count(loso_rows, metric, target) >= int(min_valid_sequences)
            beats = np.isfinite(mean_abs) and np.isfinite(best_mean) and mean_abs >= best_mean - 1.0e-12
            status = "candidate_supported" if passes_grouped and passes_sign and passes_loso and beats else "exploratory_not_validated"
            reason = pass_fail_reason(metric, passes_grouped, passes_loso, passes_sign, beats, best_count, min_valid_sequences)
            outputs.append(
                {
                    "metric_name": metric,
                    "target_name": target,
                    "passes_grouped_validity": str(passes_grouped).lower(),
                    "passes_loso_stability": str(passes_loso).lower(),
                    "passes_sign_consistency": str(passes_sign).lower(),
                    "beats_baselines": str(beats).lower(),
                    "final_day19_status": status,
                    "reason": reason,
                }
            )
    return outputs


def compute_day19_pass_fail(
    grouped_rows: Sequence[Mapping[str, str]],
    loso_rows: Sequence[Mapping[str, str]],
    metrics: Sequence[str],
    targets: Sequence[str],
    min_valid_sequences: int,
) -> List[Dict[str, str]]:
    return compare_odi_against_baselines(grouped_rows, loso_rows, metrics, targets, min_valid_sequences)


def write_day19_manifest(
    path: Path,
    *,
    config: Mapping[str, Any],
    inputs: Sequence[Path],
    outputs: Sequence[Path],
    grouped_rows: Sequence[Mapping[str, str]],
    loso_rows: Sequence[Mapping[str, str]],
    pass_fail_rows: Sequence[Mapping[str, str]],
    runtime_seconds: float,
) -> Dict[str, Any]:
    missing = [relative_to_root(output) for output in outputs if output != path and not output.exists()]
    odi_axis = find_pass_fail(pass_fail_rows, "ODI_median", "axis_drift_rate")
    manifest = {
        "status": "OK" if not missing and grouped_rows and loso_rows and pass_fail_rows else "FAILED",
        "git_commit": git_commit(),
        "source_validation": config.get("source_validation", "day18_within_sequence"),
        "inputs": [relative_to_root(path) for path in inputs],
        "outputs": [relative_to_root(path) for path in outputs],
        "n_metrics": len(config.get("metrics", DEFAULT_METRICS)),
        "n_targets": len(config.get("targets", DEFAULT_TARGETS)),
        "n_sequences": len({row["held_out_sequence"] for row in loso_rows}),
        "odi_grouped_status": odi_axis.get("passes_grouped_validity", "false"),
        "odi_loso_status": odi_axis.get("passes_loso_stability", "false"),
        "day19_validation_passed": bool(not missing and grouped_rows and loso_rows and pass_fail_rows),
        "missing_artifacts": missing,
        "runtime_seconds": round(float(runtime_seconds), 6),
        "interpretation": "data chain passed; this is not authorization for weak-subspace update",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def best_metric_counts(
    correlation_rows: Sequence[Mapping[str, str]],
    metrics: Sequence[str],
    target: str,
) -> Dict[str, int]:
    counts = {metric: 0 for metric in metrics}
    for sequence_id in sorted({row["sequence_id"] for row in correlation_rows}):
        rows = [
            row
            for row in correlation_rows
            if row["sequence_id"] == sequence_id
            and row["target_name"] == target
            and row["metric_name"] in metrics
            and row.get("validity_status") == "valid"
        ]
        best = select_best_metric({row["metric_name"]: abs(to_float(row["spearman_rho"])) for row in rows})
        if best != "none":
            counts[best] = counts.get(best, 0) + 1
    return counts


def grouped_interpretation(metric: str, target: str, n_valid: int, sign_consistency: float, best_count: int) -> str:
    if n_valid == 0:
        return "no valid per-sequence correlations; cannot interpret grouped validity"
    if metric == "ODI_median":
        if n_valid < 3 or best_count < 3 or not np.isfinite(sign_consistency) or sign_consistency < 0.75:
            return "ODI remains exploratory and is not validated for robust drift prediction."
        return "ODI has grouped support under Day 19 thresholds, but still requires controlled Day 20 checks"
    return f"{metric} grouped validity for {target}; compare fairly against ODI and other baselines"


def loso_interpretation(selected_metric: str, held_status: str, train_score: float) -> str:
    if selected_metric == "none" or not np.isfinite(train_score):
        return "no valid training metric could be selected"
    if held_status != "valid":
        return f"train-selected metric {selected_metric} is not valid on held-out sequence ({held_status})"
    return f"train-selected metric {selected_metric} remains valid on held-out sequence"


def pass_fail_reason(metric: str, grouped: bool, loso: bool, sign: bool, beats: bool, best_count: int, min_valid_sequences: int) -> str:
    missing = []
    if not grouped:
        missing.append("grouped_validity")
    if not loso:
        missing.append("loso_stability")
    if not sign:
        missing.append("sign_consistency")
    if not beats:
        missing.append("baseline_comparison")
    if metric == "ODI_median" and best_count < int(min_valid_sequences):
        missing.append("best_sequence_support")
    if not missing:
        return "passes Day 19 screening for this target; still exploratory"
    if metric == "ODI_median":
        return "ODI remains exploratory and is not validated for robust drift prediction. Missing: " + ", ".join(missing)
    return "does not pass all Day 19 screening checks. Missing: " + ", ".join(missing)


def metric_loso_valid_count(loso_rows: Sequence[Mapping[str, str]], metric: str, target: str) -> int:
    column = metric_to_loso_column(metric)
    count = 0
    for row in loso_rows:
        if row["target_name"] != target:
            continue
        rho = to_float(row.get(column))
        if np.isfinite(rho):
            count += 1
    return count


def held_out_metric_columns(held_rows: Sequence[Mapping[str, str]]) -> Dict[str, str]:
    values = {
        "ODI_held_out_rho": "nan",
        "AIS_held_out_rho": "nan",
        "lambda_min_clamped_held_out_rho": "nan",
        "condition_number_held_out_rho": "nan",
    }
    for metric in DEFAULT_METRICS:
        row = find_metric_row(held_rows, metric)
        values[metric_to_loso_column(metric)] = format_float(to_float(row.get("spearman_rho")) if row else float("nan"))
    return values


def metric_to_loso_column(metric: str) -> str:
    if metric == "ODI_median":
        return "ODI_held_out_rho"
    if metric == "AIS_median":
        return "AIS_held_out_rho"
    if metric == "lambda_min_clamped_median":
        return "lambda_min_clamped_held_out_rho"
    if metric == "condition_number_median":
        return "condition_number_held_out_rho"
    raise ValueError(f"Unsupported LOSO metric column: {metric}")


def mean_abs_valid_rho(rows: Sequence[Mapping[str, str]]) -> float:
    values = [
        abs(to_float(row["spearman_rho"]))
        for row in rows
        if row.get("validity_status") == "valid" and np.isfinite(to_float(row["spearman_rho"]))
    ]
    return safe_mean(values)


def select_best_metric(scores: Mapping[str, float]) -> str:
    finite = {metric: value for metric, value in scores.items() if np.isfinite(value)}
    if not finite:
        return "none"
    return sorted(finite.items(), key=lambda item: (-item[1], item[0]))[0][0]


def find_metric_row(rows: Sequence[Mapping[str, str]], metric: str) -> Mapping[str, str] | None:
    for row in rows:
        if row.get("metric_name") == metric:
            return row
    return None


def find_pass_fail(rows: Sequence[Mapping[str, str]], metric: str, target: str) -> Mapping[str, str]:
    for row in rows:
        if row.get("metric_name") == metric and row.get("target_name") == target:
            return row
    return {}


def write_csv(path: Path, fieldnames: Sequence[str], rows: Sequence[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def safe_mean(values: Sequence[float]) -> float:
    finite = [float(value) for value in values if np.isfinite(value)]
    return float(statistics.fmean(finite)) if finite else float("nan")


def safe_median(values: Sequence[float]) -> float:
    finite = [float(value) for value in values if np.isfinite(value)]
    return float(statistics.median(finite)) if finite else float("nan")


def to_float(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float("nan")


def format_float(value: float) -> str:
    if not np.isfinite(value):
        return "nan"
    if abs(value) < 1.0e-12:
        return "0"
    return f"{float(value):.12g}"


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def relative_to_root(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)
