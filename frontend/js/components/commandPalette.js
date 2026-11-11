/**
 * 命令面板（Ctrl/Cmd + K）。
 * 支持页面跳转、快捷操作与历史记录全文搜索。
 */

import { api } from "../api.js";
import { el, debounce, highlight, truncate } from "../utils.js";
import { icon } from "../icons.js";
import { navigate, routeMeta, routeNames } from "../router.js";
import { t, getLanguage, setLanguage } from "../i18n.js";
import { toggleTheme } from "../store.js";

let active = null;

const NAV_ICONS = {
  dashboard: "dashboard",
  ocr: "scan",
  batch: "layers",
  ai: "sparkles",
  history: "archive",
  web: "globe",
  settings: "settings",
  help: "help",
};

const NAV_DESCRIPTIONS = {
  dashboard: "查看统计、趋势与快捷入口",
  ocr: "上传图片并识别文字",
  batch: "批量处理图片任务",
  ai: "翻译、摘要、关键词与问答",
  history: "检索与管理文字资产",
  web: "提取网页正文并自动打开",
  settings: "配置引擎与运行参数",
  help: "快捷键、接口文档与团队",
};

function buildCommands() {
  const navigation = routeNames().map((name) => ({
    id: `nav:${name}`,
    group: "页面",
    icon: NAV_ICONS[name] || "file",
    label: t(`nav.${name}`),
    description: NAV_DESCRIPTIONS[name] || "",
    run: () => navigate(name),
  }));

  const actions = [
    {
      id: "action:theme",
      group: "快捷操作",
      icon: "moon",
      label: "切换深浅色主题",
      description: "在深色与浅色界面之间切换",
      run: () => toggleTheme(),
    },
    {
      id: "action:lang",
      group: "快捷操作",
      icon: "globe",
      label: getLanguage() === "zh" ? "Switch to English" : "切换为中文",
      description: "界面标题与导航语言",
      run: () => setLanguage(getLanguage() === "zh" ? "en" : "zh"),
    },
    {
      id: "action:docs",
      group: "快捷操作",
      icon: "terminal",
      label: "打开 API 文档",
      description: "查看 Swagger 接口说明与在线调试",
      run: () => window.open("/api/docs", "_blank", "noopener"),
    },
    {
      id: "action:settings",
      group: "快捷操作",
      icon: "sliders",
      label: "配置识别引擎",
      description: "切换 OCR / AI 引擎并填写密钥",
      run: () => navigate("settings"),
    },
  ];

  return [...navigation, ...actions];
}

export function openCommandPalette() {
  if (active) {
    active.input.focus();
    return active;
  }

  const commands = buildCommands();
  const input = el("input", {
    class: "palette-input",
    type: "search",
    placeholder: "输入页面名称、操作，或搜索历史记录…",
    autocomplete: "off",
  });
  const results = el("div", { class: "palette-results" });
  const palette = el("div", { class: "palette", role: "dialog", "aria-label": "命令面板" }, input, results);
  const backdrop = el("div", { class: "palette-backdrop" }, palette);

  let items = commands;
  let activeIndex = 0;
  let docResults = [];
  let query = "";
  let closed = false;

  function close() {
    if (closed) return;
    closed = true;
    document.removeEventListener("keydown", onKeydown);
    backdrop.remove();
    active = null;
  }

  function render() {
    results.innerHTML = "";
    if (!items.length) {
      results.append(el("div", { class: "empty", style: { padding: "28px 16px" } }, el("p", { text: "没有匹配的结果" })));
      return;
    }

    let lastGroup = "";
    items.forEach((item, index) => {
      if (item.group !== lastGroup) {
        lastGroup = item.group;
        results.append(el("div", { class: "palette-group-label", text: item.group }));
      }
      const row = el(
        "button",
        {
          class: `palette-item${index === activeIndex ? " active" : ""}`,
          type: "button",
          dataset: { index: String(index) },
        },
        el("span", { class: "palette-icon", html: icon(item.icon || "file", 14) }),
        el(
          "span",
          { style: { flex: "1", minWidth: "0" } },
          el("span", { html: query ? highlight(item.label, query) : undefined, text: query ? undefined : item.label }),
          item.description
            ? el("span", {
                class: "text-xs muted",
                style: { display: "block" },
                text: truncate(item.description, 60),
              })
            : null,
        ),
        item.hint ? el("kbd", { text: item.hint }) : null,
      );
      row.addEventListener("click", () => select(item));
      row.addEventListener("mousemove", () => {
        if (activeIndex !== index) {
          activeIndex = index;
          render();
        }
      });
      results.append(row);
    });
  }

  function select(item) {
    close();
    try {
      item.run?.();
    } catch (error) {
      console.error("命令执行失败", error);
    }
  }

  function filterCommands(value) {
    const term = value.trim().toLowerCase();
    query = term;
    if (!term) {
      items = commands;
    } else {
      items = commands.filter((item) =>
        `${item.label} ${item.description}`.toLowerCase().includes(term),
      );
    }

    if (docResults.length && term) {
      items = [
        ...items,
        ...docResults.map((doc) => ({
          id: `doc:${doc.id}`,
          group: "历史记录",
          icon: "fileText",
          label: doc.title,
          description: doc.excerpt || `${doc.char_count} 字 · ${doc.engine}`,
          run: () => navigate("history", { doc: doc.id }),
        })),
      ];
    }

    activeIndex = 0;
    render();
  }

  const searchDocuments = debounce(async (value) => {
    if (closed) return;
    const term = value.trim();
    if (term.length < 2) {
      if (docResults.length) {
        docResults = [];
        filterCommands(value);
      }
      return;
    }
    try {
      const result = await api.history({ q: term, page_size: 5, sort: "updated_desc" });
      if (closed || input.value.trim() !== term) return;
      docResults = result.items || [];
      filterCommands(value);
    } catch {
      docResults = [];
    }
  }, 260);

  input.addEventListener("input", () => {
    filterCommands(input.value);
    searchDocuments(input.value);
  });

  function onKeydown(event) {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      activeIndex = Math.min(items.length - 1, activeIndex + 1);
      render();
      results.querySelector(".palette-item.active")?.scrollIntoView({ block: "nearest" });
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      activeIndex = Math.max(0, activeIndex - 1);
      render();
      results.querySelector(".palette-item.active")?.scrollIntoView({ block: "nearest" });
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      const item = items[activeIndex];
      if (item) select(item);
    }
  }

  backdrop.addEventListener("mousedown", (event) => {
    if (event.target === backdrop) close();
  });
  document.addEventListener("keydown", onKeydown);

  document.querySelector("#palette-root").append(backdrop);
  filterCommands("");
  setTimeout(() => input.focus(), 30);

  active = { input, close, element: backdrop };
  return active;
}

export function closeCommandPalette() {
  active?.close();
}
