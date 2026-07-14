from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from minibench.scene_generator import generate_master_axial_patch_pool  # noqa: E402


def test_real_geometry_support_changes_by_removing_finite_surfaces():
    pool = generate_master_axial_patch_pool(101, 30.0, 4.0, 3.0, 16)
    scores = [sum(float(patch.support_strength) for patch in pool[:count]) for count in [12, 7, 3, 1]]
    assert scores[0] > scores[1] > scores[2] > scores[3] > 0.0
    assert all(patch.sampling_weight == 1.0 for patch in pool)
