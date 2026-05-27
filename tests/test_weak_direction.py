from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_weak_direction_contract_uses_translation_component_only():
    text = (ROOT / "docs/formula_contract.md").read_text(encoding="utf-8")

    assert "V_W = {v_i | lambda_i / lambda_1 < tau_w}" in text
    assert "v_p = normalize(v_weak[3:6])" in text
    assert "axis_alignment = |v_p^T a|" in text
    assert "unreliable" in text

