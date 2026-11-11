/**
 * 网页提取页。
 * 抓取正文、图片与元数据，并按设置自动打开原始网页。
 */

import { api } from "../api.js";
import { copyText, el, escapeHtml, formatNumber, timeAgo } from "../utils.js";
import { icon } from "../icons.js";
import { openExportDialog } from "../components/exportDialog.js";
import { toastError, toastSuccess, toastWarning } from "../components/toast.js";
import { navigate } from "../router.js";

export async function render(container) {
  const page = el("div", { class: "page" });
  page.innerHTML = `
    <div class="page-header">
      <div>
        <h2>${icon("globe", 20)} 网页提取</h2>
        <p>输入文章链接，自动提取标题、作者、正文与配图。提取完成后可自动打开原文，也能一键转为可编辑的文字资产。</p>
      </div>
      <div class="page-actions">
        <a class="btn btn-ghost btn-sm" href="./api/docs" target="_blank" rel="noopener">${icon("terminal", 14)}API 文档</a>
      </div>
    </div>

    <section class="web-hero">
      <h2>把网页正文变成<span style="background:var(--gradient-brand);-webkit-background-clip:text;background-clip:text;color:transparent">可编辑的文字资产</span></h2>
      <p>支持大多数静态文章页。提取过程在服务端完成，具备 SSRF 防护，不会访问内网地址。</p>
      <form class="url-form" id="web-form">
        <div class="url-input-wrap">
          ${icon("link", 16)}
          <input class="input" id="web-url" type="url" placeholder="https://example.com/article" autocomplete="off" spellcheck="false" />
        </div>
        <button class="btn btn-primary btn-lg" type="submit" id="web-extract-btn">
          ${icon("download", 16)}提取正文
        </button>
      </form>
      <div class="url-options">
        <label class="switch">
          <input type="checkbox" id="opt-auto-open" checked />
          <span class="track"></span>
          <span>提取完成后自动打开原文</span>
        </label>
        <label class="switch">
          <input type="checkbox" id="opt-save" checked />
          <span class="track"></span>
          <span>保存提取记录</span>
        </label>
        <label class="switch">
          <input type="checkbox" id="opt-to-document" />
          <span class="track"></span>
          <span>同时转为文字资产</span>
        </label>
      </div>
      <p class="text-xs muted" style="margin-top:12px">示例：https://example.com　·　当前为演示环境时，请使用公开可访问的文章页</p>
    </section>

    <div class="web-layout">
      <div class="col" style="gap:16px">
        <section class="card" id="web-result-card" hidden>
          <div class="article-head">
            <div class="row-between">
              <h2 id="web-title">—</h2>
              <div class="row" style="gap:6px;flex:none" id="web-actions"></div>
            </div>
            <div class="article-meta" id="web-meta"></div>
          </div>
          <div class="article-body" id="web-content"></div>
        </section>

        <div class="card" id="web-placeholder">
          <div class="empty" style="padding:56px 24px">
            <div class="empty-icon">${icon("globe", 26)}</div>
            <strong>粘贴一个文章链接开始提取</strong>
            <p>识文台会清理导航、广告与评论区，只保留正文段落；提取完成后可自动打开原文，方便对照。</p>
          </div>
        </div>

        <section class="card" id="web-images-card" hidden>
          <div class="card-header">
            <div class="card-title">${icon("image", 16)} 页面图片</div>
            <span class="pill pill-soft" id="web-image-count">0 张</span>
          </div>
          <div class="card-body"><div class="image-strip" id="web-images"></div></div>
        </section>
      </div>

      <div class="web-side">
        <section class="card">
          <div class="card-header"><div class="card-title">${icon("book", 16)} 提取说明</div></div>
          <div class="card-body">
            <div class="col" style="gap:10px;font-size:11.5px;color:var(--muted);line-height:1.7">
              <p><strong style="color:var(--text-soft)">自动打开：</strong>开关开启时，提取成功后会尝试在新标签页打开原文；桌面模式下由服务端调用系统默认浏览器。</p>
              <p><strong style="color:var(--text-soft)">正文识别：</strong>使用多候选容器打分算法，自动选择最可能是正文的区域，并剔除脚本、导航、广告与评论区。</p>
              <p><strong style="color:var(--text-soft)">安全限制：</strong>仅允许 http/https，阻止内网、环回与保留地址，逐跳校验重定向，防止 SSRF。</p>
              <p><strong style="color:var(--text-soft)">动态页面：</strong>依赖 JavaScript 渲染的页面可能提取不到正文，请改用静态文章页。</p>
            </div>
          </div>
        </section>

        <section class="card">
          <div class="card-header">
            <div class="card-title">${icon("clock", 16)} 最近提取</div>
            <button class="icon-btn" type="button" id="web-history-refresh" title="刷新">${icon("refresh", 14)}</button>
          </div>
          <div class="card-body" id="web-history" style="padding-top:8px"></div>
        </section>
      </div>
    </div>
  `;
  container.append(page);

  const form = page.querySelector("#web-form");
  const urlInput = page.querySelector("#web-url");
  const extractButton = page.querySelector("#web-extract-btn");
  const autoOpenSwitch = page.querySelector("#opt-auto-open");
  const saveSwitch = page.querySelector("#opt-save");
  const toDocumentSwitch = page.querySelector("#opt-to-document");
  const resultCard = page.querySelector("#web-result-card");
  const placeholder = page.querySelector("#web-placeholder");
  const imagesCard = page.querySelector("#web-images-card");
  const historyBox = page.querySelector("#web-history");

  let currentRecord = null;
  let extracting = false;

  try {
    const settings = await api.settings();
    autoOpenSwitch.checked = Boolean(settings.values?.auto_open_web);
  } catch {
    /* 使用默认值 */
  }

  async function loadHistory() {
    try {
      const result = await api.webHistory(15);
      historyBox.innerHTML = "";
      if (!result.items?.length) {
        historyBox.innerHTML = '<p class="text-xs muted" style="padding:8px 0">还没有提取记录</p>';
        return;
      }
      for (const item of result.items) {
        const row = el(
          "div",
          { class: "web-history-item", role: "button", tabindex: "0" },
          el("span", { class: "web-history-favicon", html: icon("globe", 13) }),
          el(
            "div",
            { style: { flex: "1", minWidth: "0" } },
            el("div", { class: "recent-title", text: item.title || item.url }),
            el("div", { class: "recent-meta", text: `${item.site || "网页"} · ${formatNumber(item.word_count)} 字 · ${timeAgo(item.created_at)}` }),
          ),
        );
        row.addEventListener("click", async () => {
          try {
            const record = await api.webRecord(item.id);
            renderResult(record, { fromHistory: true });
          } catch (error) {
            toastError("记录加载失败", error.message || String(error));
          }
        });
        row.addEventListener("keydown", (event) => {
          if (event.key === "Enter") row.click();
        });
        historyBox.append(row);
      }
    } catch {
      historyBox.innerHTML = '<p class="text-xs muted" style="padding:8px 0">历史记录加载失败</p>';
    }
  }

  function renderResult(record, { fromHistory = false } = {}) {
    currentRecord = record;
    placeholder.hidden = true;
    resultCard.hidden = false;
    page.querySelector("#web-title").textContent = record.title || record.url;
    page.querySelector("#web-content").textContent = record.content || "";

    const meta = page.querySelector("#web-meta");
    meta.innerHTML = "";
    const chips = [
      record.site ? { icon: "globe", text: record.site } : null,
      record.author ? { icon: "users", text: record.author } : null,
      record.published_at ? { icon: "clock", text: String(record.published_at).slice(0, 10) } : null,
      { icon: "fileText", text: `${formatNumber(record.word_count || 0)} 字` },
      fromHistory ? { icon: "archive", text: `提取于 ${timeAgo(record.created_at)}` } : null,
    ].filter(Boolean);
    for (const chip of chips) {
      meta.append(
        el("span", {
          class: "pill pill-soft",
          html: `${icon(chip.icon, 11)}<span>${escapeHtml(chip.text)}</span>`,
        }),
      );
    }

    const actions = page.querySelector("#web-actions");
    actions.innerHTML = "";
    actions.append(
      el("button", {
        class: "btn btn-primary btn-sm",
        type: "button",
        html: `${icon("external", 13)}打开原文`,
        onclick: () => openSource(record.final_url || record.url),
      }),
      el("button", {
        class: "btn btn-ghost btn-sm",
        type: "button",
        html: `${icon("copy", 13)}复制正文`,
        onclick: async () => {
          const ok = await copyText(record.content || "");
          if (ok) toastSuccess("已复制", "网页正文已复制到剪贴板");
          else toastError("复制失败", "请手动选择正文");
        },
      }),
      el("button", {
        class: "btn btn-ghost btn-sm",
        type: "button",
        html: `${icon("fileText", 13)}转为文字资产`,
        disabled: Boolean(record.document_id) || !record.id,
        onclick: () => convertToDocument(record),
      }),
      el("button", {
        class: "btn btn-ghost btn-sm",
        type: "button",
        html: `${icon("download", 13)}导出`,
        disabled: !record.document_id,
        onclick: () => openExportDialog([record.document_id], { title: "导出网页正文" }),
      }),
    );

    const imagesCardNode = page.querySelector("#web-images");
    const images = (record.images || []).filter(Boolean);
    imagesCard.hidden = images.length === 0;
    page.querySelector("#web-image-count").textContent = `${images.length} 张`;
    imagesCardNode.innerHTML = "";
    for (const url of images.slice(0, 18)) {
      imagesCardNode.append(
        el(
          "a",
          { href: url, target: "_blank", rel: "noopener noreferrer", title: "打开图片" },
          el("img", { src: url, alt: "页面配图", loading: "lazy" }),
        ),
      );
    }
  }

  async function openSource(url) {
    if (!url) return;
    try {
      const result = await api.webOpen(url);
      if (result.opened) {
        toastSuccess("已打开原文", "由系统默认浏览器打开");
        return;
      }
    } catch {
      /* 回退到前端打开 */
    }
    window.open(url, "_blank", "noopener,noreferrer");
  }

  async function convertToDocument(record) {
    if (!record.id) return;
    try {
      const result = await api.webToDocument(record.id);
      record.document_id = result.document.id;
      toastSuccess("已转为文字资产", "可在历史记录中继续编辑与导出");
      renderResult(record, { fromHistory: true });
      loadHistory();
      setTimeout(() => navigate("history", { doc: result.document.id }), 500);
    } catch (error) {
      toastError("转换失败", error.message || String(error));
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (extracting) return;
    const url = urlInput.value.trim();
    if (!/^https?:\/\//i.test(url)) {
      toastWarning("请输入完整链接", "链接需要以 http:// 或 https:// 开头");
      urlInput.focus();
      return;
    }

    extracting = true;
    extractButton.disabled = true;
    extractButton.innerHTML = '<span class="spinner"></span>提取中…';
    extractButton.style.minWidth = "120px";

    try {
      const result = await api.webExtract({
        url,
        save: saveSwitch.checked,
        auto_open: autoOpenSwitch.checked,
        to_document: toDocumentSwitch.checked,
      });

      renderResult(result);
      loadHistory();

      if (autoOpenSwitch.checked && !result.auto_opened && result.final_url) {
        window.open(result.final_url, "_blank", "noopener,noreferrer");
      }

      toastSuccess(
        "提取完成",
        `${formatNumber(result.word_count || 0)} 字 · 耗时 ${Math.round(result.elapsed_ms || 0)} ms${result.auto_opened ? " · 已打开原文" : ""}`,
      );
    } catch (error) {
      toastError("提取失败", error.message || String(error));
    } finally {
      extracting = false;
      extractButton.disabled = false;
      extractButton.innerHTML = `${icon("download", 16)}提取正文`;
    }
  });

  page.querySelector("#web-history-refresh").addEventListener("click", () => {
    loadHistory();
    toastSuccess("已刷新", "最近提取记录已更新");
  });

  urlInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  await loadHistory();

  return {
    destroy() {
      /* 无全局监听需要清理 */
    },
  };
}
