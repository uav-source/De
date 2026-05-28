"""Bias-audit helpers for the Day 15 review."""

from __future__ import annotations

import ast
import csv
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TOY_LIO_PATH = ROOT / "src/minibench/toy_lio.py"
SEQUENCE_FAMILIES = {
    "OC-L0-S01-M1": "OC",
    "ST-L3-S01-M1": "ST",
    "CT-L2-S01-M2": "CT",
    "RT-L4-S01-M1": "RT",
}
PROCESS_NOISE_FIELDS = {"axis_bias", "axis_sigma", "cross_sigma", "yaw_sigma"}


def inspect_toy_lio_bias_config(path: str | Path = DEFAULT_TOY_LIO_PATH) -> Dict[str, Any]:
    """Inspect legacy toy_lio process-noise branches without executing toy_lio."""

    toy_lio_path = Path(path)
    source = toy_lio_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    explicit_axis_bias = _find_literal_mapping(tree, "LEGACY_AXIS_BIAS_BY_FAMILY")
    explicit_noise = _find_literal_mapping(tree, "LEGACY_NOISE_BY_FAMILY")
    if explicit_axis_bias:
        axis_bias_by_family = {str(key): float(value) for key, value in explicit_axis_bias.items()}
        unique_biases = {round(value, 12) for value in axis_bias_by_family.values()}
        return {
            "source_path": str(toy_lio_path),
            "sample_process_noise_found": _find_function(tree, "sample_process_noise") is not None,
            "uses_scene_family_branch": True,
            "scene_family_dependent_axis_bias": len(unique_biases) > 1,
            "axis_bias_by_family": axis_bias_by_family,
            "noise_by_family": explicit_noise,
            "branch_count": len(axis_bias_by_family),
            "bias_source": "LEGACY_AXIS_BIAS_BY_FAMILY",
        }

    function = _find_function(tree, "sample_process_noise")
    if function is None:
        raise ValueError(f"sample_process_noise() not found in {toy_lio_path}")

    branches: List[Dict[str, Any]] = []
    for statement in function.body:
        if isinstance(statement, ast.If):
            _collect_noise_branches(statement, branches)
            break

    axis_bias_by_family: Dict[str, float] = {}
    noise_by_family: Dict[str, Dict[str, float]] = {}
    for branch in branches:
        family = str(branch["family"])
        values = {key: float(value) for key, value in branch["values"].items()}
        if family == "__else__":
            family = "ST"
        noise_by_family[family] = values
        if "axis_bias" in values:
            axis_bias_by_family[family] = float(values["axis_bias"])

    unique_biases = {round(value, 12) for value in axis_bias_by_family.values()}
    return {
        "source_path": str(toy_lio_path),
        "sample_process_noise_found": True,
        "uses_scene_family_branch": len(branches) > 1,
        "scene_family_dependent_axis_bias": len(unique_biases) > 1,
        "axis_bias_by_family": axis_bias_by_family,
        "noise_by_family": noise_by_family,
        "branch_count": len(branches),
    }


def extract_scene_family_bias(audit_or_path: Mapping[str, Any] | str | Path = DEFAULT_TOY_LIO_PATH) -> Dict[str, float]:
    """Return the legacy axis bias keyed by scene family."""

    if isinstance(audit_or_path, Mapping):
        audit = audit_or_path
    else:
        audit = inspect_toy_lio_bias_config(audit_or_path)
    return {str(key): float(value) for key, value in audit.get("axis_bias_by_family", {}).items()}


def summarize_bias_by_sequence(
    toy_lio_audit: Mapping[str, Any],
    toy_summary_rows: Sequence[Mapping[str, str]] | str | Path,
    metric_summary_rows: Sequence[Mapping[str, str]] | str | Path,
) -> List[Dict[str, str]]:
    """Join legacy bias, toy drift, and Day 8 metrics by sequence."""

    toy_rows = _rows_from_input(toy_summary_rows)
    metric_rows = _rows_from_input(metric_summary_rows)
    toy_by_seq = {row["sequence_id"]: row for row in toy_rows}
    metric_by_seq = {row["sequence_id"]: row for row in metric_rows}
    bias_by_family = extract_scene_family_bias(toy_lio_audit)

    summaries: List[Dict[str, str]] = []
    for sequence_id, scene_family in SEQUENCE_FAMILIES.items():
        toy_row = toy_by_seq.get(sequence_id, {})
        metric_row = metric_by_seq.get(sequence_id, {})
        bias = float(bias_by_family.get(scene_family, 0.0))
        final_axis_error = _first_available_float(
            toy_row.get("final_axis_error"),
            metric_row.get("final_axis_error"),
        )
        odi_median = _first_available_float(metric_row.get("ODI_median"))
        axis_drift_rate = _first_available_float(metric_row.get("axis_drift_rate_median"))
        risk = _sequence_risk_level(bias, final_axis_error, odi_median)
        summaries.append(
            {
                "sequence_id": sequence_id,
                "scene_family": scene_family,
                "legacy_axis_bias": _format_float(bias),
                "final_axis_error": _format_float(final_axis_error),
                "ODI_median": _format_float(odi_median),
                "axis_drift_rate_median": _format_float(axis_drift_rate),
                "confound_risk_level": risk,
                "interpretation": _sequence_interpretation(scene_family, bias, risk),
            }
        )
    return summaries


def flag_scene_family_confound(
    sequence_summaries: Sequence[Mapping[str, str]],
    toy_lio_audit: Mapping[str, Any] | None = None,
) -> Dict[str, str]:
    """Summarize whether legacy axis bias can confound merged metric validity."""

    biases = [_safe_float(row.get("legacy_axis_bias")) for row in sequence_summaries]
    axis_errors = [_safe_float(row.get("final_axis_error")) for row in sequence_summaries]
    odi_values = [_safe_float(row.get("ODI_median")) for row in sequence_summaries]
    nonzero_biases = [value for value in biases if value > 0.0]
    bias_varies = len({round(value, 12) for value in biases}) > 1
    tunnel_bias = bool(nonzero_biases)
    strong_axis_gap = max(axis_errors) > max(min(axis_errors) * 10.0, 0.1) if axis_errors else False
    odi_gap = max(odi_values) - min(odi_values) > 0.1 if odi_values else False
    audit_confirms = bool(toy_lio_audit and toy_lio_audit.get("scene_family_dependent_axis_bias"))

    if bias_varies and tunnel_bias and strong_axis_gap and odi_gap:
        level = "HIGH"
    elif bias_varies and tunnel_bias:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {
        "scene_family_axis_bias_present": str(bool(audit_confirms or (bias_varies and tunnel_bias))).lower(),
        "confound_risk_level": level,
        "reason": (
            "legacy toy_lio injects different axis_bias values by scene family; "
            "tunnel scenes also have larger axis error and higher ODI, so merged correlation can be inflated"
            if level in {"HIGH", "MEDIUM"}
            else "no scene-family axis-bias pattern detected"
        ),
    }


def read_csv_rows(path: str | Path) -> List[Dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _find_function(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _find_literal_mapping(tree: ast.AST, name: str) -> Dict[str, Any]:
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        if node.targets[0].id != name:
            continue
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, SyntaxError):
            return {}
        return value if isinstance(value, dict) else {}
    return {}


def _collect_noise_branches(node: ast.If, branches: List[Dict[str, Any]]) -> None:
    family = _family_from_condition(node.test)
    branches.append({"family": family or "__unknown__", "values": _collect_numeric_assignments(node.body)})
    if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
        _collect_noise_branches(node.orelse[0], branches)
    elif node.orelse:
        branches.append({"family": "__else__", "values": _collect_numeric_assignments(node.orelse)})


def _family_from_condition(test: ast.AST) -> str | None:
    if not isinstance(test, ast.Compare):
        return None
    if not isinstance(test.left, ast.Name) or test.left.id != "family":
        return None
    if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        return None
    if len(test.comparators) != 1:
        return None
    comparator = test.comparators[0]
    if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str):
        return comparator.value
    return None


def _collect_numeric_assignments(statements: Iterable[ast.stmt]) -> Dict[str, float]:
    values: Dict[str, float] = {}
    for statement in statements:
        if not isinstance(statement, ast.Assign):
            continue
        if len(statement.targets) != 1 or not isinstance(statement.targets[0], ast.Name):
            continue
        name = statement.targets[0].id
        if name not in PROCESS_NOISE_FIELDS:
            continue
        value = _literal_float(statement.value)
        if value is not None:
            values[name] = value
    return values


def _literal_float(node: ast.AST) -> float | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        value = _literal_float(node.operand)
        return -value if value is not None else None
    return None


def _rows_from_input(rows_or_path: Sequence[Mapping[str, str]] | str | Path) -> List[Mapping[str, str]]:
    if isinstance(rows_or_path, (str, Path)):
        return read_csv_rows(rows_or_path)
    return list(rows_or_path)


def _first_available_float(*values: object) -> float:
    for value in values:
        parsed = _safe_float(value)
        if parsed == parsed:
            return parsed
    return float("nan")


def _safe_float(value: object) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return float("nan")


def _sequence_risk_level(axis_bias: float, final_axis_error: float, odi_median: float) -> str:
    if axis_bias > 0.0 and final_axis_error > 0.1 and odi_median > 0.6:
        return "HIGH"
    if axis_bias > 0.0:
        return "MEDIUM"
    return "LOW"


def _sequence_interpretation(scene_family: str, axis_bias: float, risk: str) -> str:
    if axis_bias > 0.0:
        return (
            f"{scene_family} received nonzero legacy axis_bias; resulting drift evidence is diagnostic only "
            f"and has {risk.lower()} scene-family confound risk."
        )
    return "Open-control legacy axis_bias is zero; it is useful as a contrast but not sufficient for a merged claim."


def _format_float(value: float) -> str:
    if value != value:
        return "nan"
    return f"{value:.12g}"
