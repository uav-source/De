import numpy as np

from eval.frame_contract import coordinate_frame_contract_rows
from degen_detector.whitened_info import compute_translation_schur_info


def test_translation_schur_retains_world_translation_block_after_rotation_marginalization():
    hessian = np.diag([8.0, 9.0, 10.0, 1.0, 3.0, 7.0])
    schur = compute_translation_schur_info(hessian)
    np.testing.assert_allclose(schur, np.diag([1.0, 3.0, 7.0]), atol=1e-12)
    rows = {row["stage"]: row for row in coordinate_frame_contract_rows()}
    assert rows["translation_Schur"]["output_frame"] == "FAST_LIO_CAMERA_INIT_WORLD_MAP"
