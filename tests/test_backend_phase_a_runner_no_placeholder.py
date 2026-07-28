import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runner_has_no_unconditional_runtime_error_placeholder():
    path = ROOT / "scripts/168_run_backend_phase_a.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert "intentionally deferred" not in source
    assert not any(
        isinstance(node, ast.Raise)
        and isinstance(node.exc, ast.Call)
        and isinstance(node.exc.func, ast.Name)
        and node.exc.func.id == "RuntimeError"
        for node in ast.walk(tree)
    )

