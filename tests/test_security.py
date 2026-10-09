"""安全原语测试：路径逃逸、标识符、常量时间比较、日志清洗。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.security import (
    SecurityError,
    constant_time_equals,
    is_full_commit,
    is_safe_identifier,
    new_token,
    require_safe_identifier,
    resolve_within,
    sanitize_for_log,
)


def test_safe_identifier_accepts_normal_names():
    for ok in ["mcp-manager", "repo.name", "a_b-c", "A1"]:
        assert is_safe_identifier(ok), ok


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "..",
        ".",
        "a/b",
        "a\\b",
        "a b",
        "../etc",
        "a\x00b",
        "-leading",
        "a" * 101,
    ],
)
def test_safe_identifier_rejects_dangerous(bad: str):
    assert not is_safe_identifier(bad), bad


def test_require_safe_identifier_raises():
    with pytest.raises(SecurityError):
        require_safe_identifier("..", what="slug")
    assert require_safe_identifier("good-name") == "good-name"


def test_is_full_commit():
    assert is_full_commit("a" * 40)
    assert is_full_commit("0123456789abcdef0123456789abcdef01234567")
    assert not is_full_commit("main")
    assert not is_full_commit("a" * 39)
    assert not is_full_commit("")


def test_resolve_within_accepts_normal_join(tmp_path: Path):
    base = tmp_path / "root"
    base.mkdir()
    got = resolve_within(base, "a", "b.txt")
    assert got == (base / "a" / "b.txt").resolve()


@pytest.mark.parametrize(
    "parts",
    [
        ("..",),
        ("..", "..", "etc"),
        ("a", "..", "..", "outside"),
    ],
)
def test_resolve_within_blocks_traversal(tmp_path: Path, parts: tuple[str, ...]):
    base = tmp_path / "root"
    base.mkdir()
    with pytest.raises(SecurityError):
        resolve_within(base, *parts)


def test_resolve_within_blocks_absolute(tmp_path: Path):
    base = tmp_path / "root"
    base.mkdir()
    with pytest.raises(SecurityError):
        resolve_within(base, "/etc/passwd")


def test_resolve_within_blocks_symlink_escape(tmp_path: Path):
    """符号链接指向 base 之外时必须被拒绝。"""
    base = tmp_path / "root"
    base.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")

    link = base / "link"
    try:
        os.symlink(outside, link)
    except (OSError, NotImplementedError):
        pytest.skip("当前文件系统不支持创建符号链接")

    with pytest.raises(SecurityError):
        resolve_within(base, "link", "secret.txt")


def test_resolve_within_allows_symlink_inside(tmp_path: Path):
    base = tmp_path / "root"
    (base / "real").mkdir(parents=True)
    link = base / "alias"
    try:
        os.symlink(base / "real", link)
    except (OSError, NotImplementedError):
        pytest.skip("当前文件系统不支持创建符号链接")

    got = resolve_within(base, "alias", "file.txt")
    assert got == (base / "real" / "file.txt").resolve()


def test_constant_time_equals():
    assert constant_time_equals("abc", "abc")
    assert not constant_time_equals("abc", "abd")
    assert not constant_time_equals("abc", "abcd")
    assert not constant_time_equals("", "a")
    assert not constant_time_equals(None, "a")  # type: ignore[arg-type]


def test_new_token_uniqueness_and_entropy():
    tokens = {new_token() for _ in range(50)}
    assert len(tokens) == 50
    assert all(len(t) >= 32 for t in tokens)


def test_sanitize_for_log_strips_control_chars():
    got = sanitize_for_log("line1\nline2\r\tend\x00")
    assert "\n" not in got
    assert "\r" not in got
    assert "\x00" not in got
    assert "line1 line2" in got


def test_sanitize_for_log_truncates():
    got = sanitize_for_log("x" * 500, max_len=10)
    assert len(got) <= 11  # 10 + 省略号
    assert got.startswith("x" * 10)