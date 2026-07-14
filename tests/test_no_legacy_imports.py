from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]


def test_active_python_modules_do_not_import_removed_legacy_workflows():
    forbidden = {
        "eval.metric_redesign_stage1",
        "eval.metric_redesign_stage1b",
        "eval.controlled_partial_validity",
        "eval.grouped_loso_validation",
        "eval.joint_risk_features",
    }
    offenders = []
    for base in (ROOT / "src", ROOT / "scripts", ROOT / "tests"):
        for path in base.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)
            if imported & forbidden:
                offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []
