import numpy as np
import pytest

from backend_phase_a_v1_2_test_support import target_points, transform
from zero_perturbation.backend_phase_a_v1_2 import (
    Stage0ContractError,
    source_from_parent_indices,
)


def test_duplicate_parent_indices_are_rejected():
    with pytest.raises(Stage0ContractError, match="unique"):
        source_from_parent_indices(
            target_points(), np.asarray([1, 1, 2], dtype="<i8"), transform()
        )
