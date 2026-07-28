from backend_phase_a_test_support import protocol
from zero_perturbation.backend_phase_a_metrics import (
    NOT_EVALUATED,
    phase_a_backend_gate,
    snapshot_diversity_gate,
)


def _passing_rows():
    return [
        {
            "scene_variant": scene,
            "translation_update_m": 0.0,
            "rotation_update_rad": 0.0,
            "solver_failed": False,
            "finite_output": True,
        }
        for scene in protocol().scenes
        for _ in range(30)
    ]


def test_phase_a_gates_freeze_linear_q95_median_and_completeness():
    passed = phase_a_backend_gate(_passing_rows())
    assert passed["gate_pass"] is True
    assert passed["q95_translation_update_m"] == 0.0
    incomplete = phase_a_backend_gate(_passing_rows()[:-1])
    assert incomplete["status"] == NOT_EVALUATED
    assert incomplete["solver_failure_count"] is None
    failed_rows = _passing_rows()
    failed_rows[0]["solver_failed"] = True
    assert phase_a_backend_gate(failed_rows)["gate_pass"] is False


def test_snapshot_diversity_is_per_scene_and_requires_ten_sources():
    rows = [
        {
            "scene_variant": scene,
            "source_checksum": f"{scene}-source-{index % 10}",
            "target_checksum": f"{scene}-target",
        }
        for scene in protocol().scenes
        for index in range(30)
    ]
    assert snapshot_diversity_gate(rows)["IDEAL_MATCHED_SNAPSHOT_DIVERSITY_PASS"] is True
    for row in rows:
        if row["scene_variant"] == protocol().scenes[0]:
            suffix = int(row["source_checksum"].rsplit("-", 1)[1])
            row["source_checksum"] = f"collapsed-{suffix % 9}"
    assert snapshot_diversity_gate(rows)["IDEAL_MATCHED_SNAPSHOT_DIVERSITY_PASS"] is False
