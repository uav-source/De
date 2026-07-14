import pytest

import eval.weak_update_stage2c_lock as locks
from test_stage2c_update_lock import _lock_fixture


def test_test_verification_refuses_a_no_go_lock(tmp_path, monkeypatch):
    lock = _lock_fixture(tmp_path, monkeypatch)
    lock["development_go"] = False
    with pytest.raises(RuntimeError, match="development_go"):
        locks.verify_update_lock(tmp_path, lock)
