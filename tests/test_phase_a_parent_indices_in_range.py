import numpy as np
import pytest

from backend_phase_a_v1_2_test_support import target_points, transform
from zero_perturbation.backend_phase_a_v1_2 import (
    Stage0ContractError,
    source_from_parent_indices,
)


def test_parent_indices_outside_target_are_rejected():
    target = target_points()
    with pytest.raises(Stage0ContractError, match="outside"):
        source_from_parent_indices(
            target, np.asarray([0, len(target)], dtype="<i8"), transform()
        )
