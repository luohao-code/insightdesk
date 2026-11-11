/**
 * 前端常量与团队信息。
 */

export const APP_VERSION = "1.0.0";

/** 项目仓库地址。 */
export const REPO_URL = "https://github.com/luohao-code/insightdesk";

export const TEAM = [
  {
    name: "罗浩",
    role: "项目负责人 / 架构与后端",
    duty: "需求基线、系统架构、任务队列、网页提取、集成发布",
    weight: "40%",
    initial: "罗",
  },
  {
    name: "杨文杰",
    role: "前端负责人 / 交互与可视化",
    duty: "设计系统、全部页面与组件、实时进度、可用性测试",
    weight: "32%",
    initial: "杨",
  },
  {
    name: "邹俊杰",
    role: "算法与质量负责人",
    duty: "OCR/AI 引擎适配、提示词工程、自动化测试、打包与手册",
    weight: "28%",
    initial: "邹",
  },
];

export const TECH_STACK = [
  { name: "Python 3.12", detail: "服务端语言" },
  { name: "FastAPI", detail: "REST API 与 SSE" },
  { name: "SQLAlchemy + SQLite", detail: "数据持久化与 FTS5" },
  { name: "原生 ES Module", detail: "零构建前端" },
  { name: "RapidOCR / 百度 / 腾讯", detail: "可插拔 OCR" },
  { name: "DeepSeek / Kimi / 智谱 / 通义", detail: "OpenAI 兼容 AI" },
];

export const EXPORT_FORMATS = [
  { value: "txt", label: "纯文本", extension: "TXT", description: "适合快速归档与粘贴" },
  { value: "md", label: "Markdown", extension: "MD", description: "保留标题与结构" },
  { value: "docx", label: "Word 文档", extension: "DOCX", description: "带标题与元信息" },
  { value: "xlsx", label: "Excel 表格", extension: "XLSX", description: "多记录汇总，支持筛选" },
  { value: "csv", label: "CSV 表格", extension: "CSV", description: "通用数据交换格式" },
  { value: "json", label: "JSON 数据", extension: "JSON", description: "便于二次开发" },
  { value: "zip", label: "ZIP 归档", extension: "ZIP", description: "每条记录一个文本文件" },
];
