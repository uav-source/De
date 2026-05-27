from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_formula_contract_contains_whitened_pose_block():
    text = (ROOT / "docs/formula_contract.md").read_text(encoding="utf-8")

    assert "H_tilde = (J_p D)^T R_L^-1 (J_p D)" in text
    assert "delta x_p = [delta theta^T, delta p^T]^T in R^6" in text
    assert "Do not left-multiply LiDAR residuals" in text

