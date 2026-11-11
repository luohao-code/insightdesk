/**
 * 工作台看板。
 * 展示文字资产总览、近七日趋势、引擎分布、快捷入口与系统状态。
 */

import { api } from "../api.js";
import { el, formatDate, formatDuration, formatNumber, timeAgo } from "../utils.js";
import { icon } from "../icons.js";
import { navigate } from "../router.js";
import { renderEngineBars, renderTrendChart } from "../components/chart.js";
import { toastError } from "../components/toast.js";
import { APP_VERSION } from "../config.js";

const QUICK_ACTIONS = [
  { route: "ocr", icon: "scan", title: "单图识别", desc: "上传或粘贴截图" },
  { route: "batch", icon: "layers", title: "批量处理", desc: "一次识别上百张" },
  { route: "web", icon: "globe", title: "网页提取", desc: "抓取正文并打开" },
  { route: "ai", icon: "sparkles", title: "AI 加工", desc: "翻译、摘要与问答" },
];

export async function render(container) {
  const page = el("div", { class: "page" });
  page.innerHTML = `
    <section class="hero">
      <div class="hero-content">
        <span class="hero-eyebrow">${icon("sparkles", 12)} OCR × AI WORKBENCH</span>
        <h2>让每一张图片里的文字<br /><span class="gradient-text">都能被理解与复用</span></h2>
        <p>上传图片或提取网页，识文台会完成识别、编辑、翻译、摘要与归档。所有数据保存在本机，密钥不会离开服务端。</p>
        <div class="hero-actions">
          <button class="btn btn-primary btn-lg" type="button" data-go="ocr">${icon("scan", 16)}开始识别</button>
          <button class="btn btn-secondary btn-lg" type="button" data-go="batch">${icon("layers", 16)}批量处理</button>
          <button class="btn btn-ghost btn-lg" type="button" data-go="web">${icon("globe", 16)}提取网页</button>
        </div>
      </div>
      <div class="hero-visual" aria-hidden="true">
        <div class="hero-orb">
          <div class="hero-orb-label">
            <strong id="hero-total">0</strong>
            <span>Text Assets</span>
          </div>
        </div>
        <span class="hero-badge badge-a">${icon("zap", 13)}<span id="hero-today">今日 +0</span></span>
        <span class="hero-badge badge-b">${icon("shield", 13)}<span id="hero-rate">成功率 —</span></span>
      </div>
    </section>

    <div id="dashboard-alert"></div>

    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-top">
          <span class="stat-label">文字资产</span>
          <span class="stat-icon">${icon("archive", 16)}</span>
        </div>
        <div class="stat-value"><span id="stat-documents">0</span><small>条</small></div>
        <div class="stat-delta">累计 <span id="stat-chars">0</span> 字符</div>
      </div>
      <div class="stat-card">
        <div class="stat-top">
          <span class="stat-label">今日新增</span>
          <span class="stat-icon">${icon("trending", 16)}</span>
        </div>
        <div class="stat-value"><span id="stat-today">0</span><small>条</small></div>
        <div class="stat-delta up">${icon("activity", 12)} 实时统计</div>
      </div>
      <div class="stat-card">
        <div class="stat-top">
          <span class="stat-label">识别成功率</span>
          <span class="stat-icon">${icon("shield", 16)}</span>
        </div>
        <div class="stat-value"><span id="stat-rate">0</span><small>%</small></div>
        <div class="stat-delta"><span id="stat-batches">0</span> 个批次 · <span id="stat-running">0</span> 运行中</div>
      </div>
      <div class="stat-card">
        <div class="stat-top">
          <span class="stat-label">平均耗时</span>
          <span class="stat-icon">${icon("clock", 16)}</span>
        </div>
        <div class="stat-value" id="stat-duration">—</div>
        <div class="stat-delta">AI 调用 <span id="stat-ai">0</span> 次 · 网页 <span id="stat-web">0</span> 篇</div>
      </div>
    </div>

    <div class="dashboard-grid">
      <div class="col" style="gap:16px">
        <section class="card">
          <div class="card-header">
            <div class="card-title">${icon("barChart", 16)} 近七日识别趋势</div>
            <div class="row" style="gap:12px">
              <div class="chart-legend"><span><i></i>每日新增</span></div>
              <button class="icon-btn" id="dashboard-refresh" type="button" title="刷新">${icon("refresh", 15)}</button>
            </div>
          </div>
          <div class="chart-shell"><div id="trend-chart"></div></div>
        </section>

        <section class="card">
          <div class="card-header">
            <div class="card-title">${icon("fileText", 16)} 最近识别</div>
            <button class="btn btn-ghost btn-sm" type="button" data-go="history">查看全部 ${icon("chevronRight", 13)}</button>
          </div>
          <div class="recent-list" id="recent-list"></div>
        </section>
      </div>

      <div class="col" style="gap:16px">
        <section class="card">
          <div class="card-header">
            <div class="card-title">${icon("cpu", 16)} 引擎使用分布</div>
            <span class="pill pill-soft" id="engine-count">0 个引擎</span>
          </div>
          <div class="card-body"><div id="engine-bars"></div></div>
        </section>

        <section class="card">
          <div class="card-header">
            <div class="card-title">${icon("zap", 16)} 快捷入口</div>
          </div>
          <div class="card-body">
            <div class="quick-actions">
              ${QUICK_ACTIONS.map(
                (item) => `
                <button class="qa-card" type="button" data-go="${item.route}">
                  <span class="qa-icon">${icon(item.icon, 15)}</span>
                  <strong>${item.title}</strong>
                  <span>${item.desc}</span>
                </button>`,
              ).join("")}
            </div>
          </div>
        </section>

        <section class="card">
          <div class="card-header">
            <div class="card-title">${icon("activity", 16)} 运行状态</div>
            <span class="pill pill-green" id="system-pill"><span class="dot"></span>检测中</span>
          </div>
          <div class="card-body" style="padding-top:10px">
            <div class="kv">
              <div class="kv-row"><span class="kv-key">服务版本</span><span class="kv-value">v${APP_VERSION}</span></div>
              <div class="kv-row"><span class="kv-key">数据库</span><span class="kv-value" id="sys-db">—</span></div>
              <div class="kv-row"><span class="kv-key">可用 OCR 引擎</span><span class="kv-value" id="sys-engines">—</span></div>
              <div class="kv-row"><span class="kv-key">运行时长</span><span class="kv-value" id="sys-uptime">—</span></div>
              <div class="kv-row"><span class="kv-key">运行模式</span><span class="kv-value" id="sys-mode">—</span></div>
            </div>
          </div>
        </section>
      </div>
    </div>
  `;

  container.append(page);

  // 页面内跳转
  page.querySelectorAll("[data-go]").forEach((button) => {
    button.addEventListener("click", () => navigate(button.dataset.go));
  });

  const alertBox = page.querySelector("#dashboard-alert");
  let disposed = false;
  let timer = null;

  function showAlert(message) {
    alertBox.innerHTML = "";
    if (!message) return;
    const notice = el(
      "div",
      { class: "notice notice-warning", style: { marginTop: "4px" } },
      el("span", { html: icon("alert", 15) }),
      el("span", { text: message }),
    );
    alertBox.append(notice);
  }

  async function load({ silent = false } = {}) {
    try {
      const [stats, health] = await Promise.all([api.stats(), api.health()]);
      if (disposed) return;
      showAlert("");
      paintStats(stats);
      paintHealth(health);
    } catch (error) {
      if (disposed) return;
      showAlert(`数据加载失败：${error.message || error}`);
      if (!silent) toastError("看板加载失败", error.message || String(error));
    }
  }

  function paintStats(stats) {
    setText("#stat-documents", formatNumber(stats.documents));
    setText("#stat-chars", formatNumber(stats.total_chars));
    setText("#stat-today", formatNumber(stats.today_documents));
    setText("#stat-rate", Number(stats.success_rate || 0).toFixed(1));
    setText("#stat-batches", formatNumber(stats.batches));
    setText("#stat-running", formatNumber(stats.running_batches));
    setText("#stat-ai", formatNumber(stats.ai_runs));
    setText("#stat-web", formatNumber(stats.web_extractions));
    setText("#hero-total", formatNumber(stats.documents));
    setText("#hero-today", `今日 +${formatNumber(stats.today_documents)}`);
    setText("#hero-rate", `成功率 ${Number(stats.success_rate || 0).toFixed(0)}%`);

    const durationNode = page.querySelector("#stat-duration");
    if (durationNode) durationNode.textContent = stats.avg_task_ms ? formatDuration(stats.avg_task_ms) : "—";

    renderTrendChart(page.querySelector("#trend-chart"), stats.trend || []);

    const usage = stats.engine_usage || [];
    renderEngineBars(page.querySelector("#engine-bars"), usage);
    setText("#engine-count", `${usage.length} 个引擎`);

    const recent = page.querySelector("#recent-list");
    recent.innerHTML = "";
    if (!stats.recent?.length) {
      recent.innerHTML = `
        <div class="empty" style="padding:32px">
          <div class="empty-icon">${icon("inbox", 22)}</div>
          <strong>还没有识别记录</strong>
          <p>上传第一张图片，识别结果会自动出现在这里。</p>
          <button class="btn btn-primary btn-sm" type="button" data-empty-go="ocr">开始识别</button>
        </div>`;
      recent.querySelector("[data-empty-go]")?.addEventListener("click", () => navigate("ocr"));
      return;
    }

    for (const doc of stats.recent) {
      const item = el("div", { class: "recent-item", role: "button", tabindex: "0" });
      if (doc.thumbnail_url) {
        item.append(
          el("img", { class: "recent-thumb", src: doc.thumbnail_url, alt: doc.title, loading: "lazy" }),
        );
      } else {
        item.append(
          el("span", { class: "recent-thumb placeholder", html: icon(doc.source_type === "web" ? "globe" : "fileText", 16) }),
        );
      }
      item.append(
        el(
          "div",
          { class: "recent-main" },
          el("div", { class: "recent-title", text: doc.title || "未命名文档" }),
          el("div", {
            class: "recent-meta",
            text: `${doc.source_type === "web" ? "网页" : "图片"} · ${formatNumber(doc.char_count)} 字 · ${timeAgo(doc.updated_at)}`,
          }),
        ),
      );
      item.append(
        el("span", { class: doc.favorite ? "pill pill-amber" : "pill pill-soft", text: doc.favorite ? "收藏" : doc.engine || "—" }),
      );
      const open = () => navigate("history", { doc: doc.id });
      item.addEventListener("click", open);
      item.addEventListener("keydown", (event) => {
        if (event.key === "Enter") open();
      });
      recent.append(item);
    }
  }

  function paintHealth(health) {
    const pill = page.querySelector("#system-pill");
    const ok = health.status === "ok";
    pill.className = `pill ${ok ? "pill-green" : "pill-amber"}`;
    pill.innerHTML = '<span class="dot"></span>' + (ok ? "运行正常" : "降级运行");
    setText("#sys-db", health.database?.status === "ok" ? "连接正常" : "异常");
    setText("#sys-engines", `${health.engines?.available?.length || 0} / ${health.engines?.total || 0}`);
    setText("#sys-uptime", formatUptime(health.uptime_seconds));
    setText("#sys-mode", health.desktop_mode ? "桌面模式" : "浏览器模式");

    const footer = document.querySelector("#footer-status");
    if (footer) footer.textContent = health.desktop_mode ? "桌面模式运行" : "本地服务运行";
  }

  function setText(selector, value) {
    const node = page.querySelector(selector);
    if (node) node.textContent = value;
  }

  function formatUptime(seconds) {
    const value = Number(seconds || 0);
    if (value < 60) return `${Math.round(value)} 秒`;
    if (value < 3600) return `${Math.round(value / 60)} 分钟`;
    if (value < 86400) return `${(value / 3600).toFixed(1)} 小时`;
    return `${(value / 86400).toFixed(1)} 天`;
  }

  page.querySelector("#dashboard-refresh")?.addEventListener("click", async (event) => {
    const button = event.currentTarget;
    button.disabled = true;
    button.style.opacity = "0.5";
    await load();
    button.disabled = false;
    button.style.opacity = "";
  });

  await load();
  timer = setInterval(() => load({ silent: true }), 60_000);

  return {
    destroy() {
      disposed = true;
      if (timer) clearInterval(timer);
    },
  };
}
