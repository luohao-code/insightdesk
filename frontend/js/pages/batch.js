/**
 * 批量任务页。
 * 上传多张图片创建批次，实时查看进度，支持取消与失败重试。
 */

import { api } from "../api.js";
import { el, formatDuration, statusLabel, timeAgo } from "../utils.js";
import { icon } from "../icons.js";
import { navigate } from "../router.js";
import { state } from "../store.js";
import { createUploader } from "../components/uploader.js";
import { confirmDialog } from "../components/modal.js";
import { toastError, toastSuccess, toastWarning } from "../components/toast.js";

const STATUS_PILL = {
  queued: "pill-soft",
  running: "pill-accent",
  succeeded: "pill-green",
  partial: "pill-amber",
  failed: "pill-red",
  cancelled: "pill-soft",
};

export async function render(container) {
  const page = el("div", { class: "page" });
  page.innerHTML = `
    <div class="page-header">
      <div>
        <h2>${icon("layers", 20)} 批量任务</h2>
        <p>一次上传多张图片，后台按并发限制排队执行。进度实时推送，失败任务可单独重试，100 张图片也能稳定跑完。</p>
      </div>
      <div class="page-actions">
        <button class="btn btn-ghost btn-sm" type="button" id="batch-refresh">${icon("refresh", 14)}刷新</button>
        <button class="btn btn-ghost btn-sm" type="button" data-go="ocr">${icon("scan", 14)}单图识别</button>
      </div>
    </div>

    <div class="batch-grid">
      <section class="card batch-create">
        <div class="card-header">
          <div class="card-title">${icon("upload", 16)} 新建批次</div>
          <span class="pill pill-soft" id="batch-image-count">0 张</span>
        </div>
        <div class="card-body">
          <div id="batch-uploader"></div>
          <div class="col" style="margin-top:16px;gap:12px">
            <div class="field">
              <label class="field-label" for="batch-name">批次名称</label>
              <input class="input" id="batch-name" placeholder="例如：文献扫描件 01" maxlength="60" />
            </div>
            <div class="settings-grid-2" style="grid-template-columns:1fr 1fr;gap:10px">
              <div class="field">
                <label class="field-label" for="batch-engine">OCR 引擎</label>
                <select class="select" id="batch-engine"></select>
              </div>
              <div class="field">
                <label class="field-label" for="batch-language">语言</label>
                <select class="select" id="batch-language">
                  <option value="auto">中英混合</option>
                  <option value="zh">中文</option>
                  <option value="en">英文</option>
                </select>
              </div>
            </div>
            <div class="field">
              <label class="field-label" for="batch-concurrency">并发数（1–8）</label>
              <input class="input" id="batch-concurrency" type="number" min="1" max="8" value="3" />
              <p class="field-hint">并发越高速度越快，但可能触发云端接口限流。演示/本地引擎建议 2–4。</p>
            </div>
          </div>
        </div>
        <div class="card-footer" style="display:block">
          <button class="btn btn-primary btn-block" type="button" id="batch-create" disabled>
            ${icon("play", 15)}创建并开始识别
          </button>
        </div>
      </section>

      <div class="col" style="gap:16px">
        <section class="card batch-list-panel">
          <div class="card-header">
            <div class="card-title">${icon("layers", 16)} 批次列表</div>
            <span class="pill pill-soft" id="batch-total">0 个批次</span>
          </div>
          <div id="batch-list" style="max-height:330px;overflow-y:auto"></div>
        </section>

        <section class="card" id="batch-detail-card" hidden>
          <div class="card-header">
            <div class="batch-detail-head">
              <div class="card-title" id="detail-name">批次详情</div>
              <span class="pill pill-soft" id="detail-status">—</span>
              <span class="pill pill-soft" id="detail-engine">—</span>
            </div>
            <div class="row" style="gap:6px">
              <button class="btn btn-ghost btn-sm" type="button" id="detail-retry">${icon("refresh", 13)}重试失败项</button>
              <button class="btn btn-ghost btn-sm" type="button" id="detail-cancel">${icon("stop", 13)}取消</button>
            </div>
          </div>
          <div class="card-body">
            <div class="col" style="gap:12px">
              <div class="batch-stats">
                <div class="batch-stat"><span>总数</span><strong id="detail-total">0</strong></div>
                <div class="batch-stat"><span>成功</span><strong id="detail-succeeded" style="color:var(--green)">0</strong></div>
                <div class="batch-stat"><span>失败</span><strong id="detail-failed" style="color:var(--red)">0</strong></div>
                <div class="batch-stat"><span>进度</span><strong id="detail-progress">0%</strong></div>
              </div>
              <div class="progress progress-lg"><div class="progress-bar striped" id="detail-progress-bar" style="width:0%"></div></div>
              <div class="row-between">
                <span class="text-xs muted" id="detail-message"></span>
                <span class="text-xs muted" id="detail-time"></span>
              </div>
              <div class="task-list" id="task-list"></div>
            </div>
          </div>
        </section>

        <div class="card" id="batch-empty">
          <div class="empty">
            <div class="empty-icon">${icon("layers", 24)}</div>
            <strong>还没有批量任务</strong>
            <p>上传多张图片并创建批次，进度会实时显示在这里。也可以先在单图识别中调整参数。</p>
            <button class="btn btn-secondary btn-sm" type="button" data-go="ocr">先去单图识别</button>
          </div>
        </div>
      </div>
    </div>
  `;
  container.append(page);

  page.querySelectorAll("[data-go]").forEach((button) => {
    button.addEventListener("click", () => navigate(button.dataset.go));
  });

  const uploader = createUploader({
    multiple: true,
    maxFiles: 100,
    compact: true,
    title: "拖拽或点击选择图片（可多选）",
    subtitle: "最多 100 张，单张不超过 20MB",
    onChange: () => updateCount(),
  });
  page.querySelector("#batch-uploader").append(uploader.element);

  let batches = [];
  let current = null;
  let refreshDebounce = null;
  let pollTimer = null;
  let batchEventBound = false;

  const listNode = page.querySelector("#batch-list");
  const detailCard = page.querySelector("#batch-detail-card");
  const emptyCard = page.querySelector("#batch-empty");
  const createButton = page.querySelector("#batch-create");

  function updateCount() {
    const count = uploader.getImages().length;
    page.querySelector("#batch-image-count").textContent = `${count} 张`;
    createButton.disabled = count === 0;
  }

  /* ------------------------------------------------------------------ */
  /* 初始化引擎                                                          */
  /* ------------------------------------------------------------------ */

  try {
    const engines = await api.engines();
    const select = page.querySelector("#batch-engine");
    for (const item of engines.items) {
      if (!item.available) continue;
      select.append(el("option", { value: item.name, text: item.label, selected: item.name === engines.default }));
    }
    if (!select.value && select.options.length) select.selectedIndex = 0;
  } catch (error) {
    toastError("引擎加载失败", error.message || String(error));
  }

  /* ------------------------------------------------------------------ */
  /* 批次列表                                                            */
  /* ------------------------------------------------------------------ */

  async function loadBatches({ keepSelection = true } = {}) {
    try {
      const result = await api.listBatches({ limit: 30 });
      batches = result.items || [];
      page.querySelector("#batch-total").textContent = `${result.total || 0} 个批次`;
      renderList();
      if (!batches.length) {
        detailCard.hidden = true;
        emptyCard.hidden = false;
        return;
      }
      emptyCard.hidden = true;
      const preferred = keepSelection && state.activeBatchId;
      const target = batches.find((item) => item.id === preferred) || batches[0];
      if (target) await selectBatch(target.id, { silent: true });
    } catch (error) {
      toastError("批次列表加载失败", error.message || String(error));
    }
  }

  function renderList() {
    listNode.innerHTML = "";
    if (!batches.length) {
      listNode.append(
        el("div", { class: "empty", style: { padding: "28px 16px" } }, el("p", { text: "暂无批次" })),
      );
      return;
    }

    for (const batch of batches) {
      const item = el(
        "div",
        {
          class: `batch-item${current?.id === batch.id ? " active" : ""}`,
          dataset: { id: String(batch.id) },
          role: "button",
          tabindex: "0",
        },
        el(
          "div",
          { class: "batch-item-top" },
          el("strong", { text: batch.name }),
          el("span", { class: `pill ${STATUS_PILL[batch.status] || "pill-soft"}`, text: statusLabel(batch.status) }),
        ),
        el(
          "div",
          { class: "batch-item-meta" },
          el("span", {
            text: `${batch.total} 张 · 成功 ${batch.succeeded} · 失败 ${batch.failed}`,
          }),
          el("span", { text: timeAgo(batch.created_at) }),
        ),
        el(
          "div",
          { class: "progress progress-sm" },
          el("div", {
            class: "progress-bar",
            style: { width: `${batch.progress}%` },
          }),
        ),
      );
      const open = () => selectBatch(batch.id);
      item.addEventListener("click", open);
      item.addEventListener("keydown", (event) => {
        if (event.key === "Enter") open();
      });
      listNode.append(item);
    }
  }

  async function selectBatch(id, { silent = false } = {}) {
    state.activeBatchId = id;
    current = batches.find((item) => item.id === id) || current;
    renderList();
    detailCard.hidden = false;
    emptyCard.hidden = true;
    try {
      const detail = await api.getBatch(id);
      applyDetail(detail);
      if (!silent) toastSuccess("已切换批次", detail.name);
    } catch (error) {
      if (!silent) toastError("批次详情加载失败", error.message || String(error));
    }
  }

  function applyDetail(detail) {
    current = detail;
    page.querySelector("#detail-name").textContent = detail.name;
    const statusPill = page.querySelector("#detail-status");
    statusPill.textContent = statusLabel(detail.status);
    statusPill.className = `pill ${STATUS_PILL[detail.status] || "pill-soft"}`;
    page.querySelector("#detail-engine").textContent = detail.engine;
    page.querySelector("#detail-total").textContent = String(detail.total);
    page.querySelector("#detail-succeeded").textContent = String(detail.succeeded);
    page.querySelector("#detail-failed").textContent = String(detail.failed);
    page.querySelector("#detail-progress").textContent = `${detail.progress}%`;
    page.querySelector("#detail-progress-bar").style.width = `${detail.progress}%`;
    page.querySelector("#detail-message").textContent = detail.message || "";
    page.querySelector("#detail-time").textContent = detail.started_at
      ? `${timeAgo(detail.started_at)}开始 · ${detail.finished_at ? `${timeAgo(detail.finished_at)}结束` : "进行中"}`
      : "";

    const retryButton = page.querySelector("#detail-retry");
    retryButton.disabled = !["failed", "partial", "cancelled", "succeeded"].includes(detail.status) || detail.failed === 0;
    const cancelButton = page.querySelector("#detail-cancel");
    cancelButton.disabled = ["succeeded", "failed", "partial", "cancelled"].includes(detail.status);

    renderTasks(detail.tasks || []);
  }

  function renderTasks(tasks) {
    const list = page.querySelector("#task-list");
    list.innerHTML = "";
    if (!tasks.length) {
      list.append(el("div", { class: "empty", style: { padding: "20px" } }, el("p", { text: "暂无任务项" })));
      return;
    }
    for (const task of tasks) {
      const row = el("div", { class: "task-row" });
      if (task.thumbnail_url) {
        row.append(
          el("img", { class: "task-thumb", src: task.thumbnail_url, alt: task.filename, loading: "lazy" }),
        );
      } else {
        row.append(
          el("span", { class: "task-thumb", style: { display: "grid", placeItems: "center", color: "var(--muted)" }, html: icon("image", 14) }),
        );
      }
      row.append(el("span", { class: "task-name", text: task.filename, title: task.filename }));
      row.append(
        el("span", {
          class: `status-text ${["succeeded", "failed", "running", "queued", "cancelled"].includes(task.status) ? task.status : "queued"}`,
          text: statusLabel(task.status),
        }),
      );
      if (task.error) {
        row.append(el("span", { class: "task-error", text: task.error, title: task.error }));
      }
      row.append(el("span", { class: "task-duration", text: task.duration_ms ? formatDuration(task.duration_ms) : "—" }));
      if (task.status === "succeeded" && task.document_id) {
        row.style.cursor = "pointer";
        row.addEventListener("click", () => navigate("history", { doc: task.document_id }));
      }
      list.append(row);
    }
  }

  async function refreshDetail() {
    if (!current?.id) return;
    try {
      const detail = await api.getBatch(current.id);
      applyDetail(detail);
      const index = batches.findIndex((item) => item.id === detail.id);
      if (index >= 0) {
        batches[index] = { ...batches[index], ...detail, tasks: undefined };
        renderList();
      }
      if (["succeeded", "failed", "partial", "cancelled"].includes(detail.status)) {
        stopPolling();
      }
    } catch {
      /* 静默失败，等待下次事件或轮询 */
    }
  }

  function scheduleRefresh() {
    clearTimeout(refreshDebounce);
    refreshDebounce = setTimeout(refreshDetail, 320);
  }

  function startPolling() {
    if (pollTimer) return;
    pollTimer = setInterval(refreshDetail, 4000);
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  function onBatchEvent(event) {
    const payload = event.detail || {};
    if (!payload.batch?.id) return;
    const index = batches.findIndex((item) => item.id === payload.batch.id);
    if (index >= 0) {
      batches[index] = payload.batch;
      renderList();
    } else {
      batches.unshift(payload.batch);
      renderList();
    }
    if (current?.id === payload.batch.id) scheduleRefresh();
    if (payload.type === "batch_finished" && payload.batch.status !== "succeeded") {
      toastWarning("批次结束", payload.batch.message || "部分任务失败，可点击重试");
    }
    if (payload.type === "batch_finished" && payload.batch.status === "succeeded") {
      toastSuccess("批次完成", `${payload.batch.name} 全部识别成功`);
    }
  }

  window.addEventListener("batch-event", onBatchEvent);
  batchEventBound = true;

  /* ------------------------------------------------------------------ */
  /* 操作                                                                */
  /* ------------------------------------------------------------------ */

  createButton.addEventListener("click", async () => {
    const images = uploader.getImages();
    if (!images.length) {
      toastWarning("请先上传图片", "支持一次选择最多 100 张");
      return;
    }
    createButton.disabled = true;
    createButton.innerHTML = '<span class="spinner"></span>正在创建…';
    try {
      const payload = {
        images: images.map((image) => ({ image_id: image.id, filename: image.filename })),
        engine: page.querySelector("#batch-engine").value || null,
        language: page.querySelector("#batch-language").value,
        concurrency: Number(page.querySelector("#batch-concurrency").value) || 3,
        name: page.querySelector("#batch-name").value.trim() || null,
      };
      const result = await api.createBatch(payload);
      state.activeBatchId = result.batch.id;
      uploader.clear();
      updateCount();
      toastSuccess("批次已创建", `${result.accepted} 张图片已加入队列`);
      await loadBatches();
      startPolling();
    } catch (error) {
      toastError("创建批次失败", error.message || String(error));
    } finally {
      createButton.disabled = uploader.getImages().length === 0;
      createButton.innerHTML = `${icon("play", 15)}创建并开始识别`;
    }
  });

  page.querySelector("#detail-retry").addEventListener("click", async () => {
    if (!current?.id) return;
    try {
      await api.retryBatch(current.id);
      toastSuccess("已重新入队", "失败任务将按原并发数重试");
      await refreshDetail();
      startPolling();
    } catch (error) {
      toastError("重试失败", error.message || String(error));
    }
  });

  page.querySelector("#detail-cancel").addEventListener("click", async () => {
    if (!current?.id) return;
    const confirmed = await confirmDialog({
      title: "取消这个批次？",
      message: "未开始的任务会被标记为已取消，正在执行的任务会等待当前图片处理完成后停止。",
      confirmText: "取消批次",
      danger: true,
    });
    if (!confirmed) return;
    try {
      await api.cancelBatch(current.id);
      toastWarning("已请求取消", "批次状态将在片刻后更新");
      scheduleRefresh();
    } catch (error) {
      toastError("取消失败", error.message || String(error));
    }
  });

  page.querySelector("#batch-refresh").addEventListener("click", () => {
    loadBatches();
    toastSuccess("已刷新", "批次状态已更新");
  });

  await loadBatches({ keepSelection: false });
  if (current && ["queued", "running"].includes(current.status)) startPolling();
  updateCount();

  return {
    destroy() {
      stopPolling();
      clearTimeout(refreshDebounce);
      if (batchEventBound) window.removeEventListener("batch-event", onBatchEvent);
      uploader.destroy();
    },
  };
}
