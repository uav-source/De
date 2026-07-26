from pathlib import Path

import numpy as np
import pytest

from eval.time_alignment_audit import validate_strict_seconds_timestamps


ROOT = Path(__file__).resolve().parents[1]


def test_mun_frl_contract_uses_message_headers_not_bag_record_epoch():
    source = (ROOT / "src/fastlio2_adapter/mun_frl_contract.py").read_text(encoding="utf-8")
    capture = (ROOT / "scripts/133_capture_mun_frl_offline_topics.py").read_text(encoding="utf-8")
    assert "del bag_record_time" in source
    assert 'return stamp_to_seconds(_value(header, "stamp"))' in source
    assert "message.header.stamp.to_sec()" in capture
    assert '"bag_record_epoch_used": False' in capture


@pytest.mark.parametrize("scale", [1.0e3, 1.0e6, 1.0e9])
def test_microsecond_and_nanosecond_epoch_units_fail_closed(scale):
    timestamps = np.asarray([1645814029.0, 1645814029.1]) * scale
    with pytest.raises(ValueError, match="microseconds or nanoseconds"):
        validate_strict_seconds_timestamps(timestamps)
