/**
 * 文本编辑器组件。
 * 提供复制、清空、保存、字数统计、自动保存状态与快捷键。
 */

import { copyText, debounce, el, formatNumber } from "../utils.js";
import { icon } from "../icons.js";
import { toastError, toastSuccess } from "./toast.js";

export function createEditor({
  value = "",
  placeholder = "识别结果会显示在这里，可直接编辑…",
  onChange = null,
  onSave = null,
  minHeight = 260,
  readOnly = false,
  showToolbar = true,
} = {}) {
  let saved = true;
  let lastEmitted = value;

  const textarea = el("textarea", {
    class: "editor-textarea",
    placeholder,
    spellcheck: "false",
    readOnly,
    style: { minHeight: `${minHeight}px` },
  });
  textarea.value = value;

  const charCount = el("span", { text: "0 字" });
  const lineCount = el("span", { text: "0 行" });
  const statusDot = el("span", { class: "dot" });
  const statusText = el("span", { text: "已就绪" });
  const status = el("span", { class: "editor-status saved" }, statusDot, statusText);

  const copyButton = el("button", {
    class: "btn btn-ghost btn-sm",
    type: "button",
    title: "复制全部内容（Ctrl+Shift+C）",
    html: `${icon("copy", 13)}<span>复制</span>`,
  });
  const clearButton = el("button", {
    class: "btn btn-ghost btn-sm",
    type: "button",
    title: "清空编辑器",
    html: `${icon("trash", 13)}<span>清空</span>`,
  });
  const saveButton = onSave
    ? el("button", {
        class: "btn btn-ghost btn-sm",
        type: "button",
        title: "保存（Ctrl+S）",
        html: `${icon("save", 13)}<span>保存</span>`,
      })
    : null;

  const toolbar = el(
    "div",
    { class: "editor-toolbar" },
    copyButton,
    saveButton,
    el("div", { class: "divider" }),
    clearButton,
    el("div", { class: "spacer" }),
    el("span", { class: "text-xs muted", id: "editor-engine-label" }),
  );

  const footer = el(
    "div",
    { class: "editor-footer" },
    el("div", { class: "row", style: { gap: "12px" } }, charCount, lineCount),
    status,
  );

  const root = el("div", { class: "editor-shell" }, showToolbar ? toolbar : null, textarea, footer);

  function updateStats() {
    const text = textarea.value;
    const chars = text.replace(/\s/g, "").length;
    charCount.textContent = `${formatNumber(chars)} 字`;
    lineCount.textContent = `${text ? text.split("\n").length : 0} 行`;
  }

  function markDirty() {
    saved = false;
    status.className = "editor-status saving";
    statusText.textContent = "编辑中…";
  }

  function markSaved(label = "已保存") {
    saved = true;
    status.className = "editor-status saved";
    statusText.textContent = label;
  }

  function markSaving() {
    status.className = "editor-status saving";
    statusText.textContent = "保存中…";
  }

  const emitChange = debounce((text) => {
    if (text === lastEmitted) return;
    lastEmitted = text;
    onChange?.(text);
  }, 280);

  textarea.addEventListener("input", () => {
    markDirty();
    updateStats();
    emitChange(textarea.value);
  });

  textarea.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      triggerSave();
    }
  });

  async function triggerSave() {
    if (!onSave) return;
    markSaving();
    try {
      const result = await onSave(textarea.value);
      markSaved(result === false ? "未保存" : "已保存");
    } catch (error) {
      status.className = "editor-status";
      statusText.textContent = "保存失败";
      toastError("保存失败", error.message || String(error));
    }
  }

  copyButton.addEventListener("click", async () => {
    if (!textarea.value.trim()) {
      toastError("没有可复制的内容", "请先识别或粘贴文本");
      return;
    }
    const ok = await copyText(textarea.value);
    if (ok) toastSuccess("已复制", `${textarea.value.length} 个字符已复制到剪贴板`);
    else toastError("复制失败", "请手动选择文本后复制");
  });

  if (saveButton) {
    saveButton.addEventListener("click", triggerSave);
  }

  clearButton.addEventListener("click", () => {
    if (!textarea.value) return;
    textarea.value = "";
    updateStats();
    markDirty();
    onChange?.("");
    emitChange.cancel?.();
    lastEmitted = "";
  });

  updateStats();

  return {
    element: root,
    textarea,
    toolbar,
    getValue: () => textarea.value,
    setValue(next, { silent = true } = {}) {
      textarea.value = next || "";
      updateStats();
      if (!silent) {
        markDirty();
        onChange?.(textarea.value);
      }
      lastEmitted = textarea.value;
    },
    setEngineLabel(text) {
      const node = toolbar.querySelector("#editor-engine-label");
      if (node) node.textContent = text || "";
    },
    setReadOnly(value) {
      textarea.readOnly = Boolean(value);
    },
    markDirty,
    markSaved,
    markSaving,
    focus() {
      textarea.focus();
    },
    isSaved: () => saved,
    destroy() {
      root.remove();
    },
  };
}
