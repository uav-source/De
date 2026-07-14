from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from minibench.nested_geometry_observations import audit_nested_geometry_levels  # noqa: E402


def test_nested_geometry_information_increments_are_psd(nested_geometry_outputs):
    audit = audit_nested_geometry_levels(nested_geometry_outputs)
    assert audit["psd_increment_valid"] is True
    assert audit["delta_H_min_eigenvalue"] >= -1.0e-8
