#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段 1 调研工具：对候选 GitHub 仓库做真实、只读的元数据采集。

设计原则：
- 只读：仅调用 GitHub REST API 的 GET 接口，不修改任何远端内容。
- 不伪造：任何请求失败都会在结果里显式记录 error 字段，绝不编造数据。
- 令牌来自 /root/.git-credentials（credential.helper=store）或环境变量 GITHUB_TOKEN，
  脚本自身不会把令牌写入输出。

用法：
    python3 scripts/research_github.py                      # 默认候选列表
    python3 scripts/research_github.py owner/repo owner2/repo2
输出：
    结构化 JSON（stdout），同时写入 --out 指定的文件（默认 scripts/research_result.json）。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

API = "https://api.github.com"
DEFAULT_REPOS = [
    "xjeway/mcp-manager",
    "tamb/simple-mcp-manager",
    "Bigsy/mcpmu",
    "agentbridgehq/agentbridge",
    "modelcontextprotocol/registry",
    "modelcontextprotocol/python-sdk",
]
# 我们关心的、与「安装/供应链安全」相关的根目录文件名
SECURITY_RELEVANT_FILES = [
    "install.sh", "setup.sh", "postinstall.js", "package.json",
    "requirements.txt", "pyproject.toml", "Dockerfile", "Makefile",
    "install.js", "install.py", "setup.py", "docker-compose.yml",
]


def load_token() -> str | None:
    """从环境变量或 git credential store 读取令牌；不打印令牌。"""
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        return tok.strip()
    path = os.path.expanduser("~/.git-credentials")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = re.match(r"https://([^:]*):([^@]*)@github\.com", line.strip())
                if m:
                    return m.group(2)
    return None


def api_get(url: str, token: str | None, *, retries: int = 2) -> dict:
    """GET 一个 GitHub API 端点，返回 {ok, status, data|error, rate_remaining}。"""
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "mcp-manager-research/0.1")
    if token:
        req.add_header("Authorization", f"token {token}")
    last_err = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                data = json.loads(body) if body.strip() else None
                return {
                    "ok": True,
                    "status": resp.status,
                    "data": data,
                    "rate_remaining": resp.headers.get("X-RateLimit-Remaining"),
                }
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            # 404/403 属于确定性失败，不必重试
            if e.code in (403, 404, 451):
                return {
                    "ok": False,
                    "status": e.code,
                    "error": f"HTTP {e.code}: {body[:300]}",
                    "rate_remaining": e.headers.get("X-RateLimit-Remaining"),
                }
            last_err = f"HTTP {e.code}: {body[:300]}"
        except Exception as e:  # noqa: BLE001 - 网络层错误统一记录
            last_err = f"{type(e).__name__}: {e}"
        time.sleep(1.5 * (attempt + 1))
    return {"ok": False, "status": None, "error": last_err, "rate_remaining": None}


def collect_repo(full_name: str, token: str | None) -> dict:
    out: dict = {"repo": full_name, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    meta = api_get(f"{API}/repos/{full_name}", token)
    if not meta["ok"]:
        out["error"] = meta["error"]
        out["status"] = meta["status"]
        return out
    d = meta["data"]
    out["meta"] = {
        "full_name": d.get("full_name"),
        "html_url": d.get("html_url"),
        "description": d.get("description"),
        "stars": d.get("stargazers_count"),
        "forks": d.get("forks_count"),
        "open_issues": d.get("open_issues_count"),
        "watchers": d.get("subscribers_count"),
        "language": d.get("language"),
        "license": (d.get("license") or {}).get("spdx_id"),
        "topics": d.get("topics"),
        "created_at": d.get("created_at"),
        "updated_at": d.get("updated_at"),
        "pushed_at": d.get("pushed_at"),
        "archived": d.get("archived"),
        "disabled": d.get("disabled"),
        "default_branch": d.get("default_branch"),
        "size_kb": d.get("size"),
        "has_wiki": d.get("has_wiki"),
        "homepage": d.get("homepage"),
    }
    # 最近 release
    rel = api_get(f"{API}/repos/{full_name}/releases/latest", token)
    if rel["ok"] and rel["data"]:
        out["latest_release"] = {
            "tag": rel["data"].get("tag_name"),
            "name": rel["data"].get("name"),
            "published_at": rel["data"].get("published_at"),
            "assets": len(rel["data"].get("assets") or []),
        }
    else:
        out["latest_release"] = None
        if rel.get("status") not in (404, None):
            out["latest_release_error"] = rel.get("error")
    # 最近提交
    com = api_get(f"{API}/repos/{full_name}/commits?per_page=1", token)
    if com["ok"] and com["data"]:
        c = com["data"][0]
        out["latest_commit"] = {
            "sha": c.get("sha"),
            "date": (c.get("commit") or {}).get("committer", {}).get("date"),
            "message": ((c.get("commit") or {}).get("message") or "").splitlines()[0][:120],
        }
    else:
        out["latest_commit"] = None
    # 根目录内容
    con = api_get(f"{API}/repos/{full_name}/contents/", token)
    if con["ok"] and isinstance(con["data"], list):
        names = [x.get("name") for x in con["data"]]
        out["root_files"] = names
        out["security_relevant_files"] = [n for n in names if n in SECURITY_RELEVANT_FILES]
    else:
        out["root_files"] = None
    # 语言构成
    lang = api_get(f"{API}/repos/{full_name}/languages", token)
    out["languages"] = lang["data"] if lang["ok"] else None
    out["rate_remaining_after"] = meta.get("rate_remaining")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repos", nargs="*", default=None)
    ap.add_argument("--out", default="scripts/research_result.json")
    args = ap.parse_args()

    token = load_token()
    if not token:
        print("[warn] 未找到 GitHub 令牌，将以匿名方式请求（限流更严）", file=sys.stderr)

    repos = args.repos or DEFAULT_REPOS
    results = []
    for r in repos:
        print(f"[*] 采集 {r} ...", file=sys.stderr)
        results.append(collect_repo(r, token))

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "authenticated": bool(token),
        "count": len(results),
        "repos": results,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"[*] 已写入 {args.out}", file=sys.stderr)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
