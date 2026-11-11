/**
 * AI 助手页。
 * 左侧选择动作，右侧进行文本处理；另提供基于文档的多轮问答。
 */

import { api } from "../api.js";
import {
  copyText,
  el,
  formatClock,
  formatDuration,
  formatNumber,
  truncate,
} from "../utils.js";
import { icon } from "../icons.js";
import { navigate } from "../router.js";
import { createEditor } from "../components/editor.js";
import { openModal } from "../components/modal.js";
import { toastError, toastSuccess, toastWarning } from "../components/toast.js";
import { openExportDialog } from "../components/exportDialog.js";

const ACTION_ICONS = {
  translate: "globe",
  summarize: "fileText",
  keywords: "tag",
  qa: "message",
  polish: "wand",
  outline: "list",
};

const LENGTH_OPTIONS = [
  { value: "简短（约 80–120 字）", label: "简短" },
  { value: "中等（约 200–300 字）", label: "中等" },
  { value: "详细（约 500 字，含要点）", label: "详细" },
];

export async function render(container) {
  const page = el("div", { class: "page" });
  page.innerHTML = `
    <div class="page-header">
      <div>
        <h2>${icon("sparkles", 20)} AI 助手</h2>
        <p>选择一种处理方式，或直接针对某篇文档提问。AI 结果不会覆盖原文，你可以复制、追加或替换。</p>
      </div>
      <div class="page-actions">
        <button class="btn btn-ghost btn-sm" type="button" data-go="history">${icon("archive", 14)}历史记录</button>
        <button class="btn btn-ghost btn-sm" type="button" data-go="settings">${icon("settings", 14)}引擎设置</button>
      </div>
    </div>

    <div class="ai-layout">
      <div class="col" style="gap:16px">
        <section class="card">
          <div class="card-header"><div class="card-title">${icon("wand", 16)} 处理动作</div></div>
          <div class="card-body" style="padding:10px">
            <div class="ai-actions" id="action-list"></div>
          </div>
        </section>

        <section class="card">
          <div class="card-header"><div class="card-title">${icon("database", 16)} 数据来源</div></div>
          <div class="card-body">
            <div class="col" style="gap:10px">
              <select class="select ai-source-select" id="source-select">
                <option value="">手动输入 / 粘贴文本</option>
              </select>
              <button class="btn btn-secondary btn-sm btn-block" type="button" id="source-refresh">
                ${icon("refresh", 13)}刷新最近记录
              </button>
              <div class="kv" style="margin-top:4px">
                <div class="kv-row"><span class="kv-key">当前引擎</span><span class="kv-value" id="provider-name">—</span></div>
                <div class="kv-row"><span class="kv-key">默认模型</span><span class="kv-value" id="model-name">—</span></div>
              </div>
            </div>
          </div>
        </section>
      </div>

      <div class="col" style="gap:16px">
        <div class="row-between">
          <div class="tabs" role="tablist" aria-label="AI 模式">
            <button class="tab active" type="button" data-tab="process" role="tab">文本处理</button>
            <button class="tab" type="button" data-tab="chat" role="tab">文档问答</button>
          </div>
          <span class="pill pill-soft" id="ai-mode-hint">${icon("info", 12)} 结果仅供参考，请核对原文</span>
        </div>

        <div id="tab-process">
          <div class="ai-workbench">
            <section class="card ai-pane">
              <div class="ai-pane-head">
                <h3>输入文本</h3>
                <span class="spacer"></span>
                <span class="text-xs muted" id="source-label">手动输入</span>
              </div>
              <div id="ai-editor-slot"></div>
              <div class="ai-options" id="ai-options"></div>
              <button class="btn btn-primary btn-block" type="button" id="ai-run">
                ${icon("sparkles", 15)}执行处理
              </button>
            </section>

            <section class="card ai-pane">
              <div class="ai-pane-head">
                <h3>处理结果</h3>
                <span class="spacer"></span>
                <span class="pill pill-soft" id="result-action-label">等待执行</span>
              </div>
              <div class="ai-output" id="ai-output">
                <div class="empty" style="padding:48px 16px">
                  <div class="empty-icon">${icon("sparkles", 22)}</div>
                  <strong>结果会显示在这里</strong>
                  <p>选择左侧动作，输入或导入一段文本，然后点击「执行处理」。</p>
                </div>
              </div>
            </section>
          </div>
        </div>

        <div id="tab-chat" hidden>
          <div class="chat-shell">
            <div class="chat-head">
              ${icon("message", 15)}
              <span id="chat-title">新的对话</span>
              <span class="spacer"></span>
              <select class="select input-sm" id="chat-context" style="max-width:220px" title="选择文档作为上下文">
                <option value="">不使用文档上下文</option>
              </select>
              <button class="btn btn-ghost btn-sm" type="button" id="chat-history">${icon("archive", 13)}会话</button>
              <button class="btn btn-ghost btn-sm" type="button" id="chat-new">${icon("plus", 13)}新对话</button>
            </div>
            <div class="chat-messages" id="chat-messages">
              <div class="empty" style="padding:40px 16px">
                <div class="empty-icon">${icon("message", 22)}</div>
                <strong>基于文档提问</strong>
                <p>在右上角选择一篇文档作为上下文，AI 会仅依据原文回答，并尽量引用依据。</p>
              </div>
            </div>
            <div class="chat-input">
              <textarea id="chat-text" placeholder="输入问题，Enter 发送，Shift + Enter 换行…" rows="2"></textarea>
              <button class="btn btn-primary" type="button" id="chat-send">${icon("send", 15)}</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;
  container.append(page);

  page.querySelectorAll("[data-go]").forEach((button) => {
    button.addEventListener("click", () => navigate(button.dataset.go));
  });

  /* ------------------------------------------------------------------ */
  /* 基础数据                                                            */
  /* ------------------------------------------------------------------ */

  let actions = [];
  let documents = [];
  let currentAction = "summarize";
  let currentDocument = null;
  let providerInfo = null;
  let conversationId = null;
  let chatMessages = [];

  const actionList = page.querySelector("#action-list");
  const optionsBox = page.querySelector("#ai-options");
  const outputBox = page.querySelector("#ai-output");
  const resultLabel = page.querySelector("#result-action-label");
  const runButton = page.querySelector("#ai-run");
  const sourceSelect = page.querySelector("#source-select");
  const sourceLabel = page.querySelector("#source-label");

  const editor = createEditor({
    minHeight: 260,
    placeholder: "在此粘贴需要处理的文本，或从上方选择一条历史记录…",
    showToolbar: true,
  });
  page.querySelector("#ai-editor-slot").append(editor.element);

  try {
    const [actionsResult, providersResult, docsResult] = await Promise.all([
      api.aiActions(),
      api.aiProviders(),
      api.history({ page_size: 50, sort: "updated_desc" }),
    ]);
    actions = actionsResult.items || [];
    documents = docsResult.items || [];
    const provider = (providersResult.items || []).find((item) => item.name === providersResult.default);
    providerInfo = provider || null;
    page.querySelector("#provider-name").textContent = provider ? provider.label : "演示引擎";
    page.querySelector("#model-name").textContent = providersResult.default_model || "—";
    if (provider) {
      const badge = page.querySelector("#ai-mode-hint");
      badge.className = provider.name === "mock" ? "pill pill-amber" : "pill pill-green";
      badge.innerHTML = `${icon(provider.name === "mock" ? "alert" : "check", 12)} ${provider.name === "mock" ? "当前为演示引擎" : `${provider.label} 已就绪`}`;
    }
    fillDocumentSelects();
  } catch (error) {
    toastError("初始化失败", error.message || String(error));
  }

  if (!actions.length) {
    actions = [
      { action: "summarize", label: "摘要", description: "提炼核心观点" },
      { action: "translate", label: "翻译", description: "翻译为目标语言" },
      { action: "keywords", label: "关键词", description: "提取主题词" },
      { action: "qa", label: "问答", description: "基于原文提问" },
    ];
  }

  renderActions();
  selectAction(currentAction, { silent: true });

  function fillDocumentSelects() {
    for (const select of [sourceSelect, page.querySelector("#chat-context")]) {
      const keepFirst = select.firstElementChild;
      select.innerHTML = "";
      select.append(keepFirst);
      for (const doc of documents) {
        select.append(
          el("option", {
            value: String(doc.id),
            text: `${truncate(doc.title, 32)} · ${formatNumber(doc.char_count)} 字`,
          }),
        );
      }
    }
  }

  function renderActions() {
    actionList.innerHTML = "";
    for (const action of actions) {
      const button = el(
        "button",
        { class: "action-card", type: "button", dataset: { action: action.action } },
        el("span", { class: "action-icon", html: icon(ACTION_ICONS[action.action] || "sparkles", 15) }),
        el(
          "span",
          { class: "action-body" },
          el("strong", { text: action.label }),
          el("span", { text: action.description || "" }),
        ),
      );
      button.addEventListener("click", () => selectAction(action.action));
      actionList.append(button);
    }
  }

  function selectAction(actionName, { silent = false } = {}) {
    currentAction = actionName;
    actionList.querySelectorAll(".action-card").forEach((card) => {
      card.classList.toggle("active", card.dataset.action === actionName);
    });
    const action = actions.find((item) => item.action === actionName);
    resultLabel.textContent = action ? action.label : "等待执行";
    runButton.innerHTML = `${icon("sparkles", 15)}${action ? action.label : "执行处理"}`;
    renderOptions(action);
    if (!silent) outputBox.innerHTML = "";
  }

  function renderOptions(action) {
    optionsBox.innerHTML = "";
    const options = action?.options || [];
    if (!options.length) return;

    if (options.includes("target_language")) {
      optionsBox.append(
        buildField("目标语言", "select", "target_language", [
          { value: "zh", label: "简体中文" },
          { value: "en", label: "英语" },
          { value: "ja", label: "日语" },
          { value: "ko", label: "韩语" },
          { value: "fr", label: "法语" },
          { value: "de", label: "德语" },
        ]),
      );
    }
    if (options.includes("length")) {
      optionsBox.append(
        buildField("摘要长度", "select", "length", LENGTH_OPTIONS.map((item) => ({ value: item.value, label: item.label }))),
      );
    }
    if (options.includes("count")) {
      const label = action.action === "keywords" ? "关键词数量" : "条目数量";
      optionsBox.append(buildField(label, "number", "count", null, action.action === "keywords" ? "10" : "6"));
    }
    if (options.includes("tone")) {
      optionsBox.append(
        buildField("语言风格", "select", "tone", [
          { value: "正式、准确", label: "正式准确" },
          { value: "简洁、口语", label: "简洁口语" },
          { value: "学术、严谨", label: "学术严谨" },
        ]),
      );
    }
    if (options.includes("question")) {
      optionsBox.append(buildField("问题", "textarea", "question", null, "", "针对这段文本，你想问什么？"));
      optionsBox.lastElementChild.style.gridColumn = "span 2";
    }
  }

  function buildField(label, type, name, options = null, value = "", placeholder = "") {
    const wrapper = el("div", { class: "field" });
    wrapper.append(el("label", { class: "field-label", text: label }));
    let control;
    if (type === "select") {
      control = el("select", { class: "select input-sm", dataset: { option: name } });
      for (const option of options || []) {
        control.append(el("option", { value: option.value, text: option.label }));
      }
    } else if (type === "textarea") {
      control = el("textarea", {
        class: "textarea input-sm",
        rows: 2,
        dataset: { option: name },
        placeholder,
      });
    } else {
      control = el("input", {
        class: "input input-sm",
        type,
        dataset: { option: name },
        value,
        min: "1",
        max: "30",
      });
    }
    wrapper.append(control);
    return wrapper;
  }

  function collectOptions() {
    const options = {};
    optionsBox.querySelectorAll("[data-option]").forEach((control) => {
      const key = control.dataset.option;
      options[key] = control.type === "number" ? Number(control.value || 0) : control.value;
    });
    return options;
  }

  /* ------------------------------------------------------------------ */
  /* 文档来源                                                            */
  /* ------------------------------------------------------------------ */

  sourceSelect.addEventListener("change", async () => {
    const id = sourceSelect.value;
    if (!id) {
      currentDocument = null;
      sourceLabel.textContent = "手动输入";
      return;
    }
    try {
      const doc = await api.document(Number(id));
      currentDocument = doc;
      editor.setValue(doc.content || "");
      sourceLabel.textContent = `来自：${doc.title}`;
      toastSuccess("已载入文档", `${doc.title} · ${formatNumber(doc.char_count)} 字`);
    } catch (error) {
      toastError("载入失败", error.message || String(error));
    }
  });

  page.querySelector("#source-refresh").addEventListener("click", async () => {
    try {
      const result = await api.history({ page_size: 50, sort: "updated_desc" });
      documents = result.items || [];
      fillDocumentSelects();
      toastSuccess("已刷新", `共载入 ${documents.length} 条最近记录`);
    } catch (error) {
      toastError("刷新失败", error.message || String(error));
    }
  });

  /* ------------------------------------------------------------------ */
  /* 执行处理                                                            */
  /* ------------------------------------------------------------------ */

  runButton.addEventListener("click", async () => {
    const text = editor.getValue().trim();
    if (!text) {
      toastWarning("请先输入文本", "可以粘贴内容，或从左侧选择一条历史记录");
      return;
    }
    const options = collectOptions();
    if (currentAction === "qa" && !String(options.question || "").trim()) {
      toastWarning("请输入问题", "问答模式需要一个问题");
      return;
    }

    runButton.disabled = true;
    runButton.innerHTML = '<span class="spinner"></span>处理中…';
    try {
      const result = await api.aiProcess({
        action: currentAction,
        document_id: currentDocument?.id || null,
        text,
        options,
      });
      renderOutput(result);
    } catch (error) {
      outputBox.innerHTML = "";
      outputBox.append(
        el(
          "div",
          { class: "notice notice-danger" },
          el("span", { html: icon("alert", 15) }),
          el("span", { text: `处理失败：${error.message || error}` }),
        ),
      );
      toastError("AI 处理失败", error.message || String(error));
    } finally {
      runButton.disabled = false;
      const label = actions.find((item) => item.action === currentAction)?.label || "执行处理";
      runButton.innerHTML = `${icon("sparkles", 15)}${label}`;
    }
  });

  function renderOutput(result) {
    outputBox.innerHTML = "";
    const meta = el(
      "div",
      { class: "row wrap", style: { gap: "6px", marginBottom: "10px" } },
      el("span", { class: "pill pill-accent", text: result.provider_label || result.provider }),
      el("span", { class: "pill pill-soft", text: result.model || "默认模型" }),
      el("span", { class: "pill pill-soft", text: formatDuration(result.latency_ms) }),
      result.tokens_in
        ? el("span", { class: "pill pill-soft", text: `${formatNumber(result.tokens_in + result.tokens_out)} tokens` })
        : null,
      result.demo ? el("span", { class: "pill pill-amber", text: "演示结果" }) : null,
    );

    if (result.notice) {
      outputBox.append(
        el(
          "div",
          { class: result.demo ? "notice notice-warning" : "notice", style: { marginBottom: "10px" } },
          el("span", { html: icon("info", 15) }),
          el("span", { text: result.notice }),
        ),
      );
    }

    const body = el("div", { class: "result-block", style: { minHeight: "240px" } });
    body.textContent = result.output || "";
    outputBox.append(meta, body);

    const actionsRow = el(
      "div",
      { class: "row wrap", style: { gap: "8px", marginTop: "12px" } },
      el("button", {
        class: "btn btn-secondary btn-sm",
        type: "button",
        html: `${icon("copy", 13)}复制结果`,
        onclick: async () => {
          const ok = await copyText(result.output);
          if (ok) toastSuccess("已复制", "结果已复制到剪贴板");
          else toastError("复制失败", "请手动选择文本");
        },
      }),
      el("button", {
        class: "btn btn-ghost btn-sm",
        type: "button",
        html: `${icon("refresh", 13)}替换输入`,
        onclick: () => {
          editor.setValue(result.output);
          toastSuccess("已替换", "结果已写回输入框，可继续二次处理");
        },
      }),
      currentDocument?.id
        ? el("button", {
            class: "btn btn-ghost btn-sm",
            type: "button",
            html: `${icon("download", 13)}导出原文`,
            onclick: () => openExportDialog([currentDocument.id], { title: "导出当前文档" }),
          })
        : null,
    );
    outputBox.append(actionsRow);
  }

  /* ------------------------------------------------------------------ */
  /* 标签页                                                              */
  /* ------------------------------------------------------------------ */

  page.querySelectorAll("[data-tab]").forEach((tab) => {
    tab.addEventListener("click", () => {
      page.querySelectorAll("[data-tab]").forEach((item) => item.classList.toggle("active", item === tab));
      const target = tab.dataset.tab;
      page.querySelector("#tab-process").hidden = target !== "process";
      page.querySelector("#tab-chat").hidden = target !== "chat";
    });
  });

  /* ------------------------------------------------------------------ */
  /* 问答                                                                */
  /* ------------------------------------------------------------------ */

  const chatMessagesNode = page.querySelector("#chat-messages");
  const chatText = page.querySelector("#chat-text");
  const chatSend = page.querySelector("#chat-send");
  const chatContext = page.querySelector("#chat-context");

  function renderChat() {
    chatMessagesNode.innerHTML = "";
    if (!chatMessages.length) {
      chatMessagesNode.innerHTML = `
        <div class="empty" style="padding:40px 16px">
          <div class="empty-icon">${icon("message", 22)}</div>
          <strong>基于文档提问</strong>
          <p>在右上角选择一篇文档作为上下文，AI 会仅依据原文回答，并尽量引用依据。</p>
        </div>`;
      return;
    }
    for (const message of chatMessages) {
      const bubble = el(
        "div",
        { class: `bubble ${message.role === "user" ? "user" : "assistant"}` },
        el("div", { text: message.content }),
        el("div", { class: "bubble-meta", text: formatClock(message.created_at) }),
      );
      chatMessagesNode.append(bubble);
    }
    chatMessagesNode.scrollTop = chatMessagesNode.scrollHeight;
  }

  async function sendChat() {
    const message = chatText.value.trim();
    if (!message) return;
    chatSend.disabled = true;
    chatMessages.push({ role: "user", content: message, created_at: new Date().toISOString() });
    renderChat();
    chatText.value = "";
    try {
      const result = await api.aiChat({
        message,
        conversation_id: conversationId,
        document_id: chatContext.value ? Number(chatContext.value) : null,
      });
      conversationId = result.conversation.id;
      chatMessages = result.conversation.messages || chatMessages;
      page.querySelector("#chat-title").textContent = result.conversation.title;
      renderChat();
      if (result.demo) {
        toastWarning("演示对话", "当前未配置大模型密钥，回答由本地规则生成。");
      }
    } catch (error) {
      chatMessages.pop();
      renderChat();
      toastError("发送失败", error.message || String(error));
    } finally {
      chatSend.disabled = false;
      chatText.focus();
    }
  }

  chatSend.addEventListener("click", sendChat);
  chatText.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendChat();
    }
  });

  page.querySelector("#chat-new").addEventListener("click", () => {
    conversationId = null;
    chatMessages = [];
    page.querySelector("#chat-title").textContent = "新的对话";
    renderChat();
    chatText.focus();
  });

  page.querySelector("#chat-history").addEventListener("click", async () => {
    try {
      const result = await api.conversations();
      const list = el("div", { class: "col", style: { gap: "8px" } });
      if (!result.items?.length) {
        list.append(el("p", { class: "text-sm muted", text: "还没有对话记录" }));
      }
      for (const item of result.items || []) {
        const button = el(
          "button",
          { class: "card card-interactive", type: "button", style: { padding: "12px", textAlign: "left" } },
          el("strong", { style: { fontSize: "12.5px", display: "block" }, text: item.title }),
          el("span", { class: "text-xs muted", text: `${item.message_count} 条消息 · ${item.updated_at.slice(0, 16)}` }),
        );
        button.addEventListener("click", async () => {
          try {
            const conversation = await api.conversation(item.id);
            conversationId = conversation.id;
            chatMessages = conversation.messages || [];
            page.querySelector("#chat-title").textContent = conversation.title;
            if (conversation.document_id) {
              chatContext.value = String(conversation.document_id);
            }
            page.querySelectorAll("[data-tab]").forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === "chat"));
            page.querySelector("#tab-process").hidden = true;
            page.querySelector("#tab-chat").hidden = false;
            renderChat();
            close();
          } catch (error) {
            toastError("会话加载失败", error.message || String(error));
          }
        });
        list.append(button);
      }
      const { close } = openModal({
        title: "历史会话",
        subtitle: "选择一段对话继续追问",
        content: list,
        footer: el("button", { class: "btn btn-ghost", type: "button", text: "关闭", onclick: () => close() }),
      });
    } catch (error) {
      toastError("会话列表加载失败", error.message || String(error));
    }
  });

  return {
    destroy() {
      editor.destroy();
    },
  };
}
