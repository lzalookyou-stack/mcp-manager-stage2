"""数据模型测试：稳定 ID、固定 commit 强制、评分一票否决。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.models import (
    Evidence,
    EvidenceLevel,
    Plugin,
    PluginKind,
    RiskLevel,
    ScoreBreakdown,
    derive_plugin_id,
)

GOOD_COMMIT = "a" * 40
GOOD_SHA256 = "b" * 64


def test_derive_plugin_id_is_deterministic():
    a = derive_plugin_id("github:Owner/Repo", "My-Plugin")
    b = derive_plugin_id("github:owner/repo", "my-plugin")
    assert a == b, "ID 派生必须对大小写与前后空白不敏感"
    assert a != derive_plugin_id("github:owner/repo", "other-plugin")


def test_derive_plugin_id_rejects_empty():
    with pytest.raises(ValueError):
        derive_plugin_id("", "slug")
    with pytest.raises(ValueError):
        derive_plugin_id("github:x/y", "   ")


def test_derive_plugin_id_normalizes_separators():
    assert ":" not in derive_plugin_id("github:owner/repo", "slug").split(":")[1]
    pid = derive_plugin_id("github:owner/repo", "my plugin name")
    assert " " not in pid


def test_plugin_new_sets_stable_id():
    p1 = Plugin.new(source="github:o/r", slug="s", name="N", kind=PluginKind.MCP_SERVER)
    p2 = Plugin.new(source="github:o/r", slug="s", name="N2", kind=PluginKind.SKILL)
    assert p1.id == p2.id, "同一来源+slug 必须得到同一 ID"


def test_pinned_ref_accepts_full_commit():
    p = Plugin.new(
        source="github:o/r",
        slug="s",
        name="N",
        kind=PluginKind.MCP_SERVER,
        pinned_ref=GOOD_COMMIT.upper(),
    )
    assert p.pinned_ref == GOOD_COMMIT, "应统一小写"


@pytest.mark.parametrize(
    "bad_ref",
    ["main", "v1.2.3", "HEAD", "abc123", "a" * 39, "a" * 41, "refs/heads/main", ""],
)
def test_pinned_ref_rejects_floating_refs(bad_ref: str):
    """安装必须锁定到固定 commit；任何浮动引用都必须被拒绝。"""
    with pytest.raises(PydanticValidationError):
        Plugin.new(
            source="github:o/r",
            slug="s",
            name="N",
            kind=PluginKind.MCP_SERVER,
            pinned_ref=bad_ref,
        )


def test_checksum_must_be_sha256():
    with pytest.raises(PydanticValidationError):
        Plugin.new(
            source="github:o/r",
            slug="s",
            name="N",
            kind=PluginKind.MCP_SERVER,
            checksum_sha256="deadbeef",
        )
    p = Plugin.new(
        source="github:o/r",
        slug="s",
        name="N",
        kind=PluginKind.MCP_SERVER,
        checksum_sha256=GOOD_SHA256.upper(),
    )
    assert p.checksum_sha256 == GOOD_SHA256


def test_score_total_uses_declared_weights():
    score = ScoreBreakdown(
        maintenance=100, quality=100, security=100, compatibility=100, community=100
    )
    assert score.total() == 100.0

    zero = ScoreBreakdown()
    assert zero.total() == 0.0

    only_security = ScoreBreakdown(security=100)
    assert only_security.total() == pytest.approx(30.0)


def test_security_veto_zeroes_total():
    """严重安全风险必须一票否决，不能被其他维度的高分抵消。"""
    score = ScoreBreakdown(
        maintenance=100,
        quality=100,
        security=0,
        compatibility=100,
        community=100,
        vetoed=True,
    )
    assert score.total() == 0.0


def test_score_rejects_out_of_range():
    with pytest.raises(PydanticValidationError):
        ScoreBreakdown(security=101)
    with pytest.raises(PydanticValidationError):
        ScoreBreakdown(security=-1)


def test_plugin_rejects_unknown_fields():
    """extra=forbid：拼错字段必须报错，而不是静默丢弃。"""
    with pytest.raises(PydanticValidationError):
        Plugin.new(
            source="github:o/r",
            slug="s",
            name="N",
            kind=PluginKind.MCP_SERVER,
            totally_unknown_field=1,
        )


def test_plugin_default_states_are_conservative():
    p = Plugin.new(source="github:o/r", slug="s", name="N", kind=PluginKind.MCP_SERVER)
    assert p.risk_level is RiskLevel.NONE
    assert p.install_status.value == "not_installed"
    assert p.review_status.value == "pending", "默认必须是「未审查」，而非「已通过」"
    assert p.signature_verified is False
    assert p.rollback_available is False


def test_evidence_requires_source():
    ev = Evidence(
        statement="许可证为 MIT",
        level=EvidenceLevel.VERIFIED,
        source="https://api.github.com/repos/x/y",
    )
    assert ev.level is EvidenceLevel.VERIFIED
    with pytest.raises(PydanticValidationError):
        Evidence(statement="缺来源", level=EvidenceLevel.INFERRED)


def test_plugin_json_roundtrip():
    p = Plugin.new(
        source="github:o/r",
        slug="s",
        name="N",
        kind=PluginKind.MCP_SERVER,
        pinned_ref=GOOD_COMMIT,
    )
    restored = Plugin.model_validate_json(p.model_dump_json())
    assert restored == p