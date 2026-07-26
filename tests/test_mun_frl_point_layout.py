from types import SimpleNamespace

import pytest

from fastlio2_adapter.mun_frl_contract import (
    EXPECTED_POINT_FIELDS,
    POINT_STEP,
    validate_point_layout,
)


def _fields():
    return [
        SimpleNamespace(name=name, offset=offset, datatype=datatype, count=count)
        for name, offset, datatype, count in EXPECTED_POINT_FIELDS
    ]


def test_mun_frl_exact_22_byte_point_layout_is_accepted():
    validate_point_layout(_fields(), point_step=POINT_STEP, is_bigendian=False)


@pytest.mark.parametrize("point_step,is_bigendian", [(24, False), (22, True)])
def test_mun_frl_incompatible_record_layout_is_rejected(point_step, is_bigendian):
    with pytest.raises(ValueError):
        validate_point_layout(
            _fields(), point_step=point_step, is_bigendian=is_bigendian
        )


def test_mun_frl_time_offset_must_remain_18():
    fields = _fields()
    fields[-1].offset = 20
    with pytest.raises(ValueError, match="field layout"):
        validate_point_layout(fields, point_step=22, is_bigendian=False)

