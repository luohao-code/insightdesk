/**
 * 应用入口。
 * 负责：路由注册、全局布局交互、健康检查、SSE 实时进度、命令面板与主题。
 */

import { api } from "./api.js";
import { $, $$, el, errorMessage, storage } from "./utils.js";
import { icon } from "./icons.js";
import { initRouter, navigate, register } from "./router.js";
import { applyTheme, setState, state, subscribe, toggleTheme } from "./store.js";
import { applyI18n, t } from "./i18n.js";
import { openCommandPalette } from "./components/commandPalette.js";
import { toastError, toastInfo } from "./components/toast.js";
import { APP_VERSION } from "./config.js";

import * as dashboardPage from "./pages/dashboard.js";
import * as ocrPage from "./pages/ocr.js";
import * as batchPage from "./pages/batch.js";
import * as aiPage from "./pages/ai.js";
import * as historyPage from "./pages/history.js";
import * as webPage from "./pages/web.js";
import * as settingsPage from "./pages/settings.js";
import * as helpPage from "./pages/help.js";

/* ------------------------------------------------------------------ */
/* 路由注册                                                            */
/* ------------------------------------------------------------------ */

register("dashboard", { render: dashboardPage.render });
register("ocr", { render: ocrPage.render });
register("batch", { render: batchPage.render });
register("ai", { render: aiPage.render });
register("history", { render: historyPage.render });
register("web", { render: webPage.render });
register("settings", { render: settingsPage.render });
register("help", { render: helpPage.render });

/* ------------------------------------------------------------------ */
/* 静态图标与文案                                                      */
/* ------------------------------------------------------------------ */

function injectIcons(root = document) {
  $$("[data-icon]", root).forEach((node) => {
    if (!node.dataset.icon) return;
    node.innerHTML = icon(node.dataset.icon, 18);
  });
}

function applyStaticTranslations() {
  $$(".nav-item[data-route]").forEach((item) => {
    const text = item.querySelector(".nav-text");
    if (text) text.textContent = t(`nav.${item.dataset.route}`);
  });
  const groupLabels = $$(".nav-label");
  const keys = ["nav.group.core", "nav.group.assets", "nav.group.system"];
  groupLabels.forEach((label, index) => {
    if (keys[index]) label.textContent = t(keys[index]);
  });
  const searchText = $(".search-text");
  if (searchText) searchText.textContent = t("topbar.search");
  applyI18n();
}

injectIcons();
applyStaticTranslations();

const versionBadge = $("#brand-version");
if (versionBadge) versionBadge.textContent = `v${APP_VERSION}`;

/* ------------------------------------------------------------------ */
/* 布局交互                                                            */
/* ------------------------------------------------------------------ */

function openSidebar() {
  $("#sidebar")?.classList.add("open");
  const backdrop = $("#sidebar-backdrop");
  if (backdrop) backdrop.hidden = false;
}

function closeSidebar() {
  $("#sidebar")?.classList.remove("open");
  const backdrop = $("#sidebar-backdrop");
  if (backdrop) backdrop.hidden = true;
}

$$(".nav-item").forEach((item) => {
  item.addEventListener("click", () => {
    navigate(item.dataset.route);
    closeSidebar();
  });
});

$("#menu-btn")?.addEventListener("click", () => {
  if ($("#sidebar")?.classList.contains("open")) closeSidebar();
  else openSidebar();
});

$("#sidebar-backdrop")?.addEventListener("click", closeSidebar);

$("#theme-btn")?.addEventListener("click", () => {
  toggleTheme();
});

$("#search-btn")?.addEventListener("click", () => openCommandPalette());

document.addEventListener("keydown", (event) => {
  const modifier = event.ctrlKey || event.metaKey;
  if (modifier && event.key.toLowerCase() === "k") {
    event.preventDefault();
    openCommandPalette();
    return;
  }
  if (event.key === "Escape") {
    closeSidebar();
  }
});

window.addEventListener("language-changed", () => {
  applyStaticTranslations();
});

/* ------------------------------------------------------------------ */
/* 健康检查                                                            */
/* ------------------------------------------------------------------ */

let engineLabels = {};
let healthTimer = null;

async function loadEngineLabels() {
  try {
    const result = await api.engines();
    engineLabels = Object.fromEntries((result.items || []).map((item) => [item.name, item.label]));
    setState({ ocrEngines: result.items || [] });
  } catch {
    /* 健康检查会展示离线状态 */
  }
}

async function refreshHealth() {
  const dot = $("#engine-dot");
  const label = $("#engine-label");
  const detail = $("#engine-detail");
  const pill = $("#engine-pill");

  try {
    const health = await api.health();
    setState({ health, connected: true });
    const available = health.engines?.available?.length || 0;
    const total = health.engines?.total || 0;

    if (dot) dot.className = `status-dot ${health.status === "ok" ? "ok" : "error"}`;
    if (label) label.textContent = available ? `${available} / ${total} 个 OCR 引擎可用` : "没有可用的 OCR 引擎";
    if (detail) {
      const names = (health.engines?.available || []).map((name) => engineLabels[name] || name);
      detail.textContent = names.length ? `可用：${names.slice(0, 2).join("、")}` : "请前往设置配置引擎";
    }
    if (pill) {
      pill.textContent = health.desktop_mode ? "桌面模式" : "本地服务";
      pill.className = `pill ${health.status === "ok" ? "pill-green" : "pill-amber"}`;
    }
    const footer = $("#footer-status");
    if (footer) footer.textContent = health.desktop_mode ? "桌面模式运行" : "本地服务运行";
  } catch (error) {
    setState({ connected: false });
    if (dot) dot.className = "status-dot error";
    if (label) label.textContent = "服务未连接";
    if (detail) detail.textContent = "请确认后端已启动";
    if (pill) {
      pill.textContent = "离线";
      pill.className = "pill pill-red";
    }
  }
}

loadEngineLabels().then(refreshHealth);
healthTimer = setInterval(refreshHealth, 30_000);

/* ------------------------------------------------------------------ */
/* SSE 实时进度                                                        */
/* ------------------------------------------------------------------ */

const runningBatches = new Set();
let eventSource = null;
let reconnectTimer = null;

const BATCH_EVENTS = [
  "batch_created",
  "batch_update",
  "batch_finished",
  "batch_cancelled",
  "batch_retry",
  "task_started",
  "task_succeeded",
  "task_failed",
  "task_cancelled",
  "ready",
];

function updateBatchBadge() {
  const badge = $("#nav-batch-badge");
  if (!badge) return;
  if (runningBatches.size > 0) {
    badge.hidden = false;
    badge.textContent = String(runningBatches.size);
  } else {
    badge.hidden = true;
    badge.textContent = "";
  }
}

function handleBatchEvent(event) {
  let payload;
  try {
    payload = JSON.parse(event.data);
  } catch {
    return;
  }
  if (payload.type === "ready") return;
  const batch = payload.batch;
  if (batch?.id) {
    if (["queued", "running"].includes(batch.status)) runningBatches.add(batch.id);
    else runningBatches.delete(batch.id);
    updateBatchBadge();
    setState({ activeBatchId: batch.id });
  }
  window.dispatchEvent(new CustomEvent("batch-event", { detail: payload }));
}

function connectEvents() {
  if (eventSource) eventSource.close();
  try {
    eventSource = new EventSource(api.streamUrl());
    for (const name of BATCH_EVENTS) {
      eventSource.addEventListener(name, handleBatchEvent);
    }
    eventSource.onerror = () => {
      // 浏览器会自动重连；若被彻底关闭，则 8 秒后手动重建
      if (eventSource && eventSource.readyState === EventSource.CLOSED) {
        clearTimeout(reconnectTimer);
        reconnectTimer = setTimeout(connectEvents, 8000);
      }
    };
  } catch {
    reconnectTimer = setTimeout(connectEvents, 8000);
  }
}

connectEvents();

/* ------------------------------------------------------------------ */
/* 全局异常提示                                                        */
/* ------------------------------------------------------------------ */

let lastErrorToast = 0;
window.addEventListener("unhandledrejection", (event) => {
  const now = Date.now();
  if (now - lastErrorToast < 4000) return;
  lastErrorToast = now;
  const message = errorMessage(event.reason);
  if (/AbortError|NetworkError/i.test(message)) return;
  toastError("操作未完成", message);
});

window.addEventListener("error", (event) => {
  if (!event.message) return;
  console.error(event.error || event.message);
});

/* ------------------------------------------------------------------ */
/* 首次使用引导                                                        */
/* ------------------------------------------------------------------ */

if (!storage.get("insightdesk.welcomed")) {
  storage.set("insightdesk.welcomed", true);
  setTimeout(() => {
    toastInfo("欢迎使用识文台", "按 Ctrl+K 打开命令面板；上传图片即可开始识别。", { duration: 6000 });
  }, 900);
}

/* ------------------------------------------------------------------ */
/* Service Worker（离线壳）                                            */
/* ------------------------------------------------------------------ */

if ("serviceWorker" in navigator && location.protocol.startsWith("http")) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("./sw.js").catch(() => {
      /* 离线缓存失败不影响主功能 */
    });
  });
}

/* ------------------------------------------------------------------ */
/* 启动                                                                */
/* ------------------------------------------------------------------ */

applyTheme(state.theme);
initRouter();

subscribe((_, changed) => {
  if (changed.route) {
    document.body.dataset.route = changed.route;
  }
});

window.addEventListener("beforeunload", () => {
  if (eventSource) eventSource.close();
  clearInterval(healthTimer);
});
