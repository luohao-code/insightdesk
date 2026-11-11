/**
 * 通用工具函数。
 * 只放置与业务无关、可复用的纯函数，方便页面与组件共享。
 */

export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

/**
 * 创建 DOM 元素。
 * @param {string} tag
 * @param {object} attrs 支持 class/text/html/dataset/on* 与普通属性
 * @param {...(Node|string|null)} children
 */
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key === "html") node.innerHTML = value;
    else if (key === "dataset") Object.assign(node.dataset, value);
    else if (key === "style" && typeof value === "object") Object.assign(node.style, value);
    else if (key.startsWith("on") && typeof value === "function") {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (key in node && key !== "list") {
      try {
        node[key] = value;
      } catch {
        node.setAttribute(key, value);
      }
    } else {
      node.setAttribute(key, value);
    }
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

/** HTML 转义，渲染用户内容前必须调用。 */
export function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/** 条件 class 拼接。 */
export function clsx(...values) {
  return values.filter(Boolean).join(" ");
}

export function debounce(fn, wait = 300) {
  let timer = null;
  const wrapped = (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
  wrapped.cancel = () => clearTimeout(timer);
  return wrapped;
}

export function throttle(fn, wait = 200) {
  let last = 0;
  let timer = null;
  return (...args) => {
    const now = Date.now();
    const remain = wait - (now - last);
    if (remain <= 0) {
      clearTimeout(timer);
      timer = null;
      last = now;
      fn(...args);
    } else if (!timer) {
      timer = setTimeout(() => {
        last = Date.now();
        timer = null;
        fn(...args);
      }, remain);
    }
  };
}

export function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function uid(prefix = "id") {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

export function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

/** 格式化日期时间。 */
export function formatDate(value, withTime = true) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  const pad = (n) => String(n).padStart(2, "0");
  const base = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  if (!withTime) return base;
  return `${base} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/** 相对时间：刚刚 / 3 分钟前 / 昨天 … */
export function timeAgo(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  const diff = Date.now() - date.getTime();
  if (diff < 60_000) return "刚刚";
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小时前`;
  if (diff < 172_800_000) return "昨天";
  if (diff < 604_800_000) return `${Math.floor(diff / 86_400_000)} 天前`;
  return formatDate(value, false);
}

export function formatNumber(value) {
  const number = Number(value || 0);
  if (number >= 10_000) return `${(number / 10_000).toFixed(1)} 万`;
  return number.toLocaleString("zh-CN");
}

export function formatBytes(bytes) {
  const value = Number(bytes || 0);
  if (value <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(units.length - 1, Math.floor(Math.log(value) / Math.log(1024)));
  const scaled = value / 1024 ** index;
  return `${scaled >= 10 || index === 0 ? scaled.toFixed(0) : scaled.toFixed(1)} ${units[index]}`;
}

export function formatDuration(ms) {
  const value = Number(ms || 0);
  if (value <= 0) return "-";
  if (value < 1000) return `${Math.round(value)} ms`;
  if (value < 60_000) return `${(value / 1000).toFixed(1)} 秒`;
  const minutes = Math.floor(value / 60_000);
  const seconds = Math.round((value % 60_000) / 1000);
  return `${minutes} 分 ${seconds} 秒`;
}

export function truncate(value, limit = 80, suffix = "…") {
  const text = String(value ?? "");
  return text.length > limit ? text.slice(0, limit).trimEnd() + suffix : text;
}

/** 复制文本，优先使用 Clipboard API，失败时回退 execCommand。 */
export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    try {
      const area = document.createElement("textarea");
      area.value = text;
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.append(area);
      area.select();
      const ok = document.execCommand("copy");
      area.remove();
      return ok;
    } catch {
      return false;
    }
  }
}

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename || "download";
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export function readFileAsDataURL(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

export function parseFilename(disposition, fallback = "export") {
  if (!disposition) return fallback;
  const utf8 = /filename\*=UTF-8''([^;]+)/i.exec(disposition);
  if (utf8) {
    try {
      return decodeURIComponent(utf8[1]);
    } catch {
      return fallback;
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(disposition);
  return plain ? plain[1] : fallback;
}

export const storage = {
  get(key, fallback = null) {
    try {
      const raw = localStorage.getItem(key);
      return raw === null ? fallback : JSON.parse(raw);
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* 忽略隐私模式下的写入失败 */
    }
  },
  remove(key) {
    try {
      localStorage.removeItem(key);
    } catch {
      /* ignore */
    }
  },
};

export function isMac() {
  return /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
}

export function shortcutLabel(keys) {
  return isMac() ? keys.replace(/Ctrl/g, "⌘").replace(/Alt/g, "⌥") : keys;
}

export function statusLabel(status) {
  return (
    {
      ok: "正常",
      queued: "排队中",
      pending: "等待中",
      running: "识别中",
      succeeded: "已完成",
      failed: "失败",
      partial: "部分失败",
      cancelled: "已取消",
    }[status] || status
  );
}

export function statusClass(status) {
  return ["ok", "succeeded"].includes(status)
    ? "succeeded"
    : status === "running"
      ? "running"
      : status === "failed"
        ? "failed"
        : ["queued", "pending", "partial", "cancelled"].includes(status)
          ? "partial"
          : "";
}

export function relativeDayLabel(dateKey) {
  const today = new Date();
  const target = new Date(`${dateKey}T00:00:00`);
  const diff = Math.floor((today.setHours(0, 0, 0, 0) - target.getTime()) / 86_400_000);
  if (diff === 0) return "今天";
  if (diff === 1) return "昨天";
  return dateKey.slice(5);
}

/** 数字滚动动画。 */
export function animateNumber(node, target, duration = 600) {
  const start = Number(node.dataset.value || 0);
  const end = Number(target || 0);
  const started = performance.now();
  const step = (now) => {
    const progress = Math.min(1, (now - started) / duration);
    const eased = 1 - (1 - progress) ** 3;
    const current = Math.round(start + (end - start) * eased);
    node.textContent = current.toLocaleString("zh-CN");
    if (progress < 1) requestAnimationFrame(step);
    else node.dataset.value = String(end);
  };
  requestAnimationFrame(step);
}

/** 高亮搜索关键词（先转义再包裹 mark，避免 XSS）。 */
export function highlight(text, query) {
  const escaped = escapeHtml(text);
  const term = String(query || "").trim();
  if (!term) return escaped;
  const safeTerm = escapeHtml(term).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return escaped.replace(new RegExp(`(${safeTerm})`, "gi"), "<mark>$1</mark>");
}

export function emptyState({ icon = "", title = "暂无数据", description = "", action = "" } = {}) {
  return `
    <div class="empty">
      ${icon ? `<div class="empty-icon">${icon}</div>` : ""}
      <strong>${escapeHtml(title)}</strong>
      ${description ? `<p>${escapeHtml(description)}</p>` : ""}
      ${action || ""}
    </div>
  `;
}

export function errorMessage(error) {
  if (!error) return "未知错误";
  if (typeof error === "string") return error;
  if (error.message) return error.message;
  return String(error);
}

/** 以文件名推断可读标题。 */
export function titleFromFilename(name) {
  return String(name || "未命名")
    .replace(/\.[^.]+$/, "")
    .replace(/[_-]+/g, " ")
    .trim();
}

/** 时间格式化用于聊天消息。 */
export function formatClock(value) {
  const date = new Date(value || Date.now());
  if (Number.isNaN(date.getTime())) return "";
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}
