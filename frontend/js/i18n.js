/**
 * 轻量国际化。
 * 中文为默认语言，英文覆盖导航、标题与常用操作。
 * 页面内的说明性长文本保持中文，避免出现"半翻译"造成的理解负担。
 */

import { state, setState } from "./store.js";
import { storage } from "./utils.js";

const DICT = {
  zh: {
    "nav.group.core": "核心工作",
    "nav.group.assets": "资产管理",
    "nav.group.system": "系统",
    "nav.dashboard": "工作台",
    "nav.ocr": "OCR 识别",
    "nav.batch": "批量任务",
    "nav.ai": "AI 助手",
    "nav.history": "历史记录",
    "nav.web": "网页提取",
    "nav.settings": "设置",
    "nav.help": "帮助与关于",

    "page.dashboard.title": "工作台",
    "page.dashboard.subtitle": "识别、理解并沉淀每一条文字信息",
    "page.ocr.title": "OCR 识别",
    "page.ocr.subtitle": "上传图片，提取中英文印刷体文字，并交给 AI 继续加工",
    "page.batch.title": "批量任务",
    "page.batch.subtitle": "一次处理大量图片，实时查看进度，失败可重试",
    "page.ai.title": "AI 助手",
    "page.ai.subtitle": "翻译、摘要、关键词、问答与润色，让文字产生更多价值",
    "page.history.title": "历史记录",
    "page.history.subtitle": "所有识别与提取结果都保存在本机，可检索、编辑与导出",
    "page.web.title": "网页提取",
    "page.web.subtitle": "输入链接，提取正文与图片，并自动打开原始网页",
    "page.settings.title": "设置",
    "page.settings.subtitle": "配置识别引擎、AI 模型、任务参数与界面偏好",
    "page.help.title": "帮助与关于",
    "page.help.subtitle": "快速上手、快捷键、接口文档与团队信息",

    "topbar.search": "搜索与快捷操作",

    "common.refresh": "刷新",
    "common.search": "搜索",
    "common.save": "保存",
    "common.cancel": "取消",
    "common.confirm": "确认",
    "common.delete": "删除",
    "common.copy": "复制",
    "common.copied": "已复制",
    "common.export": "导出",
    "common.loading": "加载中…",
    "common.retry": "重试",
    "common.close": "关闭",
    "common.test": "测试连接",
    "common.open": "打开",
    "common.edit": "编辑",
    "common.download": "下载",
    "common.selectAll": "全选",
    "common.total": "共",
    "common.empty": "暂无数据",
    "common.upload": "上传图片",
    "common.run": "开始识别",
    "common.optional": "可选",
    "common.enabled": "已启用",
    "common.disabled": "未启用",
    "common.saved": "已保存",
    "common.unsaved": "未保存",
    "common.saving": "保存中…",

    "toast.copied": "内容已复制到剪贴板",
    "toast.copyFail": "复制失败，请手动选择文本",
    "toast.saved": "保存成功",
    "toast.saveFail": "保存失败",
    "toast.deleted": "已删除",
    "toast.deleteFail": "删除失败",
    "toast.uploaded": "上传完成",
    "toast.uploadFail": "上传失败",
    "toast.exported": "导出完成",
    "toast.exportFail": "导出失败",
    "toast.network": "网络异常，请稍后重试",
  },
  en: {
    "nav.group.core": "Workspace",
    "nav.group.assets": "Assets",
    "nav.group.system": "System",
    "nav.dashboard": "Dashboard",
    "nav.ocr": "OCR Studio",
    "nav.batch": "Batch Jobs",
    "nav.ai": "AI Assistant",
    "nav.history": "History",
    "nav.web": "Web Extract",
    "nav.settings": "Settings",
    "nav.help": "Help & About",

    "page.dashboard.title": "Dashboard",
    "page.dashboard.subtitle": "Capture, understand and organize every piece of text",
    "page.ocr.title": "OCR Studio",
    "page.ocr.subtitle": "Upload images, extract Chinese and English text, then refine with AI",
    "page.batch.title": "Batch Jobs",
    "page.batch.subtitle": "Process hundreds of images with live progress and retries",
    "page.ai.title": "AI Assistant",
    "page.ai.subtitle": "Translate, summarize, extract keywords, ask questions and polish text",
    "page.history.title": "History",
    "page.history.subtitle": "Every result is stored locally and ready to search, edit and export",
    "page.web.title": "Web Extract",
    "page.web.subtitle": "Paste a URL to extract the article and open the original page automatically",
    "page.settings.title": "Settings",
    "page.settings.subtitle": "Configure OCR engines, AI models, job limits and appearance",
    "page.help.title": "Help & About",
    "page.help.subtitle": "Getting started, shortcuts, API docs and the team",

    "topbar.search": "Search and commands",

    "common.refresh": "Refresh",
    "common.search": "Search",
    "common.save": "Save",
    "common.cancel": "Cancel",
    "common.confirm": "Confirm",
    "common.delete": "Delete",
    "common.copy": "Copy",
    "common.copied": "Copied",
    "common.export": "Export",
    "common.loading": "Loading…",
    "common.retry": "Retry",
    "common.close": "Close",
    "common.test": "Test",
    "common.open": "Open",
    "common.edit": "Edit",
    "common.download": "Download",
    "common.selectAll": "Select all",
    "common.total": "Total",
    "common.empty": "No data",
    "common.upload": "Upload",
    "common.run": "Recognize",
    "common.optional": "Optional",
    "common.enabled": "Enabled",
    "common.disabled": "Disabled",
    "common.saved": "Saved",
    "common.unsaved": "Unsaved",
    "common.saving": "Saving…",

    "toast.copied": "Copied to clipboard",
    "toast.copyFail": "Copy failed, please select manually",
    "toast.saved": "Saved",
    "toast.saveFail": "Save failed",
    "toast.deleted": "Deleted",
    "toast.deleteFail": "Delete failed",
    "toast.uploaded": "Upload complete",
    "toast.uploadFail": "Upload failed",
    "toast.exported": "Export complete",
    "toast.exportFail": "Export failed",
    "toast.network": "Network error, please retry",
  },
};

export function getLanguage() {
  return state.language === "en" ? "en" : "zh";
}

export function t(key, vars = {}) {
  const dictionary = DICT[getLanguage()] || DICT.zh;
  let text = dictionary[key] ?? DICT.zh[key] ?? key;
  for (const [name, value] of Object.entries(vars)) {
    text = text.replaceAll(`{${name}}`, String(value));
  }
  return text;
}

export function setLanguage(language) {
  const value = language === "en" ? "en" : "zh";
  setState({ language: value });
  storage.set("insightdesk.lang", value);
  document.documentElement.lang = value === "en" ? "en" : "zh-CN";
  applyI18n();
  window.dispatchEvent(new CustomEvent("language-changed", { detail: { language: value } }));
}

export function applyI18n(root = document) {
  root.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  root.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
    node.setAttribute("placeholder", t(node.dataset.i18nPlaceholder));
  });
  root.querySelectorAll("[data-i18n-title]").forEach((node) => {
    node.setAttribute("title", t(node.dataset.i18nTitle));
  });
}

if (state.language === "en") {
  document.documentElement.lang = "en";
}
