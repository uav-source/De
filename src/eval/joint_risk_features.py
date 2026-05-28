"""Day 21 interpretable joint-risk feature analysis."""

from __future__ import annotations

import csv
import json
import statistics
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

import numpy as np

from eval.controlled_partial_validity import (
    residual_correlation,
    residualize_against_controls,
    select_independent_columns,
    stable_index,
)
from eval.stats import rankdata_average, spearman_corr


ROOT = Path(__file__).resolve().parents[2]
BASE_RISK_COMPONENTS = [
    "risk_ODI",
    "risk_low_AIS",
    "risk_low_lambda",
    "risk_high_condition",
    "risk_weak_alignment",
    "risk_low_motion",
]
DEFAULT_JOINT_FEATURES = [
    "joint_risk_equal",
    "joint_risk_spectral",
    "joint_risk_information",
    "joint_risk_odi_information",
    "joint_risk_no_odi",
    "joint_risk_motion_aware",
]
DEFAULT_TARGETS = ["axis_drift_rate", "weak_drift_alignment"]

FEATURE_FIELDNAMES = [
    "sequence_id",
    "scene_family",
    "trial_id",
    "window_id",
    "axis_drift_rate",
    "weak_drift_alignment",
    "ODI_median",
    "AIS_median",
    "lambda_min_clamped_median",
    "condition_number_median",
    "weak_alignment_median",
    "path_length",
    "risk_ODI",
    "risk_low_AIS",
    "risk_low_lambda",
    "risk_high_condition",
    "risk_weak_alignment",
    "risk_low_motion",
    "joint_risk_equal",
    "joint_risk_spectral",
    "joint_risk_information",
    "joint_risk_odi_information",
    "joint_risk_no_odi",
    "joint_risk_motion_aware",
    "applied_axis_bias",
    "is_unbiased_protocol",
]

CORRELATION_FIELDNAMES = [
    "feature_name",
    "target_name",
    "scope",
    "sequence_id",
    "scene_family",
    "spearman_rho",
    "abs_spearman_rho",
    "n_samples",
    "expected_sign",
    "observed_sign",
    "expected_sign_match",
    "effect_size_threshold",
    "passes_effect_size",
    "validity_status",
    "interpretation",
]

CONTROLLED_FIELDNAMES = [
    "feature_name",
    "target_name",
    "control_set",
    "scope",
    "partial_spearman_rho",
    "abs_partial_spearman_rho",
    "n_samples",
    "expected_sign_match",
    "passes_effect_size",
    "permutation_p_value",
    "passes_permutation",
    "controlled_validity_status",
    "interpretation",
]

COMPARISON_FIELDNAMES = [
    "feature_name",
    "target_name",
    "merged_abs_rho",
    "mean_within_sequence_abs_rho",
    "controlled_abs_partial_rho",
    "permutation_p_value",
    "beats_single_metrics",
    "beats_no_odi_baseline",
    "final_day21_status",
    "reason",
]


def load_day21_inputs(day30_root: Path) -> Dict[str, Any]:
    """Read Day 18 and Day 20 inputs for joint-risk analysis."""

    paths = {
        "window_metrics": day30_root / "tables/day18_window_metrics.csv",
        "day20_partial": day30_root / "tables/day20_partial_correlations.csv",
        "day20_incremental": day30_root / "tables/day20_incremental_validity_summary.csv",
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing required Day21 input file(s): "
            + "; ".join(missing)
            + ". Run Day 18 and Day 20 validation before Day 21."
        )
    tables = {name: read_csv_rows(path) for name, path in paths.items()}
    empty = [name for name, rows in tables.items() if not rows]
    if empty:
        raise ValueError(f"Day21 input table(s) are empty: {', '.join(empty)}")
    tables["input_paths"] = list(paths.values())
    return tables


def rank_percentile_normalize(values: Iterable[float]) -> np.ndarray:
    """Return finite rank percentiles in [0, 1], preserving NaN positions."""

    array = np.asarray(list(values), dtype=float)
    output = np.full(array.shape, np.nan, dtype=float)
    finite = np.isfinite(array)
    count = int(np.sum(finite))
    if count == 0:
        return output
    if count == 1 or finite_variation(array[finite]) <= 1.0e-12:
        output[finite] = 0.5
        return output
    ranks = rankdata_average(array[finite])
    output[finite] = (ranks - 1.0) / (count - 1.0)
    return output


def compute_base_risk_components(window_rows: Sequence[Mapping[str, str]]) -> Dict[str, np.ndarray]:
    """Compute interpretable base risk components from Day 18 windows."""

    odi = np.asarray([to_float(row.get("ODI_median")) for row in window_rows], dtype=float)
    ais = np.asarray([to_float(row.get("AIS_median")) for row in window_rows], dtype=float)
    lambda_min = np.asarray([to_float(row.get("lambda_min_clamped_median")) for row in window_rows], dtype=float)
    condition = np.asarray([to_float(row.get("condition_number_median")) for row in window_rows], dtype=float)
    weak = np.asarray([to_float(row.get("weak_alignment_median")) for row in window_rows], dtype=float)
    path_length = np.asarray([to_float(row.get("path_length")) for row in window_rows], dtype=float)
    log_condition = np.where(np.isfinite(condition), np.log1p(np.maximum(condition, 0.0)), np.nan)
    return {
        "risk_ODI": rank_percentile_normalize(odi),
        "risk_low_AIS": 1.0 - rank_percentile_normalize(ais),
        "risk_low_lambda": 1.0 - rank_percentile_normalize(lambda_min),
        "risk_high_condition": rank_percentile_normalize(log_condition),
        "risk_weak_alignment": rank_percentile_normalize(weak),
        "risk_low_motion": 1.0 - rank_percentile_normalize(path_length),
    }


def compute_joint_risk_features(
    window_rows: Sequence[Mapping[str, str]],
    risk_components: Mapping[str, np.ndarray] | None = None,
) -> List[Dict[str, str]]:
    """Attach base risk components and fixed joint-risk formulas to each window."""

    components = dict(risk_components or compute_base_risk_components(window_rows))
    joint = {
        "joint_risk_equal": mean_nan_safe(
            [components["risk_ODI"], components["risk_low_AIS"], components["risk_low_lambda"], components["risk_high_condition"]]
        ),
        "joint_risk_spectral": mean_nan_safe(
            [components["risk_ODI"], components["risk_low_lambda"], components["risk_high_condition"]]
        ),
        "joint_risk_information": mean_nan_safe(
            [components["risk_low_AIS"], components["risk_low_lambda"], components["risk_high_condition"]]
        ),
        "joint_risk_odi_information": mean_nan_safe(
            [components["risk_ODI"], components["risk_low_AIS"], components["risk_low_lambda"]]
        ),
        "joint_risk_no_odi": mean_nan_safe(
            [
                components["risk_low_AIS"],
                components["risk_low_lambda"],
                components["risk_high_condition"],
                components["risk_low_motion"],
            ]
        ),
        "joint_risk_motion_aware": mean_nan_safe(
            [
                components["risk_ODI"],
                components["risk_low_AIS"],
                components["risk_low_lambda"],
                components["risk_high_condition"],
                components["risk_low_motion"],
            ]
        ),
    }
    rows: List[Dict[str, str]] = []
    for idx, row in enumerate(window_rows):
        output = {field: str(row.get(field, "")) for field in FEATURE_FIELDNAMES if field in row}
        for key, values in components.items():
            output[key] = format_float(float(values[idx]))
        for key, values in joint.items():
            output[key] = format_float(float(values[idx]))
        rows.append(output)
    return rows


def compute_joint_risk_correlations(
    feature_rows: Sequence[Mapping[str, str]],
    features: Sequence[str],
    targets: Sequence[str],
    expected_sign: Mapping[str, Mapping[str, str]],
    effect_size_threshold: float,
) -> List[Dict[str, str]]:
    """Compute merged and within-sequence Spearman checks for risk features."""

    rows: List[Dict[str, str]] = []
    for target in targets:
        for feature in features:
            rows.append(
                correlation_row(
                    feature_rows,
                    feature,
                    target,
                    "merged",
                    "ALL",
                    "ALL",
                    expected_sign,
                    effect_size_threshold,
                )
            )
            for sequence_id in sorted({row["sequence_id"] for row in feature_rows}):
                seq_rows = [row for row in feature_rows if row["sequence_id"] == sequence_id]
                scene_family = seq_rows[0].get("scene_family", "unknown")
                rows.append(
                    correlation_row(
                        seq_rows,
                        feature,
                        target,
                        "within_sequence",
                        sequence_id,
                        scene_family,
                        expected_sign,
                        effect_size_threshold,
                    )
                )
    return rows


def compute_joint_risk_controlled_validity(
    feature_rows: Sequence[Mapping[str, str]],
    features: Sequence[str],
    targets: Sequence[str],
    expected_sign: Mapping[str, Mapping[str, str]],
    effect_size_threshold: float,
    n_permutations: int,
    seed: int,
) -> List[Dict[str, str]]:
    """Residualize joint risk against no-ODI / base components and run permutation screen."""

    rows: List[Dict[str, str]] = []
    for target in targets:
        for feature in features:
            control_names = controlled_feature_controls(feature)
            analysis = controlled_analysis(
                feature_rows,
                feature,
                target,
                control_names,
                expected_sign,
                effect_size_threshold,
                n_permutations,
                seed,
            )
            rows.append(analysis)
    return rows


def compare_joint_risk_with_single_metrics(
    correlation_rows: Sequence[Mapping[str, str]],
    controlled_rows: Sequence[Mapping[str, str]],
    features: Sequence[str],
    targets: Sequence[str],
    effect_size_threshold: float,
) -> List[Dict[str, str]]:
    """Compare joint-risk features against single components and no-ODI baseline."""

    outputs: List[Dict[str, str]] = []
    merged = {
        (row["feature_name"], row["target_name"]): row
        for row in correlation_rows
        if row["scope"] == "merged"
    }
    controlled = {(row["feature_name"], row["target_name"]): row for row in controlled_rows}
    for target in targets:
        single_best = max(
            [
                to_float(merged.get((feature, target), {}).get("abs_spearman_rho"))
                for feature in BASE_RISK_COMPONENTS
            ],
            default=float("nan"),
        )
        no_odi_abs = to_float(merged.get(("joint_risk_no_odi", target), {}).get("abs_spearman_rho"))
        for feature in features:
            mrow = merged.get((feature, target), {})
            crow = controlled.get((feature, target), {})
            merged_abs = to_float(mrow.get("abs_spearman_rho"))
            controlled_abs = to_float(crow.get("abs_partial_spearman_rho"))
            within_abs = mean_within_abs(correlation_rows, feature, target)
            perm_p = to_float(crow.get("permutation_p_value"))
            beats_single = np.isfinite(merged_abs) and np.isfinite(single_best) and merged_abs >= single_best - 1.0e-12
            if feature == "joint_risk_no_odi":
                beats_no_odi = True
            else:
                beats_no_odi = np.isfinite(merged_abs) and np.isfinite(no_odi_abs) and merged_abs >= no_odi_abs - 1.0e-12
            expected_ok = mrow.get("expected_sign_match") == "true"
            effect_ok = (
                (mrow.get("passes_effect_size") == "true")
                or (np.isfinite(controlled_abs) and controlled_abs >= float(effect_size_threshold))
            )
            perm_ok = crow.get("passes_permutation") == "true"
            consistent = consistency_count(correlation_rows, feature, target) >= 2 or expected_ok
            supported = bool(expected_ok and effect_ok and perm_ok and beats_single and beats_no_odi and consistent)
            outputs.append(
                {
                    "feature_name": feature,
                    "target_name": target,
                    "merged_abs_rho": format_float(merged_abs),
                    "mean_within_sequence_abs_rho": format_float(within_abs),
                    "controlled_abs_partial_rho": format_float(controlled_abs),
                    "permutation_p_value": format_float(perm_p),
                    "beats_single_metrics": str(beats_single).lower(),
                    "beats_no_odi_baseline": str(beats_no_odi).lower(),
                    "final_day21_status": "candidate_supported" if supported else "exploratory_not_validated",
                    "reason": comparison_reason(feature, expected_ok, effect_ok, perm_ok, beats_single, beats_no_odi, consistent),
                }
            )
    return outputs


def write_day21_manifest(
    path: Path,
    *,
    config: Mapping[str, Any],
    inputs: Sequence[Path],
    outputs: Sequence[Path],
    comparison_rows: Sequence[Mapping[str, str]],
    runtime_seconds: float,
) -> Dict[str, Any]:
    missing = [relative_to_root(output) for output in outputs if output != path and not output.exists()]
    best = best_joint_feature(comparison_rows)
    weak_update_authorized = False
    manifest = {
        "status": "OK" if comparison_rows and not missing else "FAILED",
        "git_commit": git_commit(),
        "source_validation": config.get("source_validation", "day18_day20"),
        "inputs": [relative_to_root(path) for path in inputs],
        "outputs": [relative_to_root(path) for path in outputs],
        "n_features": len(config.get("risk_features", DEFAULT_JOINT_FEATURES)),
        "n_targets": len(config.get("targets", DEFAULT_TARGETS)),
        "effect_size_threshold": float(config.get("effect_size_threshold", 0.10)),
        "n_permutations": int(config.get("n_permutations", 200)),
        "best_joint_risk_feature": best.get("feature_name", "none"),
        "best_joint_risk_status": best.get("final_day21_status", "none"),
        "day21_analysis_passed": bool(comparison_rows and not missing),
        "weak_update_authorized": weak_update_authorized,
        "missing_artifacts": missing,
        "runtime_seconds": round(float(runtime_seconds), 6),
        "interpretation": "joint risk screened only; Day 22 gate review is required before any method update",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def correlation_row(
    rows: Sequence[Mapping[str, str]],
    feature: str,
    target: str,
    scope: str,
    sequence_id: str,
    scene_family: str,
    expected_sign: Mapping[str, Mapping[str, str]],
    effect_size_threshold: float,
) -> Dict[str, str]:
    feature_values = [to_float(row.get(feature)) for row in rows]
    target_values = [to_float(row.get(target)) for row in rows]
    finite = finite_pair(feature_values, target_values)
    n = len(finite[0])
    rho = float("nan")
    status = "undefined_insufficient_samples"
    if n >= 3 and finite_variation(finite[0]) > 1.0e-12 and finite_variation(finite[1]) > 1.0e-12:
        rho, _ = spearman_corr(feature_values, target_values)
        status = "computable"
    elif n >= 3:
        status = "undefined_constant_feature_or_target"
    expected = str(expected_sign.get(feature, {}).get(target, "positive"))
    observed = observed_sign_from_rho(rho)
    sign_match = expected_sign_match(expected, rho)
    passes_effect = bool(np.isfinite(rho) and abs(rho) >= float(effect_size_threshold))
    if status == "computable" and sign_match == "true" and passes_effect:
        validity = "substantive_candidate"
    elif status == "computable":
        validity = "exploratory_small_or_wrong_sign"
    else:
        validity = status
    return {
        "feature_name": feature,
        "target_name": target,
        "scope": scope,
        "sequence_id": sequence_id,
        "scene_family": scene_family,
        "spearman_rho": format_float(rho),
        "abs_spearman_rho": format_float(abs(rho) if np.isfinite(rho) else float("nan")),
        "n_samples": str(n),
        "expected_sign": expected,
        "observed_sign": observed,
        "expected_sign_match": sign_match,
        "effect_size_threshold": format_float(float(effect_size_threshold)),
        "passes_effect_size": str(passes_effect).lower(),
        "validity_status": validity,
        "interpretation": correlation_interpretation(feature, validity),
    }


def controlled_analysis(
    rows: Sequence[Mapping[str, str]],
    feature: str,
    target: str,
    control_names: Sequence[str],
    expected_sign: Mapping[str, Mapping[str, str]],
    effect_size_threshold: float,
    n_permutations: int,
    seed: int,
) -> Dict[str, str]:
    feature_values = np.asarray([to_float(row.get(feature)) for row in rows], dtype=float)
    target_values = np.asarray([to_float(row.get(target)) for row in rows], dtype=float)
    controls = np.column_stack([[to_float(row.get(name)) for row in rows] for name in control_names]) if control_names else np.zeros((len(rows), 0))
    feature_residual, feature_status, n_feature, _ = residualize_against_controls(feature_values, controls, prune_degenerate=True)
    target_residual, target_status, n_target, _ = residualize_against_controls(target_values, controls, prune_degenerate=True)
    n = int(min(n_feature, n_target))
    rho = float("nan")
    status = "computable"
    if feature_status != "ok" or target_status != "ok":
        status = pick_status(feature_status, target_status)
    else:
        rho = residual_correlation(feature_residual, target_residual)
        if not np.isfinite(rho):
            status = "undefined_singular_controls"
    expected = str(expected_sign.get(feature, {}).get(target, "positive"))
    sign_match = expected_sign_match(expected, rho)
    passes_effect = bool(np.isfinite(rho) and abs(rho) >= float(effect_size_threshold))
    p_value, perm_pass = permutation_screen(feature_residual, target_residual, rows, n_permutations, seed, feature, target)
    validity = (
        "controlled_candidate"
        if status == "computable" and sign_match == "true" and passes_effect and perm_pass == "true"
        else status if status != "computable" else "exploratory_small_or_wrong_sign"
    )
    return {
        "feature_name": feature,
        "target_name": target,
        "control_set": "+".join(control_names) if control_names else "none",
        "scope": "merged_controlled",
        "partial_spearman_rho": format_float(rho),
        "abs_partial_spearman_rho": format_float(abs(rho) if np.isfinite(rho) else float("nan")),
        "n_samples": str(n),
        "expected_sign_match": sign_match,
        "passes_effect_size": str(passes_effect).lower(),
        "permutation_p_value": format_float(p_value),
        "passes_permutation": perm_pass,
        "controlled_validity_status": validity,
        "interpretation": controlled_interpretation(feature, validity),
    }


def permutation_screen(
    feature_residual: np.ndarray,
    target_residual: np.ndarray,
    rows: Sequence[Mapping[str, str]],
    n_permutations: int,
    seed: int,
    feature: str,
    target: str,
) -> tuple[float, str]:
    observed = abs(residual_correlation(feature_residual, target_residual))
    finite = np.isfinite(feature_residual) & np.isfinite(target_residual)
    if not np.isfinite(observed) or int(np.sum(finite)) < 6 or int(n_permutations) <= 0:
        return float("nan"), "undefined"
    labels = np.asarray([row.get("sequence_id", "") for row in rows], dtype=object)
    rng = np.random.default_rng(int(seed) + stable_index(feature, target, "day21"))
    count = 0
    usable = 0
    for _ in range(int(n_permutations)):
        shuffled = feature_residual.copy()
        for label in sorted(set(labels[finite])):
            idx = np.flatnonzero(finite & (labels == label))
            if idx.size > 1:
                shuffled[idx] = shuffled[rng.permutation(idx)]
        permuted = abs(residual_correlation(shuffled, target_residual))
        if np.isfinite(permuted):
            usable += 1
            if permuted >= observed - 1.0e-12:
                count += 1
    if usable == 0:
        return float("nan"), "undefined"
    p_value = float((count + 1) / (usable + 1))
    return p_value, str(p_value <= 0.05).lower()


def controlled_feature_controls(feature: str) -> List[str]:
    if feature == "joint_risk_no_odi":
        return ["risk_ODI", "risk_weak_alignment"]
    controls = ["joint_risk_no_odi", "risk_low_AIS", "risk_low_lambda", "risk_high_condition", "risk_low_motion"]
    if "motion" not in feature:
        controls.append("risk_weak_alignment")
    return [control for control in controls if control != feature]


def mean_nan_safe(arrays: Sequence[np.ndarray]) -> np.ndarray:
    stack = np.vstack([np.asarray(array, dtype=float) for array in arrays])
    valid = np.isfinite(stack)
    sums = np.nansum(stack, axis=0)
    counts = np.sum(valid, axis=0)
    output = np.full(stack.shape[1], np.nan, dtype=float)
    mask = counts > 0
    output[mask] = sums[mask] / counts[mask]
    return output


def mean_within_abs(rows: Sequence[Mapping[str, str]], feature: str, target: str) -> float:
    values = [
        to_float(row["abs_spearman_rho"])
        for row in rows
        if row["feature_name"] == feature and row["target_name"] == target and row["scope"] == "within_sequence"
    ]
    finite = [value for value in values if np.isfinite(value)]
    return float(statistics.fmean(finite)) if finite else float("nan")


def consistency_count(rows: Sequence[Mapping[str, str]], feature: str, target: str) -> int:
    return sum(
        row["expected_sign_match"] == "true"
        and row["passes_effect_size"] == "true"
        for row in rows
        if row["feature_name"] == feature and row["target_name"] == target and row["scope"] == "within_sequence"
    )


def comparison_reason(
    feature: str,
    expected_ok: bool,
    effect_ok: bool,
    permutation_ok: bool,
    beats_single: bool,
    beats_no_odi: bool,
    consistent: bool,
) -> str:
    missing = []
    if not expected_ok:
        missing.append("expected_sign")
    if not effect_ok:
        missing.append("effect_size")
    if not permutation_ok:
        missing.append("permutation")
    if not beats_single:
        missing.append("single_metric_comparison")
    if not beats_no_odi:
        missing.append("no_odi_baseline")
    if not consistent:
        missing.append("within_sequence_consistency")
    if not missing:
        return "candidate joint risk support; Day 22 gate review still required"
    return "joint risk remains exploratory and does not authorize weak-subspace update. Missing: " + ", ".join(missing)


def best_joint_feature(comparison_rows: Sequence[Mapping[str, str]]) -> Mapping[str, str]:
    candidates = [row for row in comparison_rows if row["final_day21_status"] == "candidate_supported"]
    if not candidates:
        finite = [row for row in comparison_rows if np.isfinite(to_float(row.get("controlled_abs_partial_rho")))]
        if not finite:
            return {}
        return sorted(finite, key=lambda row: (-to_float(row["controlled_abs_partial_rho"]), row["feature_name"]))[0]
    return sorted(candidates, key=lambda row: (-to_float(row["controlled_abs_partial_rho"]), row["feature_name"]))[0]


def correlation_interpretation(feature: str, status: str) -> str:
    if status == "substantive_candidate":
        return f"{feature} has signed effect-size support; controlled screen still required"
    if status == "exploratory_small_or_wrong_sign":
        return "small rho or expected-sign mismatch; not substantive evidence"
    return "undefined or insufficient feature-target variation"


def controlled_interpretation(feature: str, status: str) -> str:
    if status == "controlled_candidate":
        return f"{feature} passes controlled screen; Day 22 gate review still required"
    if status == "exploratory_small_or_wrong_sign":
        return "controlled association is small, sign-mismatched, or permutation did not pass"
    return "controlled association undefined"


def expected_sign_match(expected: str, rho: float) -> str:
    if expected not in {"positive", "negative"} or not np.isfinite(rho) or abs(rho) <= 1.0e-12:
        return "undefined"
    return str((rho > 0.0) if expected == "positive" else (rho < 0.0)).lower()


def observed_sign_from_rho(rho: float) -> str:
    if not np.isfinite(rho) or abs(rho) <= 1.0e-12:
        return "undefined"
    return "positive" if rho > 0.0 else "negative"


def pick_status(feature_status: str, target_status: str) -> str:
    for status in [feature_status, target_status]:
        if status != "ok":
            return status
    return "undefined"


def finite_pair(x: Iterable[float], y: Iterable[float]) -> tuple[np.ndarray, np.ndarray]:
    x_arr = np.asarray(list(x), dtype=float)
    y_arr = np.asarray(list(y), dtype=float)
    finite = np.isfinite(x_arr) & np.isfinite(y_arr)
    return x_arr[finite], y_arr[finite]


def finite_variation(values: Iterable[float]) -> float:
    array = np.asarray(list(values), dtype=float)
    finite = array[np.isfinite(array)]
    if finite.size == 0:
        return float("nan")
    return float(np.max(finite) - np.min(finite))


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
