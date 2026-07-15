import copy
import json
from pathlib import Path

import pytest

from eval import stage2_failure_day11a as day11a
from eval.stage2_failure_day11a_schema import validate_case_lock


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def written_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(day11a, "git_status_clean", lambda root: True)
    day11a.run_stage2_failure_day11a(ROOT, "lock_fixture", tmp_path)
    output = tmp_path / "lock_fixture"
    return {
        "lock": json.loads(
            (output / "deterministic_diagnostic_case_lock.json").read_text()
        ),
        "rows": day11a.read_candidate_pool(output / "candidate_pool.csv"),
        "pool_sha": day11a.sha256_file(output / "candidate_pool.csv"),
        "config": day11a.load_yaml(
            ROOT / "configs/stage2_failure/day11a_case_lock.yaml"
        ),
    }


def mutate_lock(lock, mutation):
    if mutation == "stage2c_commit":
        lock["stage2c_commit"] = "0" * 40
    elif mutation == "candidate_pool_sha256":
        lock["candidate_pool_sha256"] = "0" * 64
    elif mutation == "hash_label":
        lock["geometry_hash_label"] += "-changed"
    elif mutation == "digest":
        lock["geometry_hash_digest_hex"] = "0" * 64
    elif mutation == "selected_index":
        lock["geometry_selected_index"] += 1
    elif mutation == "selected_case":
        lock["geometry_selected_case"]["process_seed"] += 1
    elif mutation == "method_list":
        lock["required_methods"] = list(reversed(lock["required_methods"]))
    elif mutation == "stress_list":
        lock["day11b_replay_stress_regimes"].append("gross_outlier_control")
    elif mutation == "selection_algorithm":
        lock["selection_algorithm_version"] = "changed"
    elif mutation == "manual_flag":
        lock["selection_used_manual_override"] = True
    elif mutation == "alias_flag":
        lock["stress_name_alias_used"] = True
    elif mutation == "legacy_name_flag":
        lock["legacy_stage2b_stress_name_used"] = True
    elif mutation == "gross_replay_flag":
        lock["gross_outlier_control_replayed"] = True
    else:
        raise AssertionError(mutation)


@pytest.mark.parametrize(
    "mutation",
    [
        "stage2c_commit",
        "candidate_pool_sha256",
        "hash_label",
        "digest",
        "selected_index",
        "selected_case",
        "method_list",
        "stress_list",
        "selection_algorithm",
        "manual_flag",
        "alias_flag",
        "legacy_name_flag",
        "gross_replay_flag",
    ],
)
def test_case_lock_tampering_is_rejected(written_lock, mutation):
    lock = copy.deepcopy(written_lock["lock"])
    mutate_lock(lock, mutation)
    with pytest.raises(ValueError):
        validate_case_lock(
            lock,
            written_lock["rows"],
            written_lock["pool_sha"],
            written_lock["config"],
        )


def test_unmodified_case_lock_round_trips(written_lock):
    validate_case_lock(
        written_lock["lock"],
        written_lock["rows"],
        written_lock["pool_sha"],
        written_lock["config"],
    )
