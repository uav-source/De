import ast
import inspect
from pathlib import Path

from eval import stage2_failure_deterministic_case as selection
from eval.stage2_failure_day11a import audit_forbidden_dependencies


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {
    "axis_rmse",
    "trajectory_rmse",
    "weak_innovation",
    "cusum",
    "gt_error",
    "plot_score",
}


def test_selection_api_has_no_metric_or_diagnostic_inputs():
    for function in (
        selection.build_candidate_pool,
        selection.deterministic_case_index,
        selection.select_case,
    ):
        assert FORBIDDEN.isdisjoint(inspect.signature(function).parameters)


def test_day11a_forbidden_dependency_audit_passes():
    audit = audit_forbidden_dependencies(ROOT)
    assert audit["audit_pass"] is True
    assert audit["ast_parse_failure_count"] == 0
    assert audit["forbidden_imports"] == []
    assert audit["forbidden_selection_parameters"] == []
    assert audit["forbidden_runtime_calls"] == []


def test_selection_module_does_not_import_random_or_call_builtin_hash():
    path = ROOT / "src/eval/stage2_failure_deterministic_case.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = []
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            calls.append(node.func.id)
    assert "random" not in imports
    assert "hash" not in calls
