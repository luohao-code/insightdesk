/**
 * 全局状态。
 * 轻量发布订阅模式，避免引入框架。
 */

import { storage } from "./utils.js";

const listeners = new Set();

export const state = {
  theme: storage.get("insightdesk.theme", "dark"),
  language: storage.get("insightdesk.lang", "zh"),
  route: "dashboard",
  health: null,
  settings: null,
  ocrEngines: [],
  aiProviders: [],
  aiActions: [],
  activeBatchId: null,
  connected: false,
  lastError: null,
};

export function setState(patch) {
  const changed = {};
  for (const [key, value] of Object.entries(patch)) {
    if (state[key] !== value) {
      state[key] = value;
      changed[key] = value;
    }
  }
  if (Object.keys(changed).length) {
    for (const listener of listeners) {
      try {
        listener(state, changed);
      } catch (error) {
        console.error("状态订阅者异常", error);
      }
    }
  }
}

export function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/* ------------------------------------------------------------------ */
/* 主题                                                                */
/* ------------------------------------------------------------------ */

const media = window.matchMedia ? window.matchMedia("(prefers-color-scheme: light)") : null;

export function resolveTheme(theme = state.theme) {
  if (theme === "system") return media?.matches ? "light" : "dark";
  return theme === "light" ? "light" : "dark";
}

export function applyTheme(theme = state.theme) {
  const resolved = resolveTheme(theme);
  document.documentElement.dataset.theme = resolved;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", resolved === "light" ? "#f4f6fb" : "#070b14");

  const button = document.querySelector("#theme-btn");
  if (button) {
    button.innerHTML = resolved === "light"
      ? '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z"/></svg>'
      : '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';
    button.setAttribute("aria-label", resolved === "light" ? "切换到深色主题" : "切换到浅色主题");
  }
}

export function setTheme(theme) {
  setState({ theme });
  storage.set("insightdesk.theme", theme);
  applyTheme(theme);
}

export function toggleTheme() {
  const resolved = resolveTheme();
  setTheme(resolved === "light" ? "dark" : "light");
}

if (media) {
  media.addEventListener("change", () => {
    if (state.theme === "system") applyTheme("system");
  });
}

applyTheme();
