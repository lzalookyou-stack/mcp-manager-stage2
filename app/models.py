"""统一插件数据模型。

覆盖 MCP / Agent 生态里形态各异的"插件"：
``mcp_server`` / ``agent_plugin`` / ``skill`` / ``command`` / ``hook`` /
``rules_instructions`` / ``adapter_extension``。

设计要点（见 docs/architecture.md）：
- 每个条目有**稳定 ID**（``source`` + ``slug`` 的确定性派生），不随抓取时间变化；
- 安装必须锁定到**固定 commit**（``pinned_ref``），拒绝浮动分支；
- 许可证、权限、风险都必须带**来源**与**证据等级**，不允许只有结论没有依据。
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# --------------------------------------------------------------------------- #
# 枚举
# --------------------------------------------------------------------------- #


class PluginKind(str, Enum):
    MCP_SERVER = "mcp_server"
    AGENT_PLUGIN = "agent_plugin"
    SKILL = "skill"
    COMMAND = "command"
    HOOK = "hook"
    RULES_INSTRUCTIONS = "rules_instructions"
    ADAPTER_EXTENSION = "adapter_extension"


class EvidenceLevel(str, Enum):
    """结论的证据等级——贯穿全项目的硬性纪律。"""

    VERIFIED = "verified"          # 【已验证事实】：有可复现的实测证据
    INFERRED = "inferred"          # 【有依据的推断】：有间接证据支撑
    UNCHECKED = "unchecked"        # 【未检查信息】：尚未核实
    UNDETERMINED = "undetermined"  # 【无法确定结论】：当前手段无法判定


class RiskLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"          # 具备"一票否决"能力


class ReviewStatus(str, Enum):
    PENDING = "pending"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    REJECTED = "rejected"


class InstallStatus(str, Enum):
    NOT_INSTALLED = "not_installed"
    PENDING = "pending"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    APPROVED = "approved"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    INTERRUPTED = "interrupted"


class LicenseSource(str, Enum):
    """许可证信息的取得方式——决定其可信度。"""

    API_FIELD = "api_field"        # 来自托管平台 API 的 license 字段
    LICENSE_FILE = "license_file"  # 来自仓库内的 LICENSE 文件
    README_CLAIM = "readme_claim"  # 仅来自 README 声称（**低可信**）
    UNKNOWN = "unknown"


# --------------------------------------------------------------------------- #
# 子结构
# --------------------------------------------------------------------------- #


class Evidence(BaseModel):
    """一条带来源的结论。"""

    model_config = ConfigDict(extra="forbid")

    statement: str
    level: EvidenceLevel
    source: str = Field(description="证据出处，例如 API 端点 / 文件路径 / 命令")
    detail: str | None = None


class Permission(BaseModel):
    """插件声明或实际需要的权限。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="例如 filesystem:read / network:outbound / shell:exec")
    required: bool = True
    granted: bool = False
    note: str | None = None


class LicenseInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    spdx_id: str | None = None
    name: str | None = None
    source: LicenseSource = LicenseSource.UNKNOWN
    evidence: EvidenceLevel = EvidenceLevel.UNCHECKED


class ScoreBreakdown(BaseModel):
    """可解释评分：每个维度都必须能给出理由，不允许"黑箱总分"。"""

    model_config = ConfigDict(extra="forbid")

    maintenance: float = Field(default=0.0, ge=0, le=100, description="维护状态 20%")
    quality: float = Field(default=0.0, ge=0, le=100, description="代码质量与测试 25%")
    security: float = Field(default=0.0, ge=0, le=100, description="安全风险 30%")
    compatibility: float = Field(default=0.0, ge=0, le=100, description="兼容性 15%")
    community: float = Field(default=0.0, ge=0, le=100, description="社区与许可证 10%")

    weights: dict[str, float] = Field(
        default_factory=lambda: {
            "maintenance": 0.20,
            "quality": 0.25,
            "security": 0.30,
            "compatibility": 0.15,
            "community": 0.10,
        }
    )
    vetoed: bool = Field(
        default=False,
        description="是否存在严重安全风险（一票否决，总分不再具有推荐意义）",
    )
    reasons: list[Evidence] = Field(default_factory=list)

    def total(self) -> float:
        if self.vetoed:
            return 0.0
        w = self.weights
        return round(
            self.maintenance * w["maintenance"]
            + self.quality * w["quality"]
            + self.security * w["security"]
            + self.compatibility * w["compatibility"]
            + self.community * w["community"],
            2,
        )


# --------------------------------------------------------------------------- #
# 主模型
# --------------------------------------------------------------------------- #

_SLUG_SAFE = re.compile(r"[^a-z0-9._-]+")


def derive_plugin_id(source: str, slug: str) -> str:
    """确定性派生稳定 ID。

    同一 (source, slug) 永远得到同一 ID，因此重抓不会产生重复条目。
    """
    norm_source = _SLUG_SAFE.sub("-", source.strip().lower()).strip("-")
    norm_slug = _SLUG_SAFE.sub("-", slug.strip().lower()).strip("-")
    if not norm_source or not norm_slug:
        raise ValueError("source 与 slug 均不能为空")
    digest = hashlib.sha256(f"{norm_source}::{norm_slug}".encode("utf-8")).hexdigest()
    return f"{norm_source}:{norm_slug}:{digest[:12]}"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Plugin(BaseModel):
    """统一插件条目。"""

    model_config = ConfigDict(extra="forbid")

    # --- 身份 ---
    id: str
    source: str = Field(description="来源标识，例如 github:owner/repo")
    slug: str = Field(description="来源内唯一短名")
    name: str
    kind: PluginKind
    description: str | None = None
    homepage: str | None = None
    repository: str | None = None

    # --- 版本与锁定 ---
    pinned_ref: str | None = Field(
        default=None, description="安装所锁定的固定 commit SHA；禁止浮动分支"
    )
    latest_version: str | None = None
    release_asset: str | None = None

    # --- 供应链 ---
    checksum_sha256: str | None = None
    signature_verified: bool = False
    signature_identity: str | None = None

    # --- 许可与权限 ---
    license: LicenseInfo = Field(default_factory=LicenseInfo)
    permissions: list[Permission] = Field(default_factory=list)

    # --- 风险与评分 ---
    risk_level: RiskLevel = RiskLevel.NONE
    score: ScoreBreakdown = Field(default_factory=ScoreBreakdown)

    # --- 状态 ---
    review_status: ReviewStatus = ReviewStatus.PENDING
    install_status: InstallStatus = InstallStatus.NOT_INSTALLED
    installed_path: str | None = None
    snapshot_path: str | None = None
    rollback_available: bool = False

    # --- 元数据 ---
    stars: int = Field(default=0, ge=0, description="仅作辅助信号，不参与评分主体")
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @field_validator("pinned_ref")
    @classmethod
    def _check_pinned_ref(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        # 只接受 40 位（或 64 位）十六进制 commit；拒绝分支名 / tag / HEAD
        if not re.fullmatch(r"[0-9a-fA-F]{40}([0-9a-fA-F]{24})?", v):
            raise ValueError(
                f"pinned_ref 必须是固定 commit SHA（40/64 位十六进制），拒绝浮动引用：{v!r}"
            )
        return v.lower()

    @field_validator("checksum_sha256")
    @classmethod
    def _check_checksum(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", v):
            raise ValueError(f"checksum_sha256 必须是 64 位十六进制：{v!r}")
        return v

    @classmethod
    def new(
        cls,
        *,
        source: str,
        slug: str,
        name: str,
        kind: PluginKind,
        **kwargs: Any,
    ) -> "Plugin":
        return cls(
            id=derive_plugin_id(source, slug),
            source=source,
            slug=slug,
            name=name,
            kind=kind,
            **kwargs,
        )