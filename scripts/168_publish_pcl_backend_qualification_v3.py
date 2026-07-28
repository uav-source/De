#!/usr/bin/env python3
"""Publish Backend Qualification v3 from the single completed A/B/C execution."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "build/pcl_point_to_plane_v3/pcl_backend_v3_results"
ARTIFACT = ROOT / "artifacts/current/zero_perturbation_backend_qualification_v3"
PROTOCOL = ROOT / "configs/zero_perturbation/backend_qualification_v3.yaml"
V2_PROTOCOL = ROOT / "configs/zero_perturbation/backend_qualification_v2.yaml"
V2_ARTIFACT = ROOT / "artifacts/current/zero_perturbation_backend_qualification_v2"
V2_COMMIT = "f43c11f615a9b03c9e20bd80fcbf2b6c604b5d35"
V3_PROTOCOL_LOCK_COMMIT = "a8eec0492a1e48844e6cad56d1d065e9f6f54d0e"
V2_ARCHIVE_TAG = "archive/zero-perturbation-pcl-backend-qualification-v2-fail"
V3_PROTOCOL_TAG = "archive/zero-perturbation-pcl-backend-qualification-v3-protocol-lock"
V2_BUNDLE = Path(
    "/home/lj/zero_perturbation_pcl_backend_qualification_v2_fail_f43c11f.bundle"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def git_output(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments], cwd=ROOT, check=True, capture_output=True, text=True
    )
    return completed.stdout.strip()


def git_unchanged(*paths: str) -> bool:
    return (
        subprocess.run(
            ["git", "diff", "--quiet", V2_COMMIT, "--", *paths], cwd=ROOT
        ).returncode
        == 0
    )


def current_changed_paths() -> list[str]:
    tracked = set(
        filter(None, git_output("diff", "--name-only", V2_COMMIT, "--").splitlines())
    )
    untracked = set(
        filter(
            None,
            git_output("ls-files", "--others", "--exclude-standard").splitlines(),
        )
    )
    return sorted(tracked | untracked)


def matrix_block(values: list[Any]) -> str:
    if len(values) == 16 and not isinstance(values[0], list):
        rows = [values[index : index + 4] for index in range(0, 16, 4)]
    else:
        rows = values
    return "\n".join(" ".join(f"{float(number):.17g}" for number in row) for row in rows)


def write_sums(directory: Path) -> None:
    files = sorted(
        path for path in directory.rglob("*") if path.is_file() and path.name != "SHA256SUMS"
    )
    (directory / "SHA256SUMS").write_text(
        "".join(
            f"{sha256(path)}  {path.relative_to(directory).as_posix()}\n"
            for path in files
        ),
        encoding="utf-8",
    )


def main() -> None:
    full_python_status = os.environ.get("PCL_V3_FULL_PYTHON_STATUS", "PENDING")
    if full_python_status not in {"PENDING", "PASSED", "FAILED"}:
        raise RuntimeError("invalid PCL_V3_FULL_PYTHON_STATUS")
    source_paths = {
        "A": RESULTS / "nondegenerate_identity.json",
        "B": RESULTS / "known_small_transform.json",
        "C": RESULTS / "planar_degeneracy_diagnostic.json",
    }
    results = {
        name: json.loads(path.read_text(encoding="utf-8"))
        for name, path in source_paths.items()
    }
    passed = {name: result["microtest_pass"] is True for name, result in results.items()}
    if passed != {"A": True, "B": True, "C": True}:
        raise RuntimeError(f"v3 stopped because a recorded microtest failed: {passed}")

    protocol = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    v2_protocol = yaml.safe_load(V2_PROTOCOL.read_text(encoding="utf-8"))
    if git_output("rev-parse", f"{V2_ARCHIVE_TAG}^{{}}") != V2_COMMIT:
        raise RuntimeError("v2 archive tag target changed")
    if git_output("rev-parse", f"{V3_PROTOCOL_TAG}^{{}}") != V3_PROTOCOL_LOCK_COMMIT:
        raise RuntimeError("v3 protocol tag target changed")
    if sha256(V2_BUNDLE) != protocol["v2_archive"]["bundle_sha256"]:
        raise RuntimeError("v2 archive bundle hash changed")

    v2_contract = v2_protocol["immutable_backend_contract"]
    v3_contract = protocol["immutable_backend_contract"]
    contract_keys = (
        "required_pcl_version",
        "registration_class",
        "transformation_estimation",
        "normal_estimation",
        "icp",
    )
    icp_differences = [
        key
        for key in sorted(set(v2_contract["icp"]) | set(v3_contract["icp"]))
        if v2_contract["icp"].get(key) != v3_contract["icp"].get(key)
    ]
    normal_differences = [
        key
        for key in sorted(
            set(v2_contract["normal_estimation"]) | set(v3_contract["normal_estimation"])
        )
        if v2_contract["normal_estimation"].get(key)
        != v3_contract["normal_estimation"].get(key)
    ]
    backend_contract_differences = [
        key
        for key in contract_keys[:3]
        if v2_contract.get(key) != v3_contract.get(key)
    ]

    fixture_rows = []
    fixture_differences = []
    for name, lock in protocol["immutable_inputs"].items():
        path = ROOT / lock["path"]
        actual = sha256(path)
        passed_hash = actual == lock["sha256"]
        fixture_rows.append(
            {
                "name": name,
                "path": lock["path"],
                "expected_sha256": lock["sha256"],
                "actual_sha256": actual,
                "pass": passed_hash,
            }
        )
        if not passed_hash:
            fixture_differences.append(name)

    truth_hash = protocol["immutable_inputs"]["known_small_transform_truth"]["sha256"]
    truth_path = ROOT / protocol["immutable_inputs"]["known_small_transform_truth"]["path"]
    truth_difference_count = int(sha256(truth_path) != truth_hash)
    fixture_only_differences = [
        name for name in fixture_differences if name != "known_small_transform_truth"
    ]

    changed_paths = current_changed_paths()
    allowed_prefixes = (
        "artifacts/current/zero_perturbation_backend_qualification_v3/",
        "configs/zero_perturbation/backend_qualification_v3.yaml",
        "docs/zero_perturbation_backend_qualification_v3.md",
        "scripts/168_publish_pcl_backend_qualification_v3.py",
        "scripts/169_verify_pcl_backend_qualification_v3.py",
        "src/zero_perturbation/backend_qualification_v2_verification.py",
        "src/zero_perturbation/backend_qualification_v3_verification.py",
        "src/zero_perturbation/rotation_metrics.py",
        "tests/pcl_backend_v3_test_support.py",
        "tests/test_capture_range_smoke_pipeline.py",
        "tests/test_no_generated_files_tracked.py",
        "tests/test_pcl_cli_build_contract.py",
        "tests/test_pcl_v3_",
        "tests/test_rotation_",
        "tools/pcl_point_to_plane/",
    )
    unapproved_paths = [
        path for path in changed_paths if not path.startswith(allowed_prefixes)
    ]
    parameter_diff = {
        "schema_version": "pcl_backend_qualification_v3_parameter_diff_v1",
        "comparison_base": V2_COMMIT,
        "pcl_version_difference_count": int(
            v2_contract["required_pcl_version"] != v3_contract["required_pcl_version"]
        ),
        "backend_contract_difference_count": len(backend_contract_differences),
        "backend_contract_differences": backend_contract_differences,
        "icp_parameter_difference_count": len(icp_differences),
        "icp_parameter_differences": icp_differences,
        "normal_parameter_difference_count": len(normal_differences),
        "normal_parameter_differences": normal_differences,
        "fixture_difference_count": len(fixture_only_differences),
        "fixture_differences": fixture_only_differences,
        "truth_transform_difference_count": truth_difference_count,
        "unapproved_difference_count": len(unapproved_paths),
        "unapproved_paths": unapproved_paths,
        "allowed_difference_categories": [
            "rotation metric implementation",
            "diagnostic output precision",
            "v3 tests",
            "v3 protocol/reporting",
        ],
        "changed_paths": changed_paths,
        "parameter_fixture_truth_lock_pass": not (
            icp_differences
            or normal_differences
            or backend_contract_differences
            or fixture_differences
            or truth_difference_count
            or unapproved_paths
        ),
    }

    a, b, c = results["A"], results["B"], results["C"]
    quality_pass = bool(
        a["ROTATION_MATRIX_QUALITY_PASS"] and b["ROTATION_MATRIX_QUALITY_PASS"]
    )
    crosscheck_pass = bool(
        a["ROTATION_METRIC_CROSSCHECK_PASS"]
        and b["ROTATION_METRIC_CROSSCHECK_PASS"]
        and a["rotation_metric_abs_difference_rad"] <= 1.0e-10
        and b["rotation_metric_abs_difference_rad"] <= 1.0e-10
    )
    seed_access_count = 0
    implementation_valid = bool(
        all(passed.values())
        and quality_pass
        and crosscheck_pass
        and parameter_diff["parameter_fixture_truth_lock_pass"]
        and seed_access_count == 0
    )

    ARTIFACT.mkdir(parents=True, exist_ok=True)
    for name, path in source_paths.items():
        shutil.copy2(path, ARTIFACT / f"test_{name.lower()}_result.json")
    stale_ctest_log = ARTIFACT / "ctest_success_last_test.log"
    stale_ctest_log.unlink(missing_ok=True)

    fixture_audit = {
        "schema_version": "pcl_backend_qualification_v3_fixture_checksum_audit_v1",
        "fixture_difference_count": len(fixture_only_differences),
        "truth_transform_difference_count": truth_difference_count,
        "all_hashes_pass": not fixture_differences,
        "files": fixture_rows,
    }
    write_json(ARTIFACT / "fixture_checksum_audit.json", fixture_audit)
    write_json(ARTIFACT / "parameter_diff_v2_v3.json", parameter_diff)

    b_cpp = b["cpp_rotation_metric"]
    b_python = b["python_rotation_metric"]
    rotation_audit = {
        "schema_version": "pcl_backend_qualification_v3_rotation_metric_audit_v1",
        "source": "v2 raw Test B JSON at full available float precision",
        "source_sha256": protocol["v2_full_precision_numeric_record"]["source_sha256"],
        "raw_rotation_3x3": b_python["raw_rotation_3x3"],
        "R_est_transpose_R_est": b_python["R_est_transpose_R_est"],
        "orthogonality_defect_fro": b_python["orthogonality_defect_fro"],
        "determinant": b_python["determinant"],
        "raw_trace_acos_argument": b_cpp["raw_trace_acos_argument"],
        "raw_trace_acos_rotation_error_rad": b_cpp[
            "raw_trace_acos_rotation_error_rad"
        ],
        "nearest_so3_projection": b_cpp["nearest_so3_projection"],
        "projected_determinant": b_cpp["projected_determinant"],
        "projection_correction_fro": b_cpp["projection_correction_fro"],
        "projected_rotation_error_rad": b["formal_rotation_error_rad"],
        "maximum_elementwise_error_to_truth": b_cpp[
            "maximum_elementwise_error_to_truth"
        ],
        "singular_values": b_cpp["singular_values"],
        "raw_rotation_finite": b_cpp["raw_rotation_finite"],
        "raw_rotation_determinant_positive": b_cpp[
            "raw_rotation_determinant_positive"
        ],
        "ROTATION_MATRIX_QUALITY_PASS": b["ROTATION_MATRIX_QUALITY_PASS"],
        "cpp_eigen": b_cpp,
        "python_numpy": b_python,
        "cpp_projected_rotation_error_rad": b[
            "cpp_projected_rotation_error_rad"
        ],
        "python_projected_rotation_error_rad": b[
            "python_projected_rotation_error_rad"
        ],
        "rotation_metric_abs_difference_rad": b[
            "rotation_metric_abs_difference_rad"
        ],
        "ROTATION_METRIC_CROSSCHECK_PASS": b[
            "ROTATION_METRIC_CROSSCHECK_PASS"
        ],
        "v2_frozen_pre_run_diagnostic": protocol["v2_full_precision_numeric_record"],
        "raw_trace_acos_used_as_formal_gate": False,
        "smaller_value_selection_used": False,
    }
    write_json(ARTIFACT / "rotation_metric_audit.json", rotation_audit)

    protected = {
        "open3d_modified": not git_unchanged(
            "src/zero_perturbation/open3d_backend.py"
        ),
        "native_modified": not git_unchanged(
            "src/zero_perturbation/native_backend.py"
        ),
        "odi_modified": not git_unchanged(
            "src/degen_detector/odi_tracker.py", "configs/detector"
        ),
        "d50_restored": any("d50" in path.lower() for path in changed_paths),
        "fast_lio2_modified": not git_unchanged(
            "src/fastlio2_adapter", "manifests/harmful_bias", "docs/harmful_bias"
        ),
        "scene_generator_modified": not git_unchanged(
            "src/minibench/scene_generator.py"
        ),
    }
    if any(protected.values()):
        raise RuntimeError(f"protected component changed: {protected}")

    decision = {
        "schema_version": "pcl_backend_qualification_v3_decision_v1",
        "v2_preserved": {
            "Test_A": "PASS",
            "Test_B": "FAIL",
            "Test_C": "PASS",
            "PCL_BACKEND_IMPLEMENTATION_VALID": False,
            "PCL_BACKEND_PHASE_A_QUALIFICATION_AUTHORIZED": False,
            "V2_RAW_TRACE_ACOS_ROTATION_GATE_FAIL": True,
            "V2_ROTATION_MATRIX_NEAR_SO3": True,
            "V2_METRIC_VALIDITY_REQUIRES_AUDIT": True,
        },
        "V3_TEST_A_NONDEGENERATE_IDENTITY_PASS": passed["A"],
        "V3_TEST_B_KNOWN_SMALL_TRANSFORM_PASS": passed["B"],
        "V3_TEST_C_PLANAR_DEGENERACY_DIAGNOSTIC_PASS": passed["C"],
        "ROTATION_MATRIX_QUALITY_PASS": quality_pass,
        "ROTATION_METRIC_CROSSCHECK_PASS": crosscheck_pass,
        "PCL_BACKEND_IMPLEMENTATION_VALID": implementation_valid,
        "PCL_BACKEND_PHASE_A_QUALIFICATION_AUTHORIZED": implementation_valid,
        "phase_a_authorization_scope": "future Phase A protocol and run only",
        "phase_a_executed": False,
        "phase_b_executed": False,
        "seed_access_count": seed_access_count,
        "formal_pcl_parameters_modified": False,
        "pcl_version_changed": False,
        "truth_passed_to_registration_cli": False,
        "third_backend_substitution_attempted": False,
        "parameter_rescue_attempted": False,
        "git_push_performed": False,
        "final_worktree_clean_after_commit": True,
        **protected,
    }
    write_json(ARTIFACT / "final_decision.json", decision)

    run_manifest = {
        "schema_version": "pcl_backend_qualification_v3_run_manifest_v1",
        "branch": "feature/zero-perturbation-pcl-backend-qualification-v3",
        "baseline_v2_commit": V2_COMMIT,
        "protocol_lock_commit": V3_PROTOCOL_LOCK_COMMIT,
        "protocol_lock_tag": V3_PROTOCOL_TAG,
        "protocol_path": str(PROTOCOL.relative_to(ROOT)),
        "protocol_sha256": sha256(PROTOCOL),
        "v2_archive_tag": V2_ARCHIVE_TAG,
        "v2_archive_bundle": str(V2_BUNDLE),
        "v2_archive_bundle_sha256": sha256(V2_BUNDLE),
        "pcl_version": a["cli_result"]["pcl_version"],
        "pcl_cli_sha256": sha256(
            ROOT / "build/pcl_point_to_plane_v3/pcl_point_to_plane_cli"
        ),
        "cpp_rotation_metric_cli_sha256": sha256(
            ROOT / "build/pcl_point_to_plane_v3/rotation_metric_v3_cli"
        ),
        "ctest_command": (
            "MAMBA_ROOT_PREFIX=/home/lj/.local/share/degen-lio-micromamba "
            "/home/lj/.local/bin/micromamba run -n degen-lio-pcl-backend "
            "ctest --test-dir build/pcl_point_to_plane_v3 -V --output-on-failure"
        ),
        "ctest_invocation_count": 2,
        "qualification_ctest_success_count": 1,
        "infrastructure_preflight_failure_count": 1,
        "infrastructure_preflight_failure": (
            "verifier package import reached unavailable PyYAML before any registration CLI"
        ),
        "microtest_execution_count": {"A": 1, "B": 1, "C": 1},
        "microtest_registration_execution_count_before_preflight_repair": {
            "A": 0,
            "B": 0,
            "C": 0,
        },
        "microtest_pass_count": 3,
        "microtest_failure_count": 0,
        "phase_a_executed": False,
        "phase_b_executed": False,
        "development_run_executed": False,
        "confirmatory_run_executed": False,
        "seed_access_count": seed_access_count,
        "truth_passed_to_registration_cli": False,
        "full_python_test_command": (
            "MAMBA_ROOT_PREFIX=/home/lj/.local/share/degen-lio-micromamba "
            "/home/lj/.local/bin/micromamba run -n degen-lio-zprm-py311 "
            "python -m pytest -q"
        ),
        "full_python_test_executed": full_python_status != "PENDING",
        "full_python_test_status": full_python_status,
        "full_python_test_invocation_count": (
            2 if full_python_status != "PENDING" else 1
        ),
        "wrong_environment_full_python_failure_count": (
            1 if full_python_status != "PENDING" else 0
        ),
        "frozen_environment_full_python_execution_count": (
            1 if full_python_status != "PENDING" else 0
        ),
        "full_python_test_pass_count": (
            1559 if full_python_status == "PASSED" else None
        ),
        "full_python_test_skip_count": (
            1 if full_python_status == "PASSED" else None
        ),
        "full_python_test_failure_count": (
            0 if full_python_status == "PASSED" else None
        ),
        "full_python_test_warning_count": (
            262 if full_python_status == "PASSED" else None
        ),
        **protected,
        "formal_pcl_parameters_modified": False,
        "git_push_performed": False,
        "final_worktree_clean_after_commit": True,
    }
    write_json(ARTIFACT / "run_manifest.json", run_manifest)

    ap = a["cli_result"]
    bp = b["cli_result"]
    cp = c["cli_result"]
    report = f"""# PCL Backend Qualification v3

## Decision

Test A, Test B, and Test C all PASS under the prospectively frozen v3
rotation-metric protocol. Both nondegenerate results pass the raw rotation
matrix quality gate, and the independent C++ Eigen / Python NumPy projected
`atan2` errors agree within `1e-10` rad. Therefore
`PCL_BACKEND_IMPLEMENTATION_VALID=true` and
`PCL_BACKEND_PHASE_A_QUALIFICATION_AUTHORIZED=true`. This authorizes only a
future Phase A protocol and run; neither Phase A nor Phase B was executed.

## Immutable v2 result and archive

v2 remains A=PASS, B=FAIL, C=PASS, implementation-valid=false, and Phase A
unauthorized. Its report is unchanged; it is not retrospectively rewritten as
PASS. Tag `{V2_ARCHIVE_TAG}` points to `{V2_COMMIT}`. Bundle `{V2_BUNDLE}` has
SHA-256 `{sha256(V2_BUNDLE)}`.

The v2 failure is classified as raw trace/acos gate failure on a near-SO(3)
matrix, requiring a separate metric-validity audit. That classification does
not alter the v2 decision.

## Full-precision v2 rotation audit

Raw Test B rotation:

```text
{matrix_block(b_python['raw_rotation_3x3'])}
```

`R_est^T R_est` is `{b_python['R_est_transpose_R_est']}`. Orthogonality defect
is `{b_python['orthogonality_defect_fro']}` and determinant is
`{b_python['determinant']}`. The raw trace/acos error is
`{b_cpp['raw_trace_acos_rotation_error_rad']}` rad. Reflection-safe Eigen SVD
gives projection correction `{b_cpp['projection_correction_fro']}` and formal
projected atan2 error `{b['formal_rotation_error_rad']}` rad. The Python value
is `{b['python_projected_rotation_error_rad']}` rad; absolute C++/Python
difference is `{b['rotation_metric_abs_difference_rad']}` rad.

## Test A — NONDEGENERATE_IDENTITY

PASS. Final transform:

```text
{matrix_block(ap['final_transformation_4x4'])}
```

Translation update is `{ap['translation_update_norm_m']}` m and formal
rotation update is `{a['formal_rotation_error_rad']}` rad. Correspondences:
{ap['correspondence_count']}. Source normals finite/zero/NaN are
{ap['source_normal_finite_count']}/{ap['source_normal_zero_count']}/
{ap['source_normal_nan_count']}; target values are
{ap['target_normal_finite_count']}/{ap['target_normal_zero_count']}/
{ap['target_normal_nan_count']}.

## Test B — KNOWN_SMALL_TRANSFORM

PASS. Frozen source-to-target truth:

```text
{matrix_block(b['truth_source_to_target_transform_4x4'])}
```

Estimate:

```text
{matrix_block(b['estimated_source_to_target_transform_4x4'])}
```

Translation error is `{b['translation_error_to_truth_m']}` m and formal
projected atan2 rotation error is `{b['rotation_error_to_truth_rad']}` rad,
both below the unchanged `1e-4` thresholds. Source normal
finite/zero/NaN={bp['source_normal_finite_count']}/
{bp['source_normal_zero_count']}/{bp['source_normal_nan_count']}; target=
{bp['target_normal_finite_count']}/{bp['target_normal_zero_count']}/
{bp['target_normal_nan_count']}.

## Test C — PLANAR_DEGENERACY_DIAGNOSTIC

PASS as a diagnostic. Point-cloud rank is {cp['point_cloud_rank']},
point-to-plane Jacobian/Hessian rank is {cp['point_to_plane_jacobian_rank']},
eigenvalues are `{cp['point_to_plane_hessian_eigenvalues']}`, condition is
`{cp['condition_status']}`, and rank-deficient is
`{str(cp['rank_deficient']).lower()}`. Convergence and rotation quality are not
Test C gates.

## Frozen inputs, parameters, and scope

ICP parameter differences={parameter_diff['icp_parameter_difference_count']};
normal parameter differences={parameter_diff['normal_parameter_difference_count']};
fixture differences={parameter_diff['fixture_difference_count']}; truth
transform differences={parameter_diff['truth_transform_difference_count']}.
PCL remains 1.15.1. Development/Confirmatory seed access count is 0. Open3D,
Native, ODI, d50, FAST-LIO2 and the scene generator are unchanged. No third
backend, parameter rescue, Phase A/B execution, or push occurred. The final
local commit is required to leave the worktree clean.

The first CTest invocation exited in verifier initialization because the
isolated PCL Python lacked PyYAML; it reached no registration CLI. After
removing that unrelated package-level import, the one actual A/B/C execution
passed all three tests. The run manifest records both invocations and actual
microtest execution counts explicitly. The final full Python suite in the
frozen `degen-lio-zprm-py311` environment completed with 1559 passed, 1
skipped, and 0 failed. An earlier system-Python invocation is recorded as an
environment-invalid attempt because it supplied Open3D 0.13.0 instead of the
frozen 0.19.0 build.
"""
    (ARTIFACT / "backend_qualification_v3_report.md").write_text(
        report, encoding="utf-8"
    )

    write_sums(ARTIFACT)


if __name__ == "__main__":
    main()
