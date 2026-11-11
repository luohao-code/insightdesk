/**
 * OCR 工作台。
 * 左侧上传与参数，右侧识别结果编辑与 AI 快速处理。
 */

import { api } from "../api.js";
import {
  copyText,
  el,
  formatBytes,
  formatDuration,
  formatNumber,
  titleFromFilename,
} from "../utils.js";
import { icon } from "../icons.js";
import { navigate } from "../router.js";
import { createUploader } from "../components/uploader.js";
import { createEditor } from "../components/editor.js";
import { openExportDialog } from "../components/exportDialog.js";
import { confirmDialog, formDialog } from "../components/modal.js";
import { toastError, toastSuccess, toastWarning } from "../components/toast.js";

const LANGUAGES = [
  { value: "auto", label: "中英混合（推荐）" },
  { value: "zh", label: "中文为主" },
  { value: "en", label: "英文为主" },
];

const AI_ACTIONS = [
  { action: "translate", label: "翻译", icon: "globe" },
  { action: "summarize", label: "摘要", icon: "fileText" },
  { action: "keywords", label: "关键词", icon: "tag" },
  { action: "qa", label: "问答", icon: "message" },
];

export async function render(container) {
  const page = el("div", { class: "page" });
  page.innerHTML = `
    <div class="page-header">
      <div>
        <h2>${icon("scan", 20)} OCR 图片识别</h2>
        <p>上传图片，自动提取中英文印刷体文字。识别结果可直接编辑、复制、导出，或交给 AI 继续加工。</p>
      </div>
      <div class="page-actions">
        <button class="btn btn-ghost btn-sm" type="button" data-go="batch">${icon("layers", 14)}批量任务</button>
        <button class="btn btn-ghost btn-sm" type="button" data-go="history">${icon("archive", 14)}历史记录</button>
      </div>
    </div>

    <div class="ocr-grid">
      <div class="ocr-side">
        <section class="card upload-panel">
          <div class="card-header">
            <div class="card-title">${icon("image", 16)} 待识别图片 <span class="pill pill-soft" id="image-count">0 张</span></div>
            <button class="btn btn-ghost btn-sm" type="button" id="clear-images">清空</button>
          </div>
          <div class="card-body" id="uploader-slot"></div>
        </section>

        <section class="card" id="preview-card" hidden>
          <div class="card-header">
            <div class="card-title">${icon("eye", 16)} 图片预览</div>
            <button class="icon-btn" type="button" id="preview-open" title="在新标签页打开原图">${icon("external", 14)}</button>
          </div>
          <div class="image-preview">
            <img id="preview-image" alt="待识别图片预览" />
            <div class="image-preview-bar">
              <span id="preview-name" class="truncate"></span>
              <span id="preview-meta" class="mono"></span>
            </div>
          </div>
        </section>

        <section class="card">
          <div class="card-header"><div class="card-title">${icon("sliders", 16)} 识别设置</div></div>
          <div class="card-body">
            <div class="control-list">
              <div class="field">
                <label class="field-label" for="ocr-engine">OCR 引擎</label>
                <select class="select" id="ocr-engine"></select>
                <p class="field-hint" id="engine-hint">正在加载引擎…</p>
              </div>
              <div class="field">
                <label class="field-label" for="ocr-language">语言</label>
                <select class="select" id="ocr-language">
                  ${LANGUAGES.map((item) => `<option value="${item.value}">${item.label}</option>`).join("")}
                </select>
              </div>
              <div class="row" style="justify-content:space-between">
                <label class="checkbox"><input type="checkbox" id="opt-grayscale" /><span class="box"></span>灰度化</label>
                <label class="checkbox"><input type="checkbox" id="opt-autocontrast" /><span class="box"></span>增强对比度</label>
              </div>
              <label class="switch">
                <input type="checkbox" id="opt-merge" checked />
                <span class="track"></span>
                <span class="text-sm muted">合并 OCR 软换行</span>
              </label>
              <div class="notice" style="margin-top:2px">
                <span>${icon("info", 15)}</span>
                <span>预处理适合低质量扫描件；普通截图保持默认即可。</span>
              </div>
            </div>
          </div>
          <div class="card-footer" style="display:block">
            <button class="btn btn-primary btn-block" type="button" id="recognize-btn" disabled>
              ${icon("play", 15)}开始识别
            </button>
            <div class="progress progress-sm" id="recognize-progress" style="margin-top:10px;display:none">
              <div class="progress-bar striped" style="width:60%"></div>
            </div>
          </div>
        </section>
      </div>

      <div class="ocr-main">
        <div id="ocr-notice"></div>

        <section class="card">
          <div class="card-header">
            <div class="doc-toolbar">
              <input class="doc-title-input" id="doc-title" value="未命名文档" aria-label="文档标题" />
              <span class="pill pill-soft" id="doc-engine">等待识别</span>
              <span class="pill pill-soft" id="doc-chars">0 字</span>
            </div>
            <div class="result-actions">
              <button class="btn btn-ghost btn-sm" type="button" id="doc-export" disabled>${icon("download", 13)}导出</button>
              <button class="btn btn-ghost btn-sm" type="button" id="doc-delete" disabled>${icon("trash", 13)}删除</button>
            </div>
          </div>
          <div class="card-body" style="padding:0" id="editor-slot"></div>
        </section>

        <section class="card">
          <div class="card-header">
            <div class="card-title">${icon("sparkles", 16)} AI 快速处理</div>
            <div class="row" style="gap:8px">
              <select class="select input-sm" id="ai-target" style="width:112px" title="翻译目标语言">
                <option value="en">译为英文</option>
                <option value="zh">译为中文</option>
                <option value="ja">译为日文</option>
                <option value="ko">译为韩文</option>
              </select>
              <span class="pill pill-soft" id="ai-provider">演示引擎</span>
            </div>
          </div>
          <div class="card-body">
            <div class="ai-quick">
              ${AI_ACTIONS.map(
                (item) =>
                  `<button class="btn btn-secondary" type="button" data-ai="${item.action}">${icon(item.icon, 14)}${item.label}</button>`,
              ).join("")}
            </div>
            <div class="ai-inline-result" id="ai-result"></div>
          </div>
        </section>
      </div>
    </div>
  `;

  container.append(page);
  page.querySelectorAll("[data-go]").forEach((button) => {
    button.addEventListener("click", () => navigate(button.dataset.go));
  });

  /* ------------------------------------------------------------------ */
  /* 组件                                                                */
  /* ------------------------------------------------------------------ */

  const uploader = createUploader({
    multiple: true,
    maxFiles: 30,
    title: "拖拽图片、点击选择或粘贴截图",
    subtitle: "支持 PNG / JPG / WEBP / BMP / TIFF，单张不超过 20MB",
    onUploaded: (uploaded) => {
      updateImageCount();
      if (!selectedImage && uploaded.length) selectImage(uploaded[0]);
    },
    onSelect: (image) => selectImage(image),
    onChange: () => updateImageCount(),
  });
  page.querySelector("#uploader-slot").append(uploader.element);

  const editor = createEditor({
    minHeight: 340,
    placeholder: "识别结果会显示在这里。你可以直接修改，修改会自动保存到历史记录。",
    onChange: () => scheduleSave(),
    onSave: () => saveDocument(),
  });
  page.querySelector("#editor-slot").append(editor.element);

  let selectedImage = null;
  let currentDocument = null;
  let savingTimer = null;
  let recognizing = false;
  let lastAI = null;

  const engineSelect = page.querySelector("#ocr-engine");
  const engineHint = page.querySelector("#engine-hint");
  const recognizeButton = page.querySelector("#recognize-btn");
  const recognizeProgress = page.querySelector("#recognize-progress");
  const titleInput = page.querySelector("#doc-title");
  const engineBadge = page.querySelector("#doc-engine");
  const charsBadge = page.querySelector("#doc-chars");
  const exportButton = page.querySelector("#doc-export");
  const deleteButton = page.querySelector("#doc-delete");
  const noticeBox = page.querySelector("#ocr-notice");
  const aiProviderBadge = page.querySelector("#ai-provider");

  /* ------------------------------------------------------------------ */
  /* 引擎加载                                                            */
  /* ------------------------------------------------------------------ */

  let engineItems = [];
  try {
    const engines = await api.engines();
    engineItems = engines.items || [];
    engineSelect.innerHTML = "";
    for (const item of engineItems) {
      const option = el("option", {
        value: item.name,
        text: `${item.label}${item.available ? "" : "（不可用）"}`,
        disabled: !item.available,
      });
      if (item.name === engines.default && item.available) option.selected = true;
      engineSelect.append(option);
    }
    const fallback = engineItems.find((item) => item.available);
    if (!engineSelect.value && fallback) engineSelect.value = fallback.name;
    updateEngineHint();
  } catch (error) {
    engineHint.textContent = `引擎加载失败：${error.message || error}`;
    toastError("无法加载 OCR 引擎", error.message || String(error));
  }

  function updateEngineHint() {
    const selected = engineItems.find((item) => item.name === engineSelect.value);
    if (!selected) {
      engineHint.textContent = "未选择引擎";
      return;
    }
    engineHint.textContent = selected.available ? selected.description : selected.reason;
    const demo = selected.name === "mock";
    engineBadge.textContent = selected.label;
    engineBadge.className = demo ? "pill pill-amber" : "pill pill-green";
  }

  engineSelect.addEventListener("change", updateEngineHint);

  // 同步 AI 引擎标签
  try {
    const providers = await api.aiProviders();
    const current = providers.items.find((item) => item.name === providers.default);
    if (current) {
      aiProviderBadge.textContent = current.label;
      aiProviderBadge.className = current.name === "mock" ? "pill pill-amber" : "pill pill-green";
    }
  } catch {
    /* 非关键信息 */
  }

  /* ------------------------------------------------------------------ */
  /* 图片选择                                                            */
  /* ------------------------------------------------------------------ */

  function updateImageCount() {
    const count = uploader.getImages().length;
    page.querySelector("#image-count").textContent = `${count} 张`;
    if (!count) {
      recognizeButton.disabled = true;
      page.querySelector("#preview-card").hidden = true;
    }
  }

  function selectImage(image) {
    selectedImage = image;
    uploader.setActive(image.id);
    const card = page.querySelector("#preview-card");
    card.hidden = false;
    const img = page.querySelector("#preview-image");
    img.src = image.url;
    img.alt = image.filename;
    page.querySelector("#preview-name").textContent = image.filename;
    page.querySelector("#preview-meta").textContent = `${image.width}×${image.height} · ${formatBytes(image.size_bytes)}`;
    page.querySelector("#preview-open").onclick = () => window.open(image.url, "_blank", "noopener");
    recognizeButton.disabled = recognizing;
  }

  page.querySelector("#clear-images").addEventListener("click", () => {
    uploader.clear();
    selectedImage = null;
    page.querySelector("#preview-card").hidden = true;
    updateImageCount();
  });

  /* ------------------------------------------------------------------ */
  /* 识别                                                                */
  /* ------------------------------------------------------------------ */

  recognizeButton.addEventListener("click", recognize);

  async function recognize() {
    if (recognizing) return;
    if (!selectedImage) {
      toastWarning("请先选择图片", "上传图片后点击缩略图选中，再进行识别");
      return;
    }

    recognizing = true;
    recognizeButton.disabled = true;
    recognizeButton.innerHTML = '<span class="spinner"></span>识别中…';
    recognizeProgress.style.display = "block";

    try {
      const result = await api.recognize({
        image_id: selectedImage.id,
        engine: engineSelect.value || null,
        language: page.querySelector("#ocr-language").value,
        grayscale: page.querySelector("#opt-grayscale").checked,
        autocontrast: page.querySelector("#opt-autocontrast").checked,
        merge_lines: page.querySelector("#opt-merge").checked,
      });

      currentDocument = {
        id: result.document_id,
        title: titleFromFilename(selectedImage.filename),
      };
      titleInput.value = currentDocument.title;
      editor.setValue(result.text);
      editor.markSaved("已存入历史");
      editor.setEngineLabel(`${result.engine_label} · ${formatDuration(result.duration_ms)}`);
      engineBadge.textContent = result.engine_label;
      engineBadge.className = result.demo ? "pill pill-amber" : "pill pill-green";
      charsBadge.textContent = `${formatNumber(result.char_count)} 字`;
      exportButton.disabled = !result.document_id;
      deleteButton.disabled = !result.document_id;

      noticeBox.innerHTML = "";
      if (result.demo) {
        noticeBox.append(
          el(
            "div",
            { class: "notice notice-warning" },
            el("span", { html: icon("alert", 15) }),
            el(
              "span",
              {},
              el("strong", { text: "当前使用演示引擎：" }),
              el("span", {
                text:
                  result.notice ||
                  "文本为模拟结果。安装 RapidOCR 或在设置中配置百度/腾讯 OCR 密钥后，即可获得真实识别结果。",
              }),
            ),
          ),
        );
      } else if (result.notice) {
        noticeBox.append(
          el(
            "div",
            { class: "notice" },
            el("span", { html: icon("info", 15) }),
            el("span", { text: result.notice }),
          ),
        );
      }

      toastSuccess("识别完成", `${result.engine_label} · ${formatNumber(result.char_count)} 字 · ${formatDuration(result.duration_ms)}`);
    } catch (error) {
      toastError("识别失败", error.message || String(error));
    } finally {
      recognizing = false;
      recognizeButton.disabled = !selectedImage;
      recognizeButton.innerHTML = `${icon("play", 15)}开始识别`;
      recognizeProgress.style.display = "none";
    }
  }

  /* ------------------------------------------------------------------ */
  /* 保存                                                                */
  /* ------------------------------------------------------------------ */

  function scheduleSave() {
    if (!currentDocument?.id) return;
    charsBadge.textContent = `${formatNumber(editor.getValue().replace(/\s/g, "").length)} 字`;
    clearTimeout(savingTimer);
    editor.markDirty();
    savingTimer = setTimeout(() => saveDocument({ silent: true }), 900);
  }

  async function saveDocument({ silent = false } = {}) {
    if (!currentDocument?.id) {
      if (!silent) toastWarning("还没有识别结果", "请先上传图片并完成识别");
      return false;
    }
    clearTimeout(savingTimer);
    editor.markSaving();
    try {
      const updated = await api.updateDocument(currentDocument.id, {
        content: editor.getValue(),
        title: titleInput.value.trim() || currentDocument.title,
      });
      currentDocument.title = updated.title;
      charsBadge.textContent = `${formatNumber(updated.char_count)} 字`;
      editor.markSaved("已保存");
      if (!silent) toastSuccess("已保存", "标题与正文已更新");
      return true;
    } catch (error) {
      toastError("保存失败", error.message || String(error));
      return false;
    }
  }

  titleInput.addEventListener("change", () => saveDocument({ silent: true }));

  /* ------------------------------------------------------------------ */
  /* 导出 / 删除                                                         */
  /* ------------------------------------------------------------------ */

  exportButton.addEventListener("click", () => {
    if (!currentDocument?.id) return;
    openExportDialog([currentDocument.id], { title: "导出识别结果" });
  });

  deleteButton.addEventListener("click", async () => {
    if (!currentDocument?.id) return;
    const confirmed = await confirmDialog({
      title: "删除这条记录？",
      message: "删除后，正文、原图与缩略图都会从本机移除，且无法恢复。",
      confirmText: "删除",
      danger: true,
    });
    if (!confirmed) return;
    try {
      await api.deleteDocument(currentDocument.id);
      currentDocument = null;
      editor.setValue("");
      editor.setEngineLabel("");
      titleInput.value = "未命名文档";
      engineBadge.textContent = "等待识别";
      engineBadge.className = "pill pill-soft";
      charsBadge.textContent = "0 字";
      exportButton.disabled = true;
      deleteButton.disabled = true;
      noticeBox.innerHTML = "";
      toastSuccess("已删除", "记录已从历史中移除");
    } catch (error) {
      toastError("删除失败", error.message || String(error));
    }
  });

  /* ------------------------------------------------------------------ */
  /* AI 快速处理                                                         */
  /* ------------------------------------------------------------------ */

  const aiResultBox = page.querySelector("#ai-result");

  page.querySelectorAll("[data-ai]").forEach((button) => {
    button.addEventListener("click", () => runAI(button.dataset.ai, button));
  });

  async function runAI(action, button) {
    const text = editor.getValue().trim();
    if (!text) {
      toastWarning("没有可处理的文本", "请先识别图片或粘贴内容");
      return;
    }

    let options = {};
    if (action === "translate") {
      options = { target_language: page.querySelector("#ai-target").value };
    } else if (action === "summarize") {
      options = { length: "中等（约 200–300 字）" };
    } else if (action === "keywords") {
      options = { count: 10 };
    } else if (action === "qa") {
      const question = await askQuestion();
      if (!question) return;
      options = { question };
    }

    const original = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<span class="spinner" style="border-color:var(--border);border-top-color:var(--accent)"></span>处理中…';
    aiResultBox.innerHTML = "";

    try {
      const result = await api.aiProcess({
        action,
        document_id: currentDocument?.id || null,
        text,
        options,
      });
      renderAIResult(result);
    } catch (error) {
      aiResultBox.innerHTML = "";
      aiResultBox.append(
        el(
          "div",
          { class: "notice notice-danger" },
          el("span", { html: icon("alert", 15) }),
          el("span", { text: `处理失败：${error.message || error}` }),
        ),
      );
      toastError("AI 处理失败", error.message || String(error));
    } finally {
      button.disabled = false;
      button.innerHTML = original;
    }
  }

  function askQuestion() {
    return new Promise((resolve) => {
      formDialog({
        title: "基于原文提问",
        subtitle: "AI 会仅依据当前编辑器中的文本作答",
        fields: [
          {
            name: "question",
            label: "你的问题",
            type: "textarea",
            rows: 3,
            placeholder: "例如：这段文字的主要结论是什么？",
          },
        ],
        submitText: "提问",
        onSubmit: (values) => {
          resolve(values.question || "");
          return true;
        },
        onClose: () => resolve(""),
      });
    });
  }

  function renderAIResult(result) {
    lastAI = result;
    aiResultBox.innerHTML = "";
    const meta = el(
      "div",
      { class: "row wrap", style: { gap: "8px", marginBottom: "10px" } },
      el("span", { class: "pill pill-accent", text: result.provider_label || result.provider }),
      el("span", { class: "pill pill-soft", text: result.model || "默认模型" }),
      el("span", { class: "pill pill-soft", text: formatDuration(result.latency_ms) }),
      result.tokens_in
        ? el("span", { class: "pill pill-soft", text: `${result.tokens_in + result.tokens_out} tokens` })
        : null,
      result.demo ? el("span", { class: "pill pill-amber", text: "演示结果" }) : null,
    );

    const body = el("div", { class: "result-block" });
    body.textContent = result.output || "";

    const actions = el(
      "div",
      { class: "row wrap", style: { gap: "8px", marginTop: "10px" } },
      el("button", {
        class: "btn btn-secondary btn-sm",
        type: "button",
        html: `${icon("copy", 13)}复制结果`,
        onclick: async () => {
          const ok = await copyText(result.output);
          if (ok) toastSuccess("已复制", "AI 结果已复制到剪贴板");
          else toastError("复制失败", "请手动选择文本");
        },
      }),
      el("button", {
        class: "btn btn-secondary btn-sm",
        type: "button",
        html: `${icon("plus", 13)}追加到正文`,
        onclick: () => {
          const value = `${editor.getValue()}\n\n${result.output}`.trim();
          editor.setValue(value, { silent: false });
          scheduleSave();
          toastSuccess("已追加", "AI 结果已追加到正文末尾");
        },
      }),
      el("button", {
        class: "btn btn-ghost btn-sm",
        type: "button",
        html: `${icon("refresh", 13)}替换正文`,
        onclick: async () => {
          const confirmed = await confirmDialog({
            title: "用 AI 结果替换正文？",
            message: "替换后仍可通过版本记录找回原始识别文本（历史记录保留 original_content）。",
            confirmText: "替换",
          });
          if (!confirmed) return;
          editor.setValue(result.output, { silent: false });
          scheduleSave();
          toastSuccess("已替换", "正文已更新，正在保存");
        },
      }),
    );

    aiResultBox.append(meta);
    if (result.notice) {
      aiResultBox.append(
        el(
          "div",
          { class: "notice notice-warning", style: { marginBottom: "10px" } },
          el("span", { html: icon("info", 15) }),
          el("span", { text: result.notice }),
        ),
      );
    }
    aiResultBox.append(body, actions);
  }

  updateImageCount();

  return {
    destroy() {
      clearTimeout(savingTimer);
      uploader.destroy();
      editor.destroy();
    },
  };
}

export default { render };
