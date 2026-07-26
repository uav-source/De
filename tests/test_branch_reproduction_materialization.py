from __future__ import annotations

import importlib.util
import json
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _lock(module, tmp_path: Path, *, include_port: bool = True) -> Path:
    value = {
        "main_run_id": module.MAIN_RUN_ID,
        "sub_run_ids": list(module.SUB_RUN_IDS),
        "ros_master_ports": {
            run_id: 20211 + index
            for index, run_id in enumerate(module.SUB_RUN_IDS)
        },
    }
    if not include_port:
        del value["ros_master_ports"][module.SUB_RUN_IDS[0]]
    path = tmp_path / "run_lock.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _stage_summary():
    return {
        "stage_record_count": 26,
        "first_scan_index": 135,
        "last_scan_index": 160,
        "diagnostic_mutation_count": 0,
        "diagnostic_internal_error_count": 0,
    }


def test_ros_master_port_present_materializes_successfully(tmp_path) -> None:
    module = _load(
        ROOT / "scripts/85_run_experiment_a_stage_hash_pair.py",
        "materialization_present",
    )
    context = module.materialization_context(
        _lock(module, tmp_path), run_id=module.SUB_RUN_IDS[0]
    )
    result = module.finalize_materialized_summary(
        {"complete": True},
        _stage_summary(),
        run_id=module.SUB_RUN_IDS[0],
        ros_master_port=context["ros_master_port"],
    )
    assert result["ros_master_port"] == 20211
    assert result["complete"] is True


def test_missing_ros_master_port_fails_preflight(tmp_path) -> None:
    module = _load(
        ROOT / "scripts/85_run_experiment_a_stage_hash_pair.py",
        "materialization_missing",
    )
    with pytest.raises(RuntimeError, match="ros_master_port missing"):
        module.materialization_context(
            _lock(module, tmp_path, include_port=False),
            run_id=module.SUB_RUN_IDS[0],
        )


def test_post_replay_finalize_has_no_transport_summary_keyerror() -> None:
    module = _load(
        ROOT / "scripts/85_run_experiment_a_stage_hash_pair.py",
        "materialization_no_keyerror",
    )
    result = module.finalize_materialized_summary(
        {"complete": True},
        _stage_summary(),
        run_id="run",
        ros_master_port=20211,
    )
    assert result["ros_master_port"] == 20211


def test_materialization_does_not_mutate_runtime_data() -> None:
    module = _load(
        ROOT / "scripts/85_run_experiment_a_stage_hash_pair.py",
        "materialization_immutable",
    )
    runtime = {"complete": True, "nested": {"value": 1}}
    before = deepcopy(runtime)
    module.finalize_materialized_summary(
        runtime,
        _stage_summary(),
        run_id="run",
        ros_master_port=20211,
    )
    assert runtime == before


def test_wrapper_success_returns_zero_and_records_clean_exit(
    monkeypatch, tmp_path
) -> None:
    module = _load(
        ROOT / "scripts/93_run_bounded_branch_reproduction.py",
        "bounded_wrapper_success",
    )
    output = tmp_path / "run"
    output.mkdir()
    (output / "run_summary.json").write_text(
        json.dumps({"complete": True}), encoding="utf-8"
    )
    old = SimpleNamespace(main=lambda: 0)
    monkeypatch.setattr(module, "_load", lambda path, name: old)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "runner",
            "--sequence",
            "avia_quick_shack",
            "--clip",
            str(tmp_path / "clip"),
            "--run-id",
            module.SUB_RUN_IDS[0],
            "--output-dir",
            str(output),
            "--run-lock",
            str(tmp_path / "lock"),
            "--endpoint-contract",
            str(tmp_path / "endpoint"),
            "--authorization-audit",
            str(tmp_path / "audit"),
            "--enable-readonly-tap",
            "--enable-compact-export",
            "--enable-in-call-audit",
            "--enable-experiment-a-stage-hash",
            "--enable-coherent-map-snapshot",
            "--disable-runtime-detector",
            "--use-frozen-tail-adjudication",
        ],
    )
    assert module.main() == 0
    summary = json.loads(
        (output / "run_summary.json").read_text(encoding="utf-8")
    )
    assert summary["wrapper_exit_code"] == 0
    assert summary["wrapper_pipeline_clean_exit_pass"] is True

