import shutil
from pathlib import Path

from eval.stage2_failure_day12_figure_qc import audit_v2_v3_data_equivalence
from eval.stage2_failure_day12_figures import FIGURE_NAMES


ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "results/stage2_failure_analysis/day12_figures/stage2_failure_day12_figures_v2"


def _copy_frozen_data(target: Path) -> None:
    (target / "figure_data").mkdir(parents=True)
    for name in FIGURE_NAMES:
        shutil.copy2(V2 / "figure_data" / f"{name}.csv", target / "figure_data" / f"{name}.csv")
    for filename in ("day12_descriptive_summary.csv", "figure_captions.md"):
        shutil.copy2(V2 / filename, target / filename)


def test_v2_v3_data_equivalence_accepts_exact_frozen_copy(tmp_path):
    v3 = tmp_path / "v3"
    _copy_frozen_data(v3)
    audit = audit_v2_v3_data_equivalence(V2, v3)
    assert audit["plot_data_value_mismatch_count"] == 0
    assert audit["data_equivalence_pass"] is True


def test_v2_v3_data_equivalence_rejects_any_plot_data_byte_change(tmp_path):
    v3 = tmp_path / "v3"
    _copy_frozen_data(v3)
    target = v3 / "figure_data" / f"{FIGURE_NAMES[0]}.csv"
    target.write_bytes(target.read_bytes() + b"\n")
    audit = audit_v2_v3_data_equivalence(V2, v3)
    assert audit["figure1_plot_data_byte_identical"] is False
    assert audit["data_equivalence_pass"] is False
