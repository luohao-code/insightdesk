/**
 * 帮助与关于。
 */

import { el } from "../utils.js";
import { icon } from "../icons.js";
import { navigate } from "../router.js";
import { APP_VERSION, REPO_URL, TEAM, TECH_STACK } from "../config.js";

export async function render(container) {
  const page = el("div", { class: "page" });
  page.innerHTML = `
    <section class="help-hero">
      <div class="row-between wrap" style="align-items:flex-start">
        <div>
          <span class="hero-eyebrow">${icon("book", 12)} 使用帮助</span>
          <h2>三步开始你的文字资产库</h2>
          <p style="max-width:620px;font-size:12.5px;color:var(--muted)">
            识文台把"图片 / 网页 → 文字 → 智能加工 → 归档导出"串成一条完整链路。
            首次使用建议先用演示引擎跑通流程，再在设置中配置真实引擎。
          </p>
        </div>
        <div class="row" style="gap:8px">
          <button class="btn btn-primary" type="button" data-go="ocr">${icon("scan", 15)}开始识别</button>
          <a class="btn btn-secondary" href="./api/docs" target="_blank" rel="noopener">${icon("terminal", 15)}API 文档</a>
        </div>
      </div>
    </section>

    <div class="help-grid">
      <article class="help-card">
        <span class="help-step">01</span>
        <h3>导入图片或网页</h3>
        <p>拖拽、点击选择或直接粘贴截图；也可以输入文章链接提取正文。图片会保存在本机 data 目录。</p>
        <button class="btn btn-ghost btn-sm" type="button" data-go="ocr" style="align-self:flex-start">去识别 ${icon("chevronRight", 12)}</button>
      </article>
      <article class="help-card">
        <span class="help-step">02</span>
        <h3>识别、编辑与智能加工</h3>
        <p>识别结果可直接修改并自动保存。翻译、摘要、关键词与问答不会覆盖原文，可复制、追加或替换。</p>
        <button class="btn btn-ghost btn-sm" type="button" data-go="ai" style="align-self:flex-start">打开 AI 助手 ${icon("chevronRight", 12)}</button>
      </article>
      <article class="help-card">
        <span class="help-step">03</span>
        <h3>检索、导出与沉淀</h3>
        <p>历史记录支持全文检索、标签与收藏。可导出 TXT、Markdown、Word、Excel、CSV、JSON 或 ZIP。</p>
        <button class="btn btn-ghost btn-sm" type="button" data-go="history" style="align-self:flex-start">查看历史 ${icon("chevronRight", 12)}</button>
      </article>
    </div>

    <div class="grid grid-2">
      <section class="card">
        <div class="card-header"><div class="card-title">${icon("mouse", 16)} 快捷键</div></div>
        <div class="card-body">
          ${[
            ["打开命令面板 / 搜索", "Ctrl K"],
            ["粘贴剪贴板截图上传", "Ctrl V"],
            ["编辑器保存", "Ctrl S"],
            ["关闭弹窗 / 面板", "Esc"],
            ["切换主题", "命令面板中搜索「主题」"],
          ]
            .map(
              ([label, keys]) => `
              <div class="shortcut-row">
                <span>${label}</span>
                <span class="shortcut-keys">${keys
                  .split(" ")
                  .map((key) => `<kbd>${key}</kbd>`)
                  .join("")}</span>
              </div>`,
            )
            .join("")}
        </div>
      </section>

      <section class="card">
        <div class="card-header"><div class="card-title">${icon("cpu", 16)} 技术栈</div></div>
        <div class="card-body">
          <div class="row wrap" style="gap:8px">
            ${TECH_STACK.map(
              (item) => `<span class="chip" title="${item.detail}">${item.name}</span>`,
            ).join("")}
          </div>
          <div class="kv" style="margin-top:14px">
            <div class="kv-row"><span class="kv-key">架构模式</span><span class="kv-value">B/S · 分层架构</span></div>
            <div class="kv-row"><span class="kv-key">前端</span><span class="kv-value">原生 ES Module · 零依赖</span></div>
            <div class="kv-row"><span class="kv-key">后端</span><span class="kv-value">FastAPI · SQLAlchemy · SQLite</span></div>
            <div class="kv-row"><span class="kv-key">实时进度</span><span class="kv-value">SSE + 轮询降级</span></div>
            <div class="kv-row"><span class="kv-key">桌面打包</span><span class="kv-value">PyInstaller</span></div>
          </div>
        </div>
      </section>
    </div>

    <div class="grid grid-2">
      <section class="card">
        <div class="card-header">
          <div class="card-title">${icon("users", 16)} 项目团队</div>
          <span class="pill pill-soft">三人协作</span>
        </div>
        <div class="card-body">
          <div class="team-list">
            ${TEAM.map(
              (member) => `
              <div class="team-member">
                <span class="team-avatar">${member.initial}</span>
                <div class="team-info" style="flex:1">
                  <strong>${member.name} · ${member.role}</strong>
                  <span>${member.duty}</span>
                </div>
                <span class="pill pill-accent">${member.weight}</span>
              </div>`,
            ).join("")}
          </div>
        </div>
        <div class="card-footer">
          <span class="text-xs muted">分工与协作规范见 docs/08-团队分工与协作规范.md</span>
        </div>
      </section>

      <section class="card">
        <div class="card-header"><div class="card-title">${icon("help", 16)} 常见问题</div></div>
        <div class="card-body col" style="gap:14px">
          <div>
            <strong style="font-size:12.5px">识别结果是模拟文本？</strong>
            <p style="font-size:11.5px;color:var(--muted);margin-top:3px">
              说明当前使用演示引擎。安装 <code>rapidocr-onnxruntime</code>，或在设置中填写百度/腾讯 OCR 密钥，即可获得真实识别结果。
            </p>
          </div>
          <div>
            <strong style="font-size:12.5px">密钥会泄露吗？</strong>
            <p style="font-size:11.5px;color:var(--muted);margin-top:3px">
              密钥仅保存在服务端 SQLite 中，接口只返回掩码；前端代码与打包产物不包含任何密钥。
            </p>
          </div>
          <div>
            <strong style="font-size:12.5px">批量任务失败怎么办？</strong>
            <p style="font-size:11.5px;color:var(--muted);margin-top:3px">
              在批量任务页打开批次，点击「重试失败项」。失败原因会显示在任务行中，常见原因是密钥无效、额度不足或图片损坏。
            </p>
          </div>
          <div>
            <strong style="font-size:12.5px">网页提取失败？</strong>
            <p style="font-size:11.5px;color:var(--muted);margin-top:3px">
              动态渲染或需要登录的页面无法直接抓取；系统也会阻止内网地址（SSRF 防护）。请换用公开的静态文章页。
            </p>
          </div>
        </div>
      </section>
    </div>

    <section class="card">
      <div class="card-header"><div class="card-title">${icon("info", 16)} 版本与链接</div></div>
      <div class="card-body">
        <div class="meta-grid">
          <div class="meta-item"><div class="meta-label">应用</div><div class="meta-value">识文台 InsightDesk</div></div>
          <div class="meta-item"><div class="meta-label">版本</div><div class="meta-value">v${APP_VERSION}</div></div>
          <div class="meta-item"><div class="meta-label">课程</div><div class="meta-value">课程综合实践 2</div></div>
          <div class="meta-item"><div class="meta-label">代码规模</div><div class="meta-value">≥ 15,000 行</div></div>
        </div>
        <div class="row wrap" style="gap:8px;margin-top:14px">
          <a class="btn btn-secondary btn-sm" href="./api/docs" target="_blank" rel="noopener">${icon("terminal", 13)}Swagger 接口文档</a>
          <a class="btn btn-secondary btn-sm" href="${REPO_URL}" target="_blank" rel="noopener">${icon("github", 13)}GitHub 仓库</a>
          <button class="btn btn-ghost btn-sm" type="button" data-go="settings">${icon("settings", 13)}引擎设置</button>
        </div>
      </div>
    </section>
  `;
  container.append(page);

  page.querySelectorAll("[data-go]").forEach((button) => {
    button.addEventListener("click", () => navigate(button.dataset.go));
  });
}
