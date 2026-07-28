from phase_a_formal_lock_test_support import wrong_binding_error


def test_wrong_publisher_sha_is_rejected(tmp_path):
    assert "FORMAL_LOCK_IMPLEMENTATION_BINDING_MISMATCH" in wrong_binding_error(tmp_path, "publisher_sha256")
