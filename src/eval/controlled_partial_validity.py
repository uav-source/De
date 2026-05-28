"""Day 20 controlled / partial metric-validity analysis."""

from __future__ import annotations

import csv
import json
import math
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np

from eval.stats import rankdata_average


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_METRICS = [
    "ODI_median",
    "AIS_median",
    "lambda_min_clamped_median",
    "condition_number_median",
]
DEFAULT_TARGETS = ["axis_drift_rate", "weak_drift_alignment"]

PARTIAL_FIELDNAMES = [
    "metric_name",
    "target_name",
    "control_set",
    "scope",
    "sequence_id",
    "scene_family",
    "partial_spearman_rho",
    "abs_partial_spearman_rho",
    "n_samples",
    "expected_sign",
    "observed_sign",
    "expected_sign_match",
    "effect_size_threshold",
    "passes_effect_size",
    "substantive_validity_status",
    "interpretation",
]

REGRESSION_FIELDNAMES = [
    "target_name",
    "metric_name",
    "control_set",
    "coefficient",
    "standardized_coefficient",
    "residual_rho",
    "n_samples",
    "expected_sign_match",
    "interpretation",
]

PERMUTATION_FIELDNAMES = [
    "metric_name",
    "target_name",
    "scope",
    "sequence_id",
    "observed_abs_partial_rho",
    "permutation_p_value",
    "n_permutations",
    "seed",
    "passes_permutation_screen",
    "interpretation",
]

INCREMENTAL_FIELDNAMES = [
    "metric_name",
    "target_name",
    "passes_expected_sign",
    "passes_effect_size",
    "passes_permutation",
    "passes_incremental_validity",
    "beats_or_matches_baselines",
    "final_day20_status",
    "reason",
]


def load_day20_inputs(day30_root: Path) -> Dict[str, Any]:
    """Read Day 18 and Day 19 inputs required by Day 20."""

    paths = {
        "window_metrics": day30_root / "tables/day18_window_metrics.csv",
        "day19_grouped": day30_root / "tables/day19_grouped_metric_summary.csv",
        "day19_loso": day30_root / "tables/day19_loso_selection_results.csv",
        "day19_pass_fail": day30_root / "tables/day19_metric_pass_fail_summary.csv",
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing required Day20 input file(s): "
            + "; ".join(missing)
            + ". Run Day 18 and Day 19 validation before Day 20."
        )
    tables = {name: read_csv_rows(path) for name, path in paths.items()}
    empty = [name for name, rows in tables.items() if not rows]
    if empty:
        raise ValueError(f"Day20 input table(s) are empty: {', '.join(empty)}")
    tables["input_paths"] = list(paths.values())
    return tables


def rank_transform_columns(rows: Sequence[Mapping[str, str]], columns: Sequence[str]) -> Dict[str, np.ndarray]:
    """Rank-transform finite numeric columns, preserving NaN positions."""

    outputs: Dict[str, np.ndarray] = {}
    for column in columns:
        values = np.asarray([to_float(row.get(column)) for row in rows], dtype=float)
        ranks = np.full(values.shape, np.nan, dtype=float)
        finite = np.isfinite(values)
        if np.sum(finite) > 0:
            ranks[finite] = rankdata_average(values[finite])
        outputs[column] = ranks
    return outputs


def residualize_against_controls(
    values: np.ndarray,
    controls: np.ndarray,
    min_samples: int = 6,
    prune_degenerate: bool = True,
) -> Tuple[np.ndarray, str, int, int]:
    """Residualize ranked values against ranked controls using least squares."""

    y = np.asarray(values, dtype=float)
    x = np.asarray(controls, dtype=float)
    if x.ndim == 1:
        x = x.reshape(-1, 1)
    if x.shape[0] != y.shape[0]:
        raise ValueError("values and controls must have the same row count")
    finite = np.isfinite(y) & np.all(np.isfinite(x), axis=1)
    n = int(np.sum(finite))
    residual = np.full(y.shape, np.nan, dtype=float)
    if n < int(min_samples):
        return residual, "undefined_insufficient_samples", n, 0

    y_fit = y[finite]
    x_fit = x[finite]
    if finite_variation(y_fit) <= 1.0e-12:
        return residual, "undefined_constant_target", n, 0

    if prune_degenerate:
        keep = [idx for idx in range(x_fit.shape[1]) if finite_variation(x_fit[:, idx]) > 1.0e-12]
        x_fit = x_fit[:, keep] if keep else np.zeros((n, 0), dtype=float)
    design = np.column_stack([np.ones(n, dtype=float), x_fit])
    rank = int(np.linalg.matrix_rank(design))
    if rank < design.shape[1]:
        if not prune_degenerate:
            return residual, "undefined_singular_controls", n, rank
        design = select_independent_columns(design)
        rank = int(np.linalg.matrix_rank(design))
    if n <= rank + 2:
        return residual, "undefined_insufficient_samples", n, rank

    beta, *_ = np.linalg.lstsq(design, y_fit, rcond=None)
    local_residual = y_fit - design @ beta
    if finite_variation(local_residual) <= 1.0e-12:
        return residual, "undefined_singular_controls", n, rank
    residual[finite] = local_residual
    return residual, "ok", n, rank


def compute_partial_spearman(
    rows: Sequence[Mapping[str, str]],
    metric: str,
    target: str,
    controls: Sequence[str],
    group_controls: Sequence[str],
    expected_sign_map: Mapping[str, Mapping[str, str]],
    effect_size_threshold: float,
    scope: str,
    sequence_id: str = "ALL",
    scene_family: str = "ALL",
) -> Dict[str, Any]:
    """Compute one controlled partial Spearman analysis row."""

    numeric_controls = [control for control in controls if control != metric]
    rank_columns = [metric, target] + numeric_controls
    ranked = rank_transform_columns(rows, rank_columns)
    control_matrix = build_control_matrix(rows, ranked, numeric_controls, group_controls if scope == "merged_controlled" else [])
    metric_residual, metric_status, n_metric, rank_metric = residualize_against_controls(
        ranked[metric], control_matrix, prune_degenerate=True
    )
    target_residual, target_status, n_target, rank_target = residualize_against_controls(
        ranked[target], control_matrix, prune_degenerate=True
    )
    n_samples = int(min(n_metric, n_target))
    status = "computable"
    rho = float("nan")
    if metric_status != "ok" or target_status != "ok":
        status = pick_undefined_status(metric_status, target_status)
    else:
        rho = residual_correlation(metric_residual, target_residual)
        if not np.isfinite(rho):
            status = "undefined_singular_controls"

    expected_sign = str(expected_sign_map.get(metric, {}).get(target, "unknown"))
    observed_sign = observed_sign_from_rho(rho)
    sign_match = compute_expected_sign_check(expected_sign, rho)
    passes_effect = bool(np.isfinite(rho) and abs(rho) >= float(effect_size_threshold))
    substantive = (
        "substantive_candidate"
        if status == "computable" and sign_match == "true" and passes_effect
        else status if status != "computable" else "exploratory_small_or_wrong_sign"
    )
    row = {
        "metric_name": metric,
        "target_name": target,
        "control_set": "numeric_plus_group_controls" if scope == "merged_controlled" else "numeric_controls_within_sequence",
        "scope": scope,
        "sequence_id": sequence_id,
        "scene_family": scene_family,
        "partial_spearman_rho": format_float(rho),
        "abs_partial_spearman_rho": format_float(abs(rho) if np.isfinite(rho) else float("nan")),
        "n_samples": str(n_samples),
        "expected_sign": expected_sign,
        "observed_sign": observed_sign,
        "expected_sign_match": sign_match,
        "effect_size_threshold": format_float(float(effect_size_threshold)),
        "passes_effect_size": str(passes_effect).lower(),
        "substantive_validity_status": substantive,
        "interpretation": partial_interpretation(metric, target, substantive),
    }
    return {
        "row": row,
        "metric_residual": metric_residual,
        "target_residual": target_residual,
        "ranked_metric": ranked[metric],
        "ranked_target": ranked[target],
        "control_matrix": control_matrix,
        "group_labels": [str(item.get("sequence_id", "")) for item in rows],
        "metric_status": metric_status,
        "target_status": target_status,
        "rank": max(rank_metric, rank_target),
    }


def compute_expected_sign_check(expected_sign: str, rho: float) -> str:
    if expected_sign not in {"positive", "negative"} or not np.isfinite(rho) or abs(rho) <= 1.0e-12:
        return "undefined"
    if expected_sign == "positive":
        return str(rho > 0.0).lower()
    return str(rho < 0.0).lower()


def run_within_sequence_permutation_tests(
    analyses: Sequence[Mapping[str, Any]],
    n_permutations: int,
    seed: int,
) -> List[Dict[str, str]]:
    """Permutation screen by shuffling metric residuals within sequence labels."""

    outputs: List[Dict[str, str]] = []
    for index, analysis in enumerate(analyses):
        row = analysis["row"]
        metric_residual = np.asarray(analysis["metric_residual"], dtype=float)
        target_residual = np.asarray(analysis["target_residual"], dtype=float)
        labels = np.asarray(analysis["group_labels"], dtype=object)
        observed = abs(to_float(row["partial_spearman_rho"]))
        local_seed = int(seed) + stable_index(row["metric_name"], row["target_name"], row["scope"], row["sequence_id"], index)
        p_value = float("nan")
        passes = "undefined"
        interpretation = "undefined permutation screen"
        finite = np.isfinite(metric_residual) & np.isfinite(target_residual)
        if np.isfinite(observed) and int(n_permutations) > 0 and int(np.sum(finite)) >= 6:
            rng = np.random.default_rng(local_seed)
            count = 0
            usable = 0
            for _ in range(int(n_permutations)):
                shuffled = metric_residual.copy()
                for label in sorted(set(labels[finite])):
                    idx = np.flatnonzero(finite & (labels == label))
                    if idx.size > 1:
                        shuffled[idx] = shuffled[rng.permutation(idx)]
                permuted = abs(residual_correlation(shuffled, target_residual))
                if np.isfinite(permuted):
                    usable += 1
                    if permuted >= observed - 1.0e-12:
                        count += 1
            if usable > 0:
                p_value = float((count + 1) / (usable + 1))
                passes = str(p_value <= 0.05).lower()
                interpretation = "permutation screen passed" if passes == "true" else "permutation screen did not pass"
        outputs.append(
            {
                "metric_name": row["metric_name"],
                "target_name": row["target_name"],
                "scope": row["scope"],
                "sequence_id": row["sequence_id"],
                "observed_abs_partial_rho": format_float(observed),
                "permutation_p_value": format_float(p_value),
                "n_permutations": str(int(n_permutations)),
                "seed": str(local_seed),
                "passes_permutation_screen": passes,
                "interpretation": interpretation,
            }
        )
    return outputs


def compute_controlled_regression_summary(analyses: Sequence[Mapping[str, Any]]) -> List[Dict[str, str]]:
    """Fit target rank on metric rank plus controls for each analysis."""

    rows: List[Dict[str, str]] = []
    for analysis in analyses:
        row = analysis["row"]
        metric = np.asarray(analysis["ranked_metric"], dtype=float)
        target = np.asarray(analysis["ranked_target"], dtype=float)
        controls = np.asarray(analysis["control_matrix"], dtype=float)
        finite = np.isfinite(metric) & np.isfinite(target) & np.all(np.isfinite(controls), axis=1)
        coefficient = float("nan")
        standardized = float("nan")
        if int(np.sum(finite)) >= 6 and finite_variation(metric[finite]) > 1.0e-12 and finite_variation(target[finite]) > 1.0e-12:
            x = np.column_stack([np.ones(int(np.sum(finite))), metric[finite], controls[finite]])
            x = select_independent_columns(x)
            beta, *_ = np.linalg.lstsq(x, target[finite], rcond=None)
            coefficient = float(beta[1]) if beta.size > 1 else float("nan")
            standardized = coefficient * safe_std(metric[finite]) / max(safe_std(target[finite]), 1.0e-12)
        rows.append(
            {
                "target_name": row["target_name"],
                "metric_name": row["metric_name"],
                "control_set": row["control_set"],
                "coefficient": format_float(coefficient),
                "standardized_coefficient": format_float(standardized),
                "residual_rho": row["partial_spearman_rho"],
                "n_samples": row["n_samples"],
                "expected_sign_match": row["expected_sign_match"],
                "interpretation": "controlled least-squares coefficient; use with partial rho and permutation screen",
            }
        )
    return rows


def compute_incremental_validity_summary(
    partial_rows: Sequence[Mapping[str, str]],
    permutation_rows: Sequence[Mapping[str, str]],
    metrics: Sequence[str],
    targets: Sequence[str],
) -> List[Dict[str, str]]:
    """Summarize strict Day 20 incremental validity decisions."""

    permutation_by_key = {
        (row["metric_name"], row["target_name"], row["scope"], row["sequence_id"]): row for row in permutation_rows
    }
    outputs: List[Dict[str, str]] = []
    for target in targets:
        merged = {
            row["metric_name"]: row
            for row in partial_rows
            if row["target_name"] == target and row["scope"] == "merged_controlled"
        }
        best_abs = max(
            [to_float(row["abs_partial_spearman_rho"]) for row in merged.values() if np.isfinite(to_float(row["abs_partial_spearman_rho"]))],
            default=float("nan"),
        )
        for metric in metrics:
            row = merged.get(metric)
            if row is None:
                continue
            perm = permutation_by_key.get((metric, target, "merged_controlled", "ALL"), {})
            passes_expected = row["expected_sign_match"] == "true"
            passes_effect = row["passes_effect_size"] == "true"
            passes_perm = perm.get("passes_permutation_screen") == "true"
            abs_rho = to_float(row["abs_partial_spearman_rho"])
            beats = np.isfinite(abs_rho) and np.isfinite(best_abs) and abs_rho >= best_abs - 1.0e-12
            passes_incremental = bool(passes_expected and passes_effect and passes_perm)
            status = "candidate_supported" if passes_incremental and beats else "exploratory_not_validated"
            reason = incremental_reason(metric, passes_expected, passes_effect, passes_perm, beats)
            outputs.append(
                {
                    "metric_name": metric,
                    "target_name": target,
                    "passes_expected_sign": str(passes_expected).lower(),
                    "passes_effect_size": str(passes_effect).lower(),
                    "passes_permutation": str(passes_perm).lower(),
                    "passes_incremental_validity": str(passes_incremental).lower(),
                    "beats_or_matches_baselines": str(beats).lower(),
                    "final_day20_status": status,
                    "reason": reason,
                }
            )
    return outputs


def write_day20_manifest(
    path: Path,
    *,
    config: Mapping[str, Any],
    inputs: Sequence[Path],
    outputs: Sequence[Path],
    incremental_rows: Sequence[Mapping[str, str]],
    runtime_seconds: float,
) -> Dict[str, Any]:
    missing = [relative_to_root(output) for output in outputs if output != path and not output.exists()]
    odi_axis = find_incremental(incremental_rows, "ODI_median", "axis_drift_rate")
    manifest = {
        "status": "OK" if incremental_rows and not missing else "FAILED",
        "git_commit": git_commit(),
        "source_validation": config.get("source_validation", "day18_day19"),
        "inputs": [relative_to_root(path) for path in inputs],
        "outputs": [relative_to_root(path) for path in outputs],
        "n_metrics": len(config.get("metrics", DEFAULT_METRICS)),
        "n_targets": len(config.get("targets", DEFAULT_TARGETS)),
        "effect_size_threshold": float(config.get("effect_size_threshold", 0.10)),
        "n_permutations": int(config.get("n_permutations", 200)),
        "odi_day20_status": odi_axis.get("final_day20_status", "missing"),
        "day20_analysis_passed": bool(incremental_rows and not missing),
        "missing_artifacts": missing,
        "runtime_seconds": round(float(runtime_seconds), 6),
        "interpretation": "analysis chain passed; this does not authorize weak-subspace update by itself",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def build_partial_analyses(
    window_rows: Sequence[Mapping[str, str]],
    config: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    metrics = list(config.get("metrics", DEFAULT_METRICS))
    targets = list(config.get("targets", DEFAULT_TARGETS))
    controls = list(config.get("controls", []))
    group_controls = list(config.get("group_controls", []))
    expected = config.get("expected_sign", {})
    threshold = float(config.get("effect_size_threshold", 0.10))
    analyses: List[Dict[str, Any]] = []
    for target in targets:
        for metric in metrics:
            analyses.append(
                compute_partial_spearman(
                    window_rows,
                    metric,
                    target,
                    controls,
                    group_controls,
                    expected,
                    threshold,
                    scope="merged_controlled",
                )
            )
            for sequence_id in sorted({row["sequence_id"] for row in window_rows}):
                seq_rows = [row for row in window_rows if row["sequence_id"] == sequence_id]
                scene_family = seq_rows[0].get("scene_family", "unknown")
                analyses.append(
                    compute_partial_spearman(
                        seq_rows,
                        metric,
                        target,
                        controls,
                        group_controls,
                        expected,
                        threshold,
                        scope="within_sequence_controlled",
                        sequence_id=sequence_id,
                        scene_family=scene_family,
                    )
                )
    return analyses


def build_control_matrix(
    rows: Sequence[Mapping[str, str]],
    ranked: Mapping[str, np.ndarray],
    numeric_controls: Sequence[str],
    group_controls: Sequence[str],
) -> np.ndarray:
    columns: List[np.ndarray] = []
    for control in numeric_controls:
        if control in ranked:
            columns.append(np.asarray(ranked[control], dtype=float))
    for control in group_controls:
        values = [str(row.get(control, "")) for row in rows]
        categories = sorted(set(values))
        for category in categories[1:]:
            columns.append(np.asarray([1.0 if value == category else 0.0 for value in values], dtype=float))
    if not columns:
        return np.zeros((len(rows), 0), dtype=float)
    return np.column_stack(columns)


def residual_correlation(x: np.ndarray, y: np.ndarray) -> float:
    finite = np.isfinite(x) & np.isfinite(y)
    if int(np.sum(finite)) < 3:
        return float("nan")
    x_fit = x[finite]
    y_fit = y[finite]
    if finite_variation(x_fit) <= 1.0e-12 or finite_variation(y_fit) <= 1.0e-12:
        return float("nan")
    return float(np.corrcoef(x_fit, y_fit)[0, 1])


def select_independent_columns(matrix: np.ndarray, tol: float = 1.0e-10) -> np.ndarray:
    selected: List[int] = []
    rank = 0
    for idx in range(matrix.shape[1]):
        candidate = matrix[:, selected + [idx]]
        candidate_rank = int(np.linalg.matrix_rank(candidate, tol=tol))
        if candidate_rank > rank:
            selected.append(idx)
            rank = candidate_rank
    return matrix[:, selected] if selected else np.zeros((matrix.shape[0], 0), dtype=float)


def pick_undefined_status(metric_status: str, target_status: str) -> str:
    for status in [metric_status, target_status]:
        if status != "ok":
            if status == "undefined_constant_target":
                return "undefined_singular_controls"
            return status
    return "undefined"


def partial_interpretation(metric: str, target: str, status: str) -> str:
    if status == "substantive_candidate":
        return f"{metric} retains controlled association with {target}; still requires Day 21 joint-risk context"
    if status == "exploratory_small_or_wrong_sign":
        if metric == "ODI_median":
            return "ODI remains exploratory and is not validated for robust drift prediction."
        return "controlled rho is small or expected sign does not match; not substantive evidence"
    if status == "undefined_insufficient_samples":
        return "not enough samples after finite filtering and controls"
    if status == "undefined_singular_controls":
        return "control residualization is singular or removes usable variation"
    return "undefined controlled partial association"


def incremental_reason(metric: str, expected: bool, effect: bool, permutation: bool, beats: bool) -> str:
    missing = []
    if not expected:
        missing.append("expected_sign")
    if not effect:
        missing.append("effect_size")
    if not permutation:
        missing.append("permutation")
    if not beats:
        missing.append("baseline_comparison")
    if not missing:
        return "passes controlled Day 20 screen; still needs joint risk analysis"
    if metric == "ODI_median":
        return "ODI remains exploratory and is not validated for robust drift prediction. Missing: " + ", ".join(missing)
    return "does not pass controlled Day 20 screen. Missing: " + ", ".join(missing)


def observed_sign_from_rho(rho: float) -> str:
    if not np.isfinite(rho) or abs(rho) <= 1.0e-12:
        return "undefined"
    return "positive" if rho > 0.0 else "negative"


def stable_index(*parts: object) -> int:
    text = "|".join(str(part) for part in parts)
    total = 0
    for char in text:
        total = (total * 131 + ord(char)) % 1_000_003
    return total


def find_incremental(rows: Sequence[Mapping[str, str]], metric: str, target: str) -> Mapping[str, str]:
    for row in rows:
        if row["metric_name"] == metric and row["target_name"] == target:
            return row
    return {}


def finite_variation(values: Iterable[float]) -> float:
    array = np.asarray(list(values), dtype=float)
    finite = array[np.isfinite(array)]
    if finite.size == 0:
        return float("nan")
    return float(np.max(finite) - np.min(finite))


def safe_std(values: Iterable[float]) -> float:
    array = np.asarray(list(values), dtype=float)
    finite = array[np.isfinite(array)]
    if finite.size <= 1:
        return float("nan")
    return float(np.std(finite))


def write_csv(path: Path, fieldnames: Sequence[str], rows: Sequence[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


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
