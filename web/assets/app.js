/*
 * mcp-manager 控制台脚本（阶段 2：只读）。
 *
 * 安全约定：**只使用 textContent / createElement 写入 DOM**，
 * 全程不使用 innerHTML / insertAdjacentHTML / eval / new Function。
 */

"use strict";

async function getJSON(url) {
  const resp = await fetch(url, {
    method: "GET",
    headers: { Accept: "application/json" },
    credentials: "same-origin",
    cache: "no-store",
  });
  if (!resp.ok) {
    throw new Error("HTTP " + resp.status);
  }
  return resp.json();
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) {
    el.textContent = String(text);
  }
}

function td(text, className) {
  const cell = document.createElement("td");
  cell.textContent = String(text);
  if (className) {
    cell.className = className;
  }
  return cell;
}

async function refreshHealth() {
  const el = document.getElementById("health");
  try {
    const data = await getJSON("/api/health");
    el.textContent =
      "服务正常 · 版本 " + data.version +
      " · 仅回环：" + (data.loopback_only ? "是" : "否") +
      " · 条目 " + data.plugins;
    el.className = "health ok";
  } catch (err) {
    el.textContent = "服务异常：" + err.message;
    el.className = "health err";
  }
}

async function refreshStats() {
  try {
    const data = await getJSON("/api/stats");
    setText("stat-total", data.total);
    setText("stat-kind", JSON.stringify(data.by_kind));
    setText("stat-install", JSON.stringify(data.by_install_status));
  } catch (err) {
    setText("stat-total", "读取失败：" + err.message);
  }
}

async function refreshPlugins() {
  const tbody = document.getElementById("plugin-rows");
  const empty = document.getElementById("plugin-empty");
  while (tbody.firstChild) {
    tbody.removeChild(tbody.firstChild);
  }
  try {
    const data = await getJSON("/api/plugins?limit=50");
    if (!data.items.length) {
      empty.hidden = false;
      return;
    }
    empty.hidden = true;
    for (const p of data.items) {
      const tr = document.createElement("tr");
      tr.appendChild(td(p.name));
      tr.appendChild(td(p.kind));
      tr.appendChild(td(p.risk_level, "risk-" + p.risk_level));
      tr.appendChild(td(p.review_status));
      tr.appendChild(td(p.install_status));
      tr.appendChild(td(p.score.total));
      tbody.appendChild(tr);
    }
  } catch (err) {
    empty.hidden = false;
    empty.textContent = "读取失败：" + err.message;
  }
}

async function refreshAudit() {
  const list = document.getElementById("audit-list");
  while (list.firstChild) {
    list.removeChild(list.firstChild);
  }
  try {
    const data = await getJSON("/api/audit?limit=20");
    for (const row of data.items) {
      const li = document.createElement("li");
      const actor = document.createElement("span");
      actor.className = "actor";
      actor.textContent = row.actor;
      li.appendChild(actor);
      li.appendChild(document.createTextNode(" · " + row.action + " · "));
      const outcome = document.createElement("span");
      outcome.className = row.outcome;
      outcome.textContent = row.outcome;
      li.appendChild(outcome);
      li.appendChild(document.createTextNode(" · " + (row.target || "-")));
      list.appendChild(li);
    }
  } catch (err) {
    const li = document.createElement("li");
    li.textContent = "读取失败：" + err.message;
    list.appendChild(li);
  }
}

async function refreshAll() {
  await refreshHealth();
  await refreshStats();
  await refreshPlugins();
  await refreshAudit();
}

document.addEventListener("DOMContentLoaded", () => {
  refreshAll();
  // 每 10 秒刷新一次（本地服务，开销极低）
  window.setInterval(refreshAll, 10000);
});