from types import SimpleNamespace

import pytest

from fastlio2_adapter.mun_frl_contract import message_header_time_seconds


def test_message_header_time_is_used_instead_of_bag_record_epoch():
    message = SimpleNamespace(
        header=SimpleNamespace(stamp=SimpleNamespace(secs=1537295474, nsecs=125000000))
    )
    timestamp = message_header_time_seconds(
        message, bag_record_time=SimpleNamespace(secs=1700000000, nsecs=0)
    )
    assert timestamp == pytest.approx(1537295474.125)


def test_mapping_header_stamp_is_supported_without_ros_dependency():
    message = {"header": {"stamp": {"secs": 10, "nsecs": 250000000}}}
    assert message_header_time_seconds(message, bag_record_time=999) == 10.25

