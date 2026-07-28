import ast
from pathlib import Path

from backend_phase_a_v1_2_test_support import ROOT


def test_stage0_sources_have_no_registration_backend_imports():
    paths = [ROOT / "scripts/169_build_backend_phase_a_stage0.py", ROOT / "scripts/170_verify_backend_phase_a_stage0.py", ROOT / "src/zero_perturbation/backend_phase_a_v1_2.py", ROOT / "src/zero_perturbation/backend_phase_a_stage0_verification.py"]
    forbidden = {"open3d_backend", "pcl_backend", "native_backend"}
    imports = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports.extend(node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom))
        imports.extend(alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names)
    assert sum(any(token in name for token in forbidden) for name in imports) == 0
