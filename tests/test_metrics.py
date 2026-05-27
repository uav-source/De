from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_metrics_contract_includes_directional_and_alternative_metrics():
    text = (ROOT / "docs/metrics_contract.md").read_text(encoding="utf-8")

    assert "e_axis(t) = |a(t)^T (p_est(t) - p_gt(t))|" in text
    assert "e_cross(t) = ||(I - a(t)a(t)^T)(p_est(t) - p_gt(t))||_2" in text
    assert "ODI" in text
    assert "condition_number" in text
    assert "lambda_min" in text
    assert "AIS" in text


def test_day14_acceptance_freezes_gate_thresholds():
    text = (ROOT / "docs/day14_acceptance.md").read_text(encoding="utf-8")

    assert "Median reliable axis alignment >= 0.70" in text
    assert "Spearman rho(ODI, axis drift rate) >= 0.50" in text
    assert "ODI beats condition_number or lambda_min" in text

