from pathlib import Path

import pytest

from fastlio2_adapter.runtime_paths import (
    RuntimePathError,
    build_runtime_paths,
    resolve_runtime_path,
    validate_runtime_output_param,
)


def test_relative_run_root_resolves_to_absolute(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert resolve_runtime_path("relative/run", name="run_root").is_absolute()


def test_absolute_tilde_and_parent_paths_are_normalized(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert resolve_runtime_path("~/run", name="run_root") == (tmp_path / "run").resolve()
    assert resolve_runtime_path(tmp_path / "a/../run", name="run_root") == (tmp_path / "run").resolve()


def test_all_runtime_paths_are_absolute_and_not_duplicated(tmp_path):
    run_root = (tmp_path / "run").resolve()
    paths = build_runtime_paths(
        run_root=run_root,
        phase_root=run_root / "runs/baseline",
        run_dir=run_root / "runs/baseline/sequence/AUDIT_ONLY_R1",
        clip_path=tmp_path / "clip.bag",
        binary_path=tmp_path / "fastlio_mapping",
    )
    audit = paths.audit()
    assert audit["all_runtime_paths_absolute"] is True
    assert audit["duplicate_run_root_detected"] is False
    assert paths.ros_home.is_absolute()
    assert paths.ros_log_dir.is_absolute()
    assert paths.runtime_output_dir.is_absolute()
    assert paths.clip_path.is_absolute()
    assert paths.binary_path.is_absolute()


def test_empty_runtime_path_and_param_mismatch_fail(tmp_path):
    with pytest.raises(RuntimePathError):
        resolve_runtime_path("", name="runtime_output_dir")
    expected = (tmp_path / "run").resolve()
    with pytest.raises(RuntimePathError):
        validate_runtime_output_param(expected, "")
    with pytest.raises(RuntimePathError):
        validate_runtime_output_param(expected, str(tmp_path / "other"))


def test_matching_absolute_rosparam_passes(tmp_path):
    expected = (tmp_path / "run").resolve()
    assert validate_runtime_output_param(expected, str(expected))["runtime_output_param_match"] is True


def test_committed_v3_docs_do_not_contain_personal_absolute_path():
    root = Path(__file__).resolve().parents[1]
    for relative in (
        "docs/harmful_bias/day5_startup_sync_v3_contract.md",
        "docs/harmful_bias/day5_startup_sync_v3_report.md",
        "manifests/harmful_bias/day5_startup_sync_v3_manifest.json",
    ):
        path = root / relative
        if path.exists():
            assert "/home/lj" not in path.read_text(encoding="utf-8")
