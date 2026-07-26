from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runner = load_script(
    ROOT / "scripts/101_run_focused_branch_capacity_remediation.py",
    "test_capacity_remediation_runner",
)
finalizer = load_script(
    ROOT / "scripts/102_finalize_focused_branch_capacity_remediation.py",
    "test_capacity_remediation_finalizer",
)


def authorization_value() -> dict:
    return {
        "schema_version":
            "focused_stage_hash_capacity_remediation_authorization_v1",
        "scientific_authorization_audit_sha256":
            runner.SCIENTIFIC_AUTHORIZATION_SHA256,
        "failed_focused_audit_sha256":
            runner.FAILED_FOCUSED_AUDIT_SHA256,
        "failure_classification":
            "REQUESTED_51_RECORD_WINDOW_EXCEEDS_FROZEN_RUNTIME_CAPACITY_26",
        "authorized_change":
            "EXPAND_BOUNDED_DIAGNOSTIC_RECORD_CAPACITY_FROM_26_TO_51",
        "formal_algorithm_change_authorized": False,
        "hash_contract_change_authorized": False,
        "snapshot_change_authorized": False,
        "thread_configuration_change_authorized": False,
        "replay_count_authorized": 4,
        "day7_authorized": False,
    }


def test_new_run_identity_is_fixed_and_disjoint() -> None:
    assert runner.MAIN_RUN_ID == (
        "multihyp_day6_focused_branch_capacity_remediation_v1"
    )
    assert runner.SUB_RUN_IDS == tuple(
        f"multihyp_day6_focused_capacity_r{index}"
        for index in range(1, 5)
    )
    assert runner.MAXIMUM_STAGE_RECORD_COUNT == 51
    assert (runner.SCAN_START, runner.SCAN_END) == (155, 205)
    assert not set(runner.SUB_RUN_IDS) & {
        f"multihyp_day6_focused_branch_r{index}"
        for index in range(1, 5)
    }


def test_capacity_authorization_accepts_only_bounded_change(
    tmp_path: Path,
) -> None:
    path = tmp_path / "authorization.json"
    path.write_text(
        json.dumps(authorization_value()) + "\n", encoding="utf-8"
    )
    value = runner.validate_capacity_authorization(path)
    assert value["replay_count_authorized"] == 4
    assert value["formal_algorithm_change_authorized"] is False
    assert value["day7_authorized"] is False


def test_capacity_authorization_rejects_unbounded_replay(
    tmp_path: Path,
) -> None:
    value = authorization_value()
    value["replay_count_authorized"] = 5
    path = tmp_path / "authorization.json"
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="authorization mismatch"):
        runner.validate_capacity_authorization(path)


def test_capacity_gate_requires_every_pre_replay_gate(
    tmp_path: Path,
) -> None:
    value = {
        name: True for name in runner.CAPACITY_GATE_FLAGS
    }
    value["maximum_stage_record_count"] = 51
    path = tmp_path / "gate.json"
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")
    assert runner.validate_capacity_gate(path)[
        "focused_stage_155_205_replay_authorized"
    ] is True
    value["window_52_rejected_pass"] = False
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Gate is not open"):
        runner.validate_capacity_gate(path)


def test_finalizer_preserves_closed_scientific_authority() -> None:
    result = finalizer.augment_gate(
        {
            "focused_formal_branch_localization_execution_pass": True,
            "formal_branch_reproduced": True,
            "formal_branch_stage_localized": True,
            "day7_recommended": True,
        },
        {
            "focused_stage_hash_capacity_remediation_pass": True,
            "focused_stage_155_205_replay_authorized": True,
        },
    )
    assert result["focused_stage_hash_capacity_remediation_pass"] is True
    assert result["STAGE2_GATE"] == "FAIL"
    assert result["TRANSITION"] == "PIVOT"
    assert result["DAY7_AUTHORIZED"] is False
    assert result["STAGE3_START_AUTHORIZED"] is False
    assert result["FAST_LIO2_INTEGRATION_AUTHORIZED"] is False
    assert result["additional_replay_authorized"] is False
