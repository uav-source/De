import pytest

from fastlio2_adapter.mun_frl_contract import validate_ring_values


def test_mun_frl_all_sixteen_rings_are_valid():
    assert validate_ring_values(range(16)) == {"minimum": 0, "maximum": 15}


@pytest.mark.parametrize("rings", [[-1, 0], [0, 16]])
def test_mun_frl_out_of_range_ring_is_rejected(rings):
    with pytest.raises(ValueError, match="0--15"):
        validate_ring_values(rings)

