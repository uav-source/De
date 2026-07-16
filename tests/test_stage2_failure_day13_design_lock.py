from pathlib import Path

import pytest

from eval.stage2_failure_day13_design import load_and_validate_day13_config


ROOT = Path(__file__).resolve().parents[1]


def test_day13_config_is_strictly_frozen():
    config = load_and_validate_day13_config(ROOT)
    assert config["primary_statistic"] == "huber_cusum_max"
    assert config["threshold_comparison_operator"] == ">"
    assert config["bootstrap_block"] == "geometry_seed"


def test_day13_config_rejects_primary_or_quantile_change(tmp_path, monkeypatch):
    from eval import stage2_failure_day13_design as design
    real = design.load_yaml
    monkeypatch.setattr(design, "load_yaml", lambda path: {**real(ROOT / design.DAY13_CONFIG_RELATIVE), "threshold_quantile": 0.91})
    with pytest.raises(ValueError):
        design.load_and_validate_day13_config(tmp_path)
