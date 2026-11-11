/**
 * 模态框。
 * 支持静态内容与 DOM 节点、Esc 关闭、背景点击关闭与焦点管理。
 */

import { $, el } from "../utils.js";
import { icon } from "../icons.js";

let activeModal = null;

export function openModal({
  title = "",
  subtitle = "",
  content = null,
  footer = null,
  size = "md",
  closeOnBackdrop = true,
  onClose = null,
  className = "",
} = {}) {
  closeModal();

  const previousFocus = document.activeElement;
  const body = el("div", { class: "modal-body" });
  if (content instanceof Node) body.append(content);
  else if (typeof content === "string") body.innerHTML = content;

  const footerNode = el("div", { class: "modal-footer" });
  if (footer instanceof Node) footerNode.append(footer);
  else if (typeof footer === "string") footerNode.innerHTML = footer;
  else footerNode.remove();

  const closeButton = el("button", {
    class: "icon-btn modal-close",
    type: "button",
    "aria-label": "关闭",
    html: icon("x", 17),
    onclick: () => close(),
  });

  const header = el(
    "div",
    { class: "modal-header" },
    el(
      "div",
      { style: { flex: "1", minWidth: "0" } },
      el("h3", { text: title || "对话框" }),
      subtitle ? el("p", { text: subtitle }) : null,
    ),
    closeButton,
  );

  const modal = el(
    "div",
    { class: `modal ${size === "lg" ? "modal-lg" : size === "sm" ? "modal-sm" : ""} ${className}`.trim(), role: "dialog", "aria-modal": "true" },
    header,
    body,
    footerNode,
  );

  const backdrop = el("div", { class: "modal-backdrop" }, modal);
  backdrop.addEventListener("mousedown", (event) => {
    if (event.target === backdrop && closeOnBackdrop) close();
  });

  const onKeydown = (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
    }
    if (event.key === "Tab") {
      const focusable = modal.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  };

  const close = () => {
    document.removeEventListener("keydown", onKeydown);
    backdrop.remove();
    activeModal = null;
    if (previousFocus && typeof previousFocus.focus === "function") previousFocus.focus();
    onClose?.();
  };

  document.addEventListener("keydown", onKeydown);
  document.querySelector("#modal-root").append(backdrop);
  activeModal = { backdrop, modal, body, close };

  setTimeout(() => {
    const focusTarget =
      modal.querySelector("input, textarea, select, button:not(.modal-close)") || closeButton;
    focusTarget.focus();
  }, 40);

  return { element: modal, body, footer: footerNode, close };
}

export function closeModal() {
  if (activeModal) activeModal.close();
}

export function isModalOpen() {
  return Boolean(activeModal);
}

/**
 * 确认对话框。
 * @returns {Promise<boolean>}
 */
export function confirmDialog({
  title = "请确认",
  message = "",
  confirmText = "确认",
  cancelText = "取消",
  danger = false,
} = {}) {
  return new Promise((resolve) => {
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      resolve(value);
      closeModal();
    };

    const footer = el(
      "div",
      { class: "row" },
      el("button", {
        class: "btn btn-ghost",
        type: "button",
        text: cancelText,
        onclick: () => finish(false),
      }),
      el("button", {
        class: danger ? "btn btn-danger" : "btn btn-primary",
        type: "button",
        text: confirmText,
        onclick: () => finish(true),
      }),
    );

    const content = el(
      "div",
      { class: "col" },
      el("p", { text: message, style: { fontSize: "13px", lineHeight: "1.7" } }),
    );

    openModal({
      title,
      content,
      footer,
      size: "sm",
      onClose: () => {
        if (!settled) {
          settled = true;
          resolve(false);
        }
      },
    });
  });
}

/** 打开一个带表单的弹窗，自动收集输入值。 */
export function formDialog({
  title,
  subtitle = "",
  fields = [],
  submitText = "保存",
  cancelText = "取消",
  onSubmit,
  onClose = null,
} = {}) {
  const form = el("form", { class: "col", style: { gap: "14px" } });
  const inputs = new Map();

  for (const field of fields) {
    const inputId = `field_${field.name}`;
    let control;
    if (field.type === "textarea") {
      control = el("textarea", {
        class: "textarea",
        id: inputId,
        name: field.name,
        placeholder: field.placeholder || "",
        value: field.value || "",
        rows: field.rows || 4,
      });
    } else if (field.type === "select") {
      control = el("select", { class: "select", id: inputId, name: field.name });
      for (const option of field.options || []) {
        control.append(
          el("option", {
            value: option.value,
            text: option.label,
            selected: option.value === field.value,
          }),
        );
      }
    } else {
      control = el("input", {
        class: "input",
        id: inputId,
        name: field.name,
        type: field.type || "text",
        placeholder: field.placeholder || "",
        value: field.value || "",
      });
    }
    inputs.set(field.name, control);
    form.append(
      el(
        "div",
        { class: "field" },
        el("label", { class: "field-label", for: inputId, text: field.label }),
        control,
        field.hint ? el("p", { class: "field-hint", text: field.hint }) : null,
      ),
    );
  }

  const footer = el(
    "div",
    { class: "row" },
    el("button", {
      class: "btn btn-ghost",
      type: "button",
      text: cancelText,
      onclick: () => closeModal(),
    }),
    el("button", {
      class: field ? "btn btn-primary" : "btn btn-primary",
      type: "submit",
      text: submitText,
      form: "form-dialog-form",
    }),
  );

  form.id = "form-dialog-form";
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const values = {};
    for (const [name, input] of inputs.entries()) values[name] = input.value.trim();
    const result = await onSubmit?.(values);
    if (result !== false) closeModal();
  });

  const { close } = openModal({ title, subtitle, content: form, footer, size: "sm", onClose });
  setTimeout(() => {
    const first = inputs.values().next().value;
    first?.focus();
  }, 60);
  return { close, inputs };
}

export { $ };
