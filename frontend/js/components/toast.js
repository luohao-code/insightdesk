/**
 * 轻提示。
 * 支持堆叠、自动关闭、手动关闭与四种语义颜色。
 */

import { el } from "../utils.js";
import { icon } from "../icons.js";

const ICONS = {
  success: "check",
  error: "alert",
  warning: "alert",
  info: "info",
};

function root() {
  let node = document.querySelector("#toast-root");
  if (!node) {
    node = el("div", { id: "toast-root", class: "toast-root" });
    document.body.append(node);
  }
  return node;
}

export function toast(options = {}) {
  const {
    title = "提示",
    message = "",
    type = "info",
    duration = 4200,
    closable = true,
  } = typeof options === "string" ? { message: options } : options;

  const node = el(
    "div",
    { class: `toast toast-${type}`, role: "status" },
    el("div", { class: "toast-icon", html: icon(ICONS[type] || "info", 13) }),
    el(
      "div",
      { class: "toast-content" },
      el("strong", { text: title }),
      message ? el("p", { text: message }) : null,
    ),
  );

  if (closable) {
    const closeButton = el("button", {
      class: "toast-close",
      type: "button",
      "aria-label": "关闭提示",
      html: icon("x", 13),
      onclick: () => remove(),
    });
    node.append(closeButton);
  }

  let timer = null;
  const remove = () => {
    if (!node.isConnected) return;
    clearTimeout(timer);
    node.classList.add("leaving");
    setTimeout(() => node.remove(), 180);
  };

  root().append(node);
  if (duration > 0) timer = setTimeout(remove, duration);

  // 鼠标悬停时暂停自动关闭
  node.addEventListener("mouseenter", () => clearTimeout(timer));
  node.addEventListener("mouseleave", () => {
    if (duration > 0) timer = setTimeout(remove, 1200);
  });

  return { close: remove, element: node };
}

export const toastSuccess = (title, message = "", options = {}) =>
  toast({ title, message, type: "success", ...options });

export const toastError = (title, message = "", options = {}) =>
  toast({ title, message, type: "error", duration: 6000, ...options });

export const toastWarning = (title, message = "", options = {}) =>
  toast({ title, message, type: "warning", duration: 5200, ...options });

export const toastInfo = (title, message = "", options = {}) =>
  toast({ title, message, type: "info", ...options });
