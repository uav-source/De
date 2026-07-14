from eval.weak_update_stage2b import select_attenuation_alpha


def _trial(level, stress, method, axis=1.0):
    return {
        "sweep": "open_control" if level == "OC" else "geometry",
        "level": level, "stress": stress, "geometry_seed": 1709,
        "sensor_seed": 55, "process_seed": 3001, "method": method,
        "axis_rmse": axis, "strong_translation_rmse": 1.0,
        "orientation_rmse_rad": 1.0, "trajectory_rmse_3d": 1.0,
        "solver_failure": 0,
    }


def test_alpha_selection_uses_feasibility_and_weakest_intervention_tie_break():
    candidates = [0.0, 0.1, 0.25, 0.5, 0.75]
    common = {"attenuation_alpha_candidates": candidates}
    base = [_trial("OC", "clean", "huber_full"), _trial("L3", "axial_correspondence_slip", "huber_full")]
    reductions = {0.0: 0.20, 0.1: 0.195, 0.25: 0.18, 0.5: 0.10, 0.75: 0.05}
    rows = []
    for alpha in candidates:
        clean = _trial("OC", "clean", "huber_selective")
        clean["candidate_alpha"] = alpha
        severe = _trial("L3", "axial_correspondence_slip", "huber_selective", 1.0 - reductions[alpha])
        severe["candidate_alpha"] = alpha
        rows.extend([clean, severe])
    table, selected = select_attenuation_alpha(base, rows, common)
    assert selected == 0.1
    assert [row["attenuation_alpha"] for row in table if row["selected"]] == [0.1]

