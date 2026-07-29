from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


FORMAL_LOCK_RELATIVE = Path(
    "artifacts/current/zero_perturbation_phase_a_lock_architecture_v2/"
    "phase_a_formal_run_lock_v2.json"
)
LEGACY_RUNNER_RELATIVE = Path("scripts/168_run_backend_phase_a.py")


@dataclass(frozen=True)
class ActiveRunnerBinding:
    formal_lock: Path
    implementation_lock: Path
    implementation_manifest: Path
    active_runner: Path
    active_runner_relative: Path
    active_runner_sha256: str


def _json_object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert type(value) is dict, f"JSON root is not an object: {path}"
    return value


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_active_formal_runner(root: Path) -> ActiveRunnerBinding:
    repository = root.resolve()
    formal_path = repository / FORMAL_LOCK_RELATIVE
    formal = _json_object(formal_path)

    implementation_relative = Path(formal["execution_implementation_lock_path"])
    implementation_path = repository / implementation_relative
    implementation_file_sha = file_sha256(implementation_path)
    assert implementation_file_sha == formal["execution_implementation_lock_sha256"]
    implementation = _json_object(implementation_path)

    manifests = []
    for candidate in formal_path.parent.glob("*.json"):
        try:
            value = _json_object(candidate)
        except (OSError, UnicodeError, json.JSONDecodeError, AssertionError):
            continue
        if (
            value.get("schema_version")
            == "phase_a_lock_architecture_v2_implementation_manifest_v1"
            and value.get("implementation_lock_file_sha256") == implementation_file_sha
        ):
            manifests.append((candidate, value))
    assert len(manifests) == 1, "active implementation manifest is not unique"
    manifest_path, manifest = manifests[0]

    locked_sha = implementation["implementation_bindings"]["formal_runner_sha256"]
    manifest_binding = manifest["files"]["formal_runner_sha256"]
    assert manifest_binding["sha256"] == locked_sha
    runner_relative = Path(manifest_binding["path"])
    runner = repository / runner_relative
    assert runner.is_file()
    assert file_sha256(runner) == locked_sha
    return ActiveRunnerBinding(
        formal_lock=formal_path,
        implementation_lock=implementation_path,
        implementation_manifest=manifest_path,
        active_runner=runner,
        active_runner_relative=runner_relative,
        active_runner_sha256=locked_sha,
    )


def _is_fixed_runtime_error_raise(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Raise)
        and isinstance(node.exc, ast.Call)
        and isinstance(node.exc.func, ast.Name)
        and node.exc.func.id == "RuntimeError"
        and bool(node.exc.args)
        and isinstance(node.exc.args[0], ast.Constant)
        and isinstance(node.exc.args[0].value, str)
    )


def _block_guarantees_fixed_runtime_error(statements: list[ast.stmt]) -> bool:
    for statement in statements:
        if _is_fixed_runtime_error_raise(statement):
            return True
        if isinstance(statement, ast.If) and statement.orelse:
            if _block_guarantees_fixed_runtime_error(
                statement.body
            ) and _block_guarantees_fixed_runtime_error(statement.orelse):
                return True
        if isinstance(statement, (ast.Return, ast.Break, ast.Continue)):
            return False
    return False


def unconditional_placeholder_findings(source: str) -> list[str]:
    tree = ast.parse(source)
    findings = []
    if "intentionally deferred" in source.lower():
        findings.append("deferred placeholder marker")
    for statement in tree.body:
        if _is_fixed_runtime_error_raise(statement):
            findings.append(f"module-level fixed RuntimeError at line {statement.lineno}")
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name not in {"main", "execution_entry"}:
            continue
        direct_raise = next(
            (statement for statement in node.body if _is_fixed_runtime_error_raise(statement)),
            None,
        )
        if direct_raise is not None:
            findings.append(
                f"{node.name} has an unconditional fixed RuntimeError at line "
                f"{direct_raise.lineno}"
            )
        elif _block_guarantees_fixed_runtime_error(node.body):
            findings.append(f"all {node.name} branches terminate in a fixed RuntimeError")
    return findings
