from eval.stage2_failure_day13_correction_v2 import build_fpr_breakdown_v2


def _rows(role):
    rows = []
    for sweep, scores in (
        ("geometry", [14.0, 1.0]),
        ("observation", [14.0, 1.0]),
        ("open_control", [1.0, 1.0]),
    ):
        for index, score in enumerate(scores):
            rows.append({
                "role": role, "stress": "clean", "sweep": sweep,
                "stat_input_valid": True, "window_ready": True,
                "primary_score": score, "frame_index": index,
            })
    return rows


def test_fpr_is_reported_by_role_and_clean_population():
    rows = build_fpr_breakdown_v2(_rows("calibration"), _rows("evaluation"))
    assert {(row["role"], row["population"]) for row in rows} == {
        (role, population)
        for role in ("calibration", "evaluation")
        for population in ("clean_all", "weak_clean", "open_control")
    }
    evaluation = {
        row["population"]: row for row in rows if row["role"] == "evaluation"
    }
    assert evaluation["clean_all"]["fpr"] == 2 / 6
    assert evaluation["weak_clean"]["fpr"] == 2 / 4
    assert evaluation["open_control"]["fpr"] == 0.0

