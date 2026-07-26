from pathlib import Path

from capture_range.day2_protocol import (
    AMENDMENT_MARKDOWN_RELATIVE,
    AMENDMENT_MARKDOWN_SHA256,
    AMENDMENT_YAML_RELATIVE,
    AMENDMENT_YAML_SHA256,
    BASE_MARKDOWN_RELATIVE,
    BASE_MARKDOWN_SHA256,
    BASE_YAML_RELATIVE,
    BASE_YAML_SHA256,
    file_sha256,
)


ROOT = Path(__file__).resolve().parents[1]


def test_v1_1_amendment_files_are_byte_exact():
    assert file_sha256(ROOT / AMENDMENT_YAML_RELATIVE) == AMENDMENT_YAML_SHA256
    assert (
        file_sha256(ROOT / AMENDMENT_MARKDOWN_RELATIVE)
        == AMENDMENT_MARKDOWN_SHA256
    )


def test_archived_v1_0_files_remain_byte_exact():
    assert file_sha256(ROOT / BASE_YAML_RELATIVE) == BASE_YAML_SHA256
    assert file_sha256(ROOT / BASE_MARKDOWN_RELATIVE) == BASE_MARKDOWN_SHA256
