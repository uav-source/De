from pathlib import Path

from eval.measurement_pilot import load_interval_lock


ROOT = Path(__file__).resolve().parents[1]


def test_audit_uses_exact_preregistered_intervals_without_swap():
    lock = load_interval_lock(ROOT / "configs/real_data/mun_frl_pilot_intervals.yaml")
    intervals = {row["label"]: row for row in lock["intervals"]}
    structural = intervals["structural_degeneracy_candidate"]
    control = intervals["geometry_rich_control"]
    assert (structural["start_timestamp"], structural["end_timestamp"]) == (
        1645814048.0,
        1645814062.0,
    )
    assert (control["start_timestamp"], control["end_timestamp"]) == (
        1645814164.0,
        1645814178.0,
    )
    assert lock["lock"]["detector_outputs_examined"] is False
