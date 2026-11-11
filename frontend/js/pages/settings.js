/**
 * 设置页。
 * 配置 OCR / AI 引擎、任务参数、网页提取、外观与数据管理。
 */

import { api } from "../api.js";
import { el, formatBytes, formatNumber } from "../utils.js";
import { icon } from "../icons.js";
import { applyTheme, setTheme, state } from "../store.js";
import { setLanguage } from "../i18n.js";
import { confirmDialog } from "../components/modal.js";
import { toastError, toastSuccess, toastWarning } from "../components/toast.js";
import { APP_VERSION, TEAM, TECH_STACK } from "../config.js";

const MASK = "••••••••";

export async function render(container) {
  const page = el("div", { class: "page" });
  page.innerHTML = `
    <div class="page-header">
      <div>
        <h2>${icon("settings", 20)} 设置</h2>
        <p>引擎与密钥仅保存在本机服务端；接口返回时自动脱敏。修改任务参数后，新建批次立即生效。</p>
      </div>
      <div class="page-actions">
        <span class="pill pill-soft" id="dirty-pill" hidden>有未保存修改</span>
        <button class="btn btn-ghost btn-sm" type="button" id="reload-settings">${icon("refresh", 14)}放弃修改</button>
      </div>
    </div>

    <div class="settings-layout">
      <nav class="settings-nav" aria-label="设置分类">
        <a href="#settings-ocr" class="active">识别引擎</a>
        <a href="#settings-ai">AI 模型</a>
        <a href="#settings-task">任务与性能</a>
        <a href="#settings-web">网页提取</a>
        <a href="#settings-ui">外观与语言</a>
        <a href="#settings-data">数据管理</a>
        <a href="#settings-about">关于</a>
      </nav>

      <div class="settings-sections" id="settings-sections">
        <div id="settings-loading" class="card">
          <div class="card-body">
            <div class="skeleton skeleton-title"></div>
            <div class="skeleton skeleton-text"></div>
            <div class="skeleton skeleton-text" style="width:60%"></div>
          </div>
        </div>
      </div>
    </div>
  `;
  container.append(page);

  const sectionsRoot = page.querySelector("#settings-sections");
  const dirtyPill = page.querySelector("#dirty-pill");
  let data = null;
  let values = {};
  let selectedTheme = state.theme;
  let selectedLanguage = "zh";
  let systemInfo = null;
  let historyStats = null;

  try {
    const [settings, info, stats] = await Promise.all([
      api.settings(),
      api.systemInfo().catch(() => null),
      api.historyStats().catch(() => null),
    ]);
    data = settings;
    values = { ...settings.values };
    systemInfo = info;
    historyStats = stats;
    selectedTheme = values.theme || state.theme;
    selectedLanguage = values.ui_language || "zh";
  } catch (error) {
    sectionsRoot.innerHTML = "";
    sectionsRoot.append(
      el(
        "div",
        { class: "card" },
        el(
          "div",
          { class: "empty" },
          el("div", { class: "empty-icon", html: icon("alert", 22) }),
          el("strong", { text: "设置加载失败" }),
          el("p", { text: error.message || String(error) }),
          el("button", { class: "btn btn-secondary btn-sm", type: "button", text: "重试", onclick: () => render(container) }),
        ),
      ),
    );
    return;
  }

  page.querySelector("#settings-loading")?.remove();
  sectionsRoot.innerHTML = "";

  applyTheme(selectedTheme);

  const markDirty = () => {
    dirtyPill.hidden = false;
  };

  /* ------------------------------------------------------------------ */
  /* 通用构建函数                                                        */
  /* ------------------------------------------------------------------ */

  function makeSection(id, iconName, title, description) {
    const card = el("section", { class: "card settings-section", id });
    card.append(
      el(
        "div",
        { class: "card-header" },
        el(
          "div",
          { class: "card-title" },
          el("span", { html: icon(iconName, 16) }),
          el(
            "span",
            {},
            el("div", { text: title }),
            el("div", { class: "card-subtitle", text: description, style: { marginTop: "2px", fontWeight: "400" } }),
          ),
        ),
      ),
    );
    const body = el("div", { class: "card-body" });
    card.append(body);
    sectionsRoot.append(card);
    return { card, body };
  }

  function makeRow(label, hint, control, controlStyle = "") {
    return el(
      "div",
      { class: "settings-row" },
      el(
        "div",
        { class: "settings-row-info" },
        el("strong", { text: label }),
        hint ? el("span", { text: hint }) : null,
      ),
      el("div", { class: `settings-row-control ${controlStyle}`.trim() }, control),
    );
  }

  function numberControl(key, { min, max, step = 1, suffix = "" } = {}) {
    const input = el("input", {
      class: "input input-sm",
      type: "number",
      min,
      max,
      step,
      value: values[key] ?? "",
    });
    input.addEventListener("input", () => {
      values[key] = input.value === "" ? "" : Number(input.value);
      markDirty();
    });
    const wrapper = el("div", { class: "row", style: { gap: "6px" } }, input);
    if (suffix) wrapper.append(el("span", { class: "text-xs muted", text: suffix }));
    return wrapper;
  }

  function textControl(key, { placeholder = "", secret = false, type = "text", width = "" } = {}) {
    const configured = values[key] === MASK;
    const input = el("input", {
      class: "input input-sm",
      type,
      value: secret ? "" : values[key] ?? "",
      placeholder: configured ? "已配置，留空保持不变" : placeholder,
      style: width ? { width } : {},
      autocomplete: "off",
    });
    input.addEventListener("input", () => {
      values[key] = input.value;
      markDirty();
    });
    if (secret) input.dataset.secret = "1";
    return input;
  }

  function switchControl(key, label = "") {
    const input = el("input", { type: "checkbox", checked: Boolean(values[key]) });
    input.addEventListener("change", () => {
      values[key] = input.checked;
      markDirty();
    });
    const wrapper = el(
      "label",
      { class: "switch" },
      input,
      el("span", { class: "track" }),
      label ? el("span", { class: "text-sm muted", text: label }) : null,
    );
    return { wrapper, input };
  }

  function selectControl(key, options, { width = "150px" } = {}) {
    const select = el("select", { class: "select input-sm", style: { width } });
    for (const option of options) {
      select.append(el("option", { value: option.value, text: option.label, selected: values[key] === option.value }));
    }
    select.addEventListener("change", () => {
      values[key] = select.value;
      markDirty();
    });
    return select;
  }

  /* ------------------------------------------------------------------ */
  /* OCR 引擎                                                            */
  /* ------------------------------------------------------------------ */

  const ocrSection = makeSection(
    "settings-ocr",
    "scan",
    "OCR 识别引擎",
    "演示引擎无需配置即可体验流程；生产使用建议安装 RapidOCR 或配置云端密钥。",
  );

  const ocrList = el("div", { class: "engine-list" });
  const ocrCredBox = el("div", { class: "col", style: { gap: "12px", marginTop: "14px" } });
  ocrSection.body.append(ocrList, ocrCredBox);

  function renderOcrEngines() {
    ocrList.innerHTML = "";
    for (const engine of data.engines.ocr) {
      const selected = values.ocr_engine === engine.name;
      const card = el(
        "div",
        { class: `engine-card${selected ? " selected" : ""}`, role: "button", tabindex: "0" },
        el("span", { class: "engine-radio" }),
        el(
          "div",
          { class: "engine-main" },
          el(
            "strong",
            {},
            engine.label,
            el("span", { class: `engine-state ${engine.available ? "ok" : "bad"}`, text: engine.available ? "可用" : "不可用" }),
          ),
          el("p", { text: engine.available ? engine.description : `${engine.description}（${engine.reason}）` }),
        ),
      );
      const testButton = el("button", {
        class: "btn btn-ghost btn-sm",
        type: "button",
        text: "测试",
        onclick: async (event) => {
          event.stopPropagation();
          const originalText = testButton.textContent;
          testButton.disabled = true;
          testButton.textContent = "测试中…";
          try {
            const result = await api.testProvider("ocr", engine.name);
            if (result.ok) toastSuccess(`${result.label} 连接正常`, `${Math.round(result.latency_ms)} ms · ${result.message}`);
            else toastWarning(`${result.label} 不可用`, result.message);
          } catch (error) {
            toastError("测试失败", error.message || String(error));
          } finally {
            testButton.disabled = false;
            testButton.textContent = originalText;
          }
        },
      });
      card.append(testButton);
      const select = () => {
        if (values.ocr_engine === engine.name) return;
        values.ocr_engine = engine.name;
        markDirty();
        renderOcrEngines();
        renderOcrCredentials();
      };
      card.addEventListener("click", select);
      card.addEventListener("keydown", (event) => {
        if (event.key === "Enter") select();
      });
      ocrList.append(card);
    }
  }

  function renderOcrCredentials() {
    ocrCredBox.innerHTML = "";
    const providers = data.engines.ocr.filter((engine) => engine.credential_fields?.length);
    if (!providers.length) return;

    ocrCredBox.append(
      el("div", { class: "row", style: { gap: "8px" } },
        el("span", { class: "text-sm", style: { fontWeight: "600" }, text: "云端凭据" }),
        el("span", { class: "pill pill-soft", text: "仅保存在服务端" }),
      ),
    );

    for (const engine of providers) {
      const box = el("div", { class: "credential-box" });
      box.append(el("div", { class: "row-between" }, el("strong", { class: "text-sm", text: engine.label }), el("span", { class: "pill pill-soft", text: "需要配置" })));
      const grid = el("div", { class: "settings-grid-2" });
      for (const field of engine.credential_fields) {
        const input = textControl(field.key, {
          placeholder: field.placeholder,
          secret: field.secret,
        });
        grid.append(
          el(
            "div",
            { class: "field" },
            el("label", { class: "field-label", text: field.label }),
            input,
            field.help_text ? el("p", { class: "field-hint", text: field.help_text }) : null,
          ),
        );
      }
      box.append(grid);
      ocrCredBox.append(box);
    }
  }

  renderOcrEngines();
  renderOcrCredentials();

  /* ------------------------------------------------------------------ */
  /* AI 引擎                                                             */
  /* ------------------------------------------------------------------ */

  const aiSection = makeSection(
    "settings-ai",
    "sparkles",
    "AI 大模型",
    "支持 DeepSeek、Kimi、智谱、通义千问以及任意 OpenAI 兼容服务。",
  );

  const aiList = el("div", { class: "engine-list" });
  const aiCredBox = el("div", { class: "col", style: { gap: "12px", marginTop: "14px" } });
  aiSection.body.append(aiList, aiCredBox);

  function renderAiEngines() {
    aiList.innerHTML = "";
    for (const provider of data.engines.ai) {
      const selected = values.ai_provider === provider.name;
      const card = el(
        "div",
        { class: `engine-card${selected ? " selected" : ""}`, role: "button", tabindex: "0" },
        el("span", { class: "engine-radio" }),
        el(
          "div",
          { class: "engine-main" },
          el(
            "strong",
            {},
            provider.label,
            el("span", { class: `engine-state ${provider.available ? "ok" : "bad"}`, text: provider.available ? "可用" : "未配置" }),
          ),
          el("p", { text: provider.description }),
          provider.models?.length
            ? el("p", { class: "mono text-xs", style: { marginTop: "4px" }, text: `模型：${provider.models.join(" / ")}` })
            : null,
        ),
      );
      const testButton = el("button", {
        class: "btn btn-ghost btn-sm",
        type: "button",
        text: "测试",
        onclick: async (event) => {
          event.stopPropagation();
          const originalText = testButton.textContent;
          testButton.disabled = true;
          testButton.textContent = "测试中…";
          try {
            const result = await api.testProvider("ai", provider.name);
            if (result.ok) toastSuccess(`${result.label} 连接正常`, `${Math.round(result.latency_ms)} ms · ${result.message}`);
            else toastWarning(`${result.label} 不可用`, result.message);
          } catch (error) {
            toastError("测试失败", error.message || String(error));
          } finally {
            testButton.disabled = false;
            testButton.textContent = originalText;
          }
        },
      });
      card.append(testButton);
      const select = () => {
        if (values.ai_provider === provider.name) return;
        values.ai_provider = provider.name;
        markDirty();
        renderAiEngines();
        renderAiCredentials();
        if (provider.default_base_url) {
          values.ai_base_url = provider.default_base_url;
          const baseInput = aiCredBox.querySelector('[data-key="ai_base_url"]');
          if (baseInput) baseInput.value = provider.default_base_url;
        }
        if (provider.models?.length && !provider.models.includes(values.ai_model)) {
          values.ai_model = provider.models[0];
          const modelInput = aiCredBox.querySelector('[data-key="ai_model"]');
          if (modelInput) modelInput.value = provider.models[0];
        }
      };
      card.addEventListener("click", select);
      card.addEventListener("keydown", (event) => {
        if (event.key === "Enter") select();
      });
      aiList.append(card);
    }
  }

  function renderAiCredentials() {
    aiCredBox.innerHTML = "";
    const provider = data.engines.ai.find((item) => item.name === values.ai_provider);
    if (!provider || provider.name === "mock") {
      aiCredBox.append(
        el(
          "div",
          { class: "notice" },
          el("span", { html: icon("info", 15) }),
          el("span", { text: "当前使用演示引擎，本地规则即可完成摘要、翻译、关键词与问答流程。配置任意云端模型后可获得更高质量的结果。" }),
        ),
      );
      return;
    }

    const box = el("div", { class: "credential-box" });
    const fields = provider.credential_fields?.length
      ? provider.credential_fields
      : [
          { key: "ai_api_key", label: "API Key", secret: true, placeholder: "sk-..." },
          { key: "ai_base_url", label: "Base URL", secret: false, placeholder: "https://api.example.com/v1" },
          { key: "ai_model", label: "模型名称", secret: false, placeholder: "model-name" },
        ];

    const grid = el("div", { class: "settings-grid-2" });
    for (const field of fields) {
      let input;
      if (field.key === "ai_model" && provider.models?.length) {
        input = el("input", {
          class: "input input-sm",
          value: values.ai_model || "",
          list: "ai-model-options",
          placeholder: field.placeholder,
        });
        input.dataset.key = field.key;
        input.addEventListener("input", () => {
          values.ai_model = input.value;
          markDirty();
        });
      } else {
        input = textControl(field.key, { placeholder: field.placeholder, secret: Boolean(field.secret) });
        input.dataset.key = field.key;
      }
      grid.append(
        el(
          "div",
          { class: "field" },
          el("label", { class: "field-label", text: field.label }),
          input,
          field.help_text ? el("p", { class: "field-hint", text: field.help_text }) : null,
        ),
      );
    }
    box.append(grid);

    if (provider.models?.length) {
      const datalist = el("datalist", { id: "ai-model-options" });
      for (const model of provider.models) datalist.append(el("option", { value: model }));
      box.append(datalist);
    }

    const extra = el(
      "div",
      { class: "settings-grid-2", style: { marginTop: "12px" } },
      el(
        "div",
        { class: "field" },
        el("label", { class: "field-label", text: "温度（0–2，越低越稳定）" }),
        numberControl("ai_temperature", { min: 0, max: 2, step: 0.1 }),
      ),
      el(
        "div",
        { class: "field" },
        el("label", { class: "field-label", text: "最大输出 Token" }),
        numberControl("ai_max_tokens", { min: 64, max: 16384, step: 64 }),
      ),
    );
    box.append(extra);
    aiCredBox.append(box);
  }

  renderAiEngines();
  renderAiCredentials();

  /* ------------------------------------------------------------------ */
  /* 任务与性能                                                          */
  /* ------------------------------------------------------------------ */

  const taskSection = makeSection("settings-task", "cpu", "任务与性能", "控制批量识别的并发、重试与超时，避免触发云端限流。");
  taskSection.body.append(
    makeRow("默认并发数", "1–8，演示/本地引擎建议 2–4", numberControl("concurrency", { min: 1, max: 8 })),
    makeRow("失败重试次数", "单个任务失败后的最大重试次数", numberControl("max_retries", { min: 0, max: 5 })),
    makeRow("重试退避倍数", "每次重试的等待时间按倍数增长", numberControl("retry_backoff", { min: 1, max: 5, step: 0.1 })),
    makeRow("外部请求超时", "OCR / AI 单次调用超时时间", numberControl("request_timeout", { min: 5, max: 300, suffix: "秒" })),
    makeRow("单文件大小上限", "超过该大小的图片会被拒绝", numberControl("max_file_mb", { min: 1, max: 100, suffix: "MB" })),
    makeRow("历史分页条数", "历史记录默认每页显示数量", numberControl("history_page_size", { min: 5, max: 100, suffix: "条" })),
  );

  /* ------------------------------------------------------------------ */
  /* 网页提取                                                            */
  /* ------------------------------------------------------------------ */

  const webSection = makeSection("settings-web", "globe", "网页提取", "控制抓取超时、响应体大小与提取后的自动打开行为。");
  const autoOpen = switchControl("auto_open_web", "提取成功后自动打开原文");
  webSection.body.append(
    makeRow("提取后自动打开网页", "桌面模式调用系统浏览器；浏览器模式新开标签页", autoOpen.wrapper),
    makeRow("抓取超时", "超过该时间将放弃本次提取", numberControl("web_timeout", { min: 3, max: 120, suffix: "秒" })),
    makeRow(
      "响应体大小上限",
      "防止抓取超大页面导致内存占用过高",
      (() => {
        const mb = Math.max(0.1, Number(values.web_max_bytes || 3_000_000) / 1_000_000);
        const input = el("input", { class: "input input-sm", type: "number", min: "0.1", max: "20", step: "0.1", value: mb });
        input.addEventListener("input", () => {
          values.web_max_bytes = Math.round(Number(input.value || 0) * 1_000_000);
          markDirty();
        });
        return el("div", { class: "row", style: { gap: "6px" } }, input, el("span", { class: "text-xs muted", text: "MB" }));
      })(),
    ),
  );

  /* ------------------------------------------------------------------ */
  /* 外观与语言                                                          */
  /* ------------------------------------------------------------------ */

  const uiSection = makeSection("settings-ui", "moon", "外观与语言", "主题立即生效；界面语言在保存后切换。");

  const themeSegmented = el("div", { class: "segmented", style: { width: "260px" } });
  for (const option of [
    { value: "dark", label: "深色" },
    { value: "light", label: "浅色" },
    { value: "system", label: "跟随系统" },
  ]) {
    const button = el("button", {
      type: "button",
      text: option.label,
      class: selectedTheme === option.value ? "active" : "",
    });
    button.addEventListener("click", () => {
      selectedTheme = option.value;
      values.theme = option.value;
      themeSegmented.querySelectorAll("button").forEach((item) => item.classList.toggle("active", item === button));
      setTheme(option.value);
      markDirty();
    });
    themeSegmented.append(button);
  }

  const languageSelect = el("select", { class: "select input-sm", style: { width: "150px" } });
  for (const option of [
    { value: "zh", label: "简体中文" },
    { value: "en", label: "English" },
  ]) {
    languageSelect.append(el("option", { value: option.value, text: option.label, selected: selectedLanguage === option.value }));
  }
  languageSelect.addEventListener("change", () => {
    selectedLanguage = languageSelect.value;
    values.ui_language = languageSelect.value;
    markDirty();
  });

  const autoSave = switchControl("editor_auto_save", "编辑后自动保存（推荐）");

  uiSection.body.append(
    makeRow("界面主题", "深色、浅色或跟随系统", themeSegmented),
    makeRow("界面语言", "导航与页面标题的语言", languageSelect),
    makeRow("编辑器自动保存", "关闭后仍可通过 Ctrl+S 手动保存", autoSave.wrapper),
  );

  /* ------------------------------------------------------------------ */
  /* 数据管理                                                            */
  /* ------------------------------------------------------------------ */

  const dataSection = makeSection("settings-data", "database", "数据管理", "所有数据保存在本机；上传文件默认可按保留天数自动清理。");

  const statsRow = el(
    "div",
    { class: "meta-grid", style: { marginBottom: "14px" } },
    metaCard("文字资产", historyStats ? `${formatNumber(historyStats.total)} 条` : "—"),
    metaCard("收藏", historyStats ? `${formatNumber(historyStats.favorites)} 条` : "—"),
    metaCard("总字数", historyStats ? formatNumber(historyStats.total_chars) : "—"),
    metaCard("数据目录", systemInfo ? formatBytes(systemInfo.storage?.bytes || 0) : "—"),
  );

  const cleanupButton = el("button", {
    class: "btn btn-secondary btn-sm",
    type: "button",
    html: `${icon("trash", 13)}立即清理`,
    onclick: async () => {
      const days = Number(values.keep_uploads_days || 30);
      const confirmed = await confirmDialog({
        title: "清理过期上传文件？",
        message: `将删除超过 ${days} 天的原图、缩略图与临时文件。历史记录中的文本不会受影响。`,
        confirmText: "开始清理",
      });
      if (!confirmed) return;
      cleanupButton.disabled = true;
      cleanupButton.textContent = "清理中…";
      try {
        const result = await api.cleanup(days);
        toastSuccess("清理完成", `删除 ${result.removed} 个文件，释放 ${formatBytes(result.freed_bytes)}`);
      } catch (error) {
        toastError("清理失败", error.message || String(error));
      } finally {
        cleanupButton.disabled = false;
        cleanupButton.innerHTML = `${icon("trash", 13)}立即清理`;
      }
    },
  });

  dataSection.body.append(
    statsRow,
    makeRow("上传文件保留天数", "超过天数的原图会被清理，文本记录保留", numberControl("keep_uploads_days", { min: 1, max: 3650, suffix: "天" })),
    makeRow("清理上传文件", "建议在磁盘空间紧张时执行", cleanupButton),
  );

  function metaCard(label, value) {
    return el(
      "div",
      { class: "meta-item" },
      el("div", { class: "meta-label", text: label }),
      el("div", { class: "meta-value", text: value }),
    );
  }

  /* ------------------------------------------------------------------ */
  /* 关于                                                                */
  /* ------------------------------------------------------------------ */

  const aboutSection = makeSection("settings-about", "info", "关于", "课程综合实践 2 · 三人团队协作项目。");
  aboutSection.body.append(
    el(
      "div",
      { class: "settings-grid-2" },
      el(
        "div",
        { class: "kv" },
        kvRow("应用名称", "识文台 InsightDesk"),
        kvRow("版本", `v${APP_VERSION}`),
        kvRow("运行模式", systemInfo?.desktop_mode ? "桌面模式" : "浏览器模式"),
        kvRow("Python", systemInfo?.python || "—"),
        kvRow("数据目录", systemInfo?.data_dir || "—"),
        kvRow("存储占用", systemInfo ? `${formatBytes(systemInfo.storage?.bytes || 0)} / ${systemInfo.storage?.files || 0} 个文件` : "—"),
      ),
      el(
        "div",
        { class: "team-list" },
        ...TEAM.map((member) =>
          el(
            "div",
            { class: "team-member" },
            el("span", { class: "team-avatar", text: member.initial }),
            el(
              "div",
              { class: "team-info" },
              el("strong", { text: `${member.name} · ${member.weight}` }),
              el("span", { text: member.role }),
            ),
          ),
        ),
        el("div", { class: "row wrap", style: { gap: "6px", marginTop: "4px" } },
          ...TECH_STACK.map((item) => el("span", { class: "chip", text: item.name })),
        ),
      ),
    ),
  );

  function kvRow(key, value) {
    return el(
      "div",
      { class: "kv-row" },
      el("span", { class: "kv-key", text: key }),
      el("span", { class: "kv-value", text: value }),
    );
  }

  /* ------------------------------------------------------------------ */
  /* 保存                                                                */
  /* ------------------------------------------------------------------ */

  const saveCard = el(
    "section",
    { class: "card" },
    el(
      "div",
      { class: "card-body settings-footer", style: { justifyContent: "space-between" } },
      el("span", { class: "text-xs muted", text: "保存后立即生效。密钥接口仅返回掩码，不会泄露到浏览器。" }),
      el(
        "div",
        { class: "row", style: { gap: "8px" } },
        el("button", {
          class: "btn btn-ghost",
          type: "button",
          text: "放弃修改",
          onclick: () => render(container),
        }),
        el("button", {
          class: "btn btn-primary",
          type: "button",
          id: "save-settings",
          html: `${icon("save", 14)}保存设置`,
        }),
      ),
    ),
  );
  sectionsRoot.append(saveCard);

  page.querySelector("#reload-settings").addEventListener("click", async () => {
    if (!dirtyPill.hidden) {
      const confirmed = await confirmDialog({
        title: "放弃未保存的修改？",
        message: "当前页面中尚未保存的设置会恢复为上一次保存的值。",
        confirmText: "放弃修改",
        danger: true,
      });
      if (!confirmed) return;
    }
    render(container);
  });

  page.querySelector("#save-settings").addEventListener("click", async (event) => {
    const button = event.currentTarget;
    button.disabled = true;
    button.innerHTML = '<span class="spinner"></span>保存中…';

    const payload = {};
    for (const [key, value] of Object.entries(values)) {
      if (key.startsWith("_")) continue;
      if (value === MASK) continue;
      if (value === undefined || value === null) continue;
      payload[key] = value;
    }
    payload.theme = selectedTheme;
    payload.ui_language = selectedLanguage;

    // 校验数值范围
    const ranges = {
      concurrency: [1, 8],
      max_retries: [0, 5],
      retry_backoff: [1, 5],
      request_timeout: [5, 300],
      max_file_mb: [1, 100],
      history_page_size: [5, 100],
      web_timeout: [3, 120],
      keep_uploads_days: [1, 3650],
    };
    for (const [key, [min, max]] of Object.entries(ranges)) {
      const value = Number(payload[key]);
      if (!Number.isFinite(value) || value < min || value > max) {
        toastWarning("参数超出范围", `${key} 需要在 ${min}–${max} 之间`);
        button.disabled = false;
        button.innerHTML = `${icon("save", 14)}保存设置`;
        return;
      }
    }

    try {
      const updated = await api.updateSettings(payload);
      values = { ...updated.values };
      original = { ...updated.values };
      dirtyPill.hidden = true;
      applyTheme(selectedTheme);
      toastSuccess("设置已保存", "新配置对后续任务立即生效");

      if (selectedLanguage !== state.language) {
        setLanguage(selectedLanguage);
      }
    } catch (error) {
      toastError("保存失败", error.message || String(error));
    } finally {
      button.disabled = false;
      button.innerHTML = `${icon("save", 14)}保存设置`;
    }
  });

  // 侧边导航高亮
  const navLinks = Array.from(page.querySelectorAll(".settings-nav a"));
  navLinks.forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      const target = page.querySelector(link.getAttribute("href"));
      target?.scrollIntoView({ behavior: "smooth", block: "start" });
      navLinks.forEach((item) => item.classList.toggle("active", item === link));
    });
  });

  return {
    destroy() {
      /* 无全局监听 */
    },
  };
}
