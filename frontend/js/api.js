/**
 * 后端 API 客户端。
 * - 统一超时与错误处理
 * - 上传使用 XHR 以获得进度
 * - 导出返回 Blob 与文件名
 */

const API_BASE = "/api";

export class ApiError extends Error {
  constructor(message, { status = 0, code = "error", details = null } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

function combineSignal(timeout) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  return { signal: controller.signal, clear: () => clearTimeout(timer) };
}

async function parseBody(response) {
  const contentType = response.headers.get("Content-Type") || "";
  if (response.status === 204) return null;
  if (contentType.includes("application/json")) {
    try {
      return await response.json();
    } catch {
      return null;
    }
  }
  return await response.text();
}

async function request(path, options = {}) {
  const {
    method = "GET",
    body = null,
    headers = {},
    timeout = 30_000,
    raw = false,
    signal: externalSignal = null,
  } = options;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  const onAbort = () => controller.abort();
  if (externalSignal) externalSignal.addEventListener("abort", onAbort, { once: true });

  const init = { method, headers: { Accept: "application/json", ...headers }, signal: controller.signal };
  if (body instanceof FormData) {
    init.body = body;
  } else if (body !== null && body !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch (error) {
    clearTimeout(timer);
    if (error.name === "AbortError") {
      throw new ApiError("请求超时，请稍后重试", { code: "timeout" });
    }
    throw new ApiError("无法连接服务器，请确认服务已启动", { code: "network" });
  } finally {
    clearTimeout(timer);
    if (externalSignal) externalSignal.removeEventListener("abort", onAbort);
  }

  if (!response.ok) {
    const payload = await parseBody(response).catch(() => null);
    const detail =
      (payload && (payload.detail || payload.message)) || `请求失败（HTTP ${response.status}）`;
    throw new ApiError(typeof detail === "string" ? detail : "请求参数有误", {
      status: response.status,
      code: payload?.code || "http",
      details: payload?.errors || null,
    });
  }

  if (raw) {
    return {
      blob: await response.blob(),
      filename: response.headers.get("Content-Disposition") || "",
      count: Number(response.headers.get("X-Export-Count") || 0),
    };
  }
  return parseBody(response);
}

function toQuery(params = {}) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === "") continue;
    search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

/* ------------------------------------------------------------------ */
/* 上传（XHR 进度）                                                    */
/* ------------------------------------------------------------------ */

export function uploadImages(files, { onProgress } = {}) {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    for (const file of files) form.append("files", file, file.name);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/ocr/upload`);
    xhr.timeout = 180_000;

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };

    xhr.onload = () => {
      let payload = null;
      try {
        payload = JSON.parse(xhr.responseText || "null");
      } catch {
        payload = null;
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        onProgress?.(100);
        resolve(payload);
      } else {
        reject(
          new ApiError(payload?.detail || `上传失败（HTTP ${xhr.status}）`, {
            status: xhr.status,
          }),
        );
      }
    };

    xhr.onerror = () => reject(new ApiError("上传失败，网络异常", { code: "network" }));
    xhr.ontimeout = () => reject(new ApiError("上传超时，请减少文件数量或压缩图片", { code: "timeout" }));
    xhr.send(form);
  });
}

/* ------------------------------------------------------------------ */
/* 接口定义                                                            */
/* ------------------------------------------------------------------ */

export const api = {
  request,

  // 系统
  health: () => request("/health", { timeout: 8000 }),
  systemInfo: () => request("/system/info"),
  logs: (lines = 200) => request(`/system/logs?lines=${lines}`),
  cleanup: (days = null, dryRun = false) =>
    request(`/system/cleanup${toQuery({ days, dry_run: dryRun })}`, { method: "POST", timeout: 60_000 }),

  // 统计
  stats: () => request("/stats/overview"),

  // OCR
  engines: () => request("/ocr/engines"),
  upload: uploadImages,
  recognize: (payload) => request("/ocr/recognize", { method: "POST", body: payload, timeout: 180_000 }),

  // 批量任务
  createBatch: (payload) =>
    request("/tasks/batches", { method: "POST", body: payload, timeout: 60_000 }),
  listBatches: (params = {}) => request(`/tasks/batches${toQuery(params)}`),
  getBatch: (id) => request(`/tasks/batches/${id}`),
  retryBatch: (id, taskIds = null) =>
    request(`/tasks/batches/${id}/retry`, { method: "POST", body: { task_ids: taskIds } }),
  cancelBatch: (id) => request(`/tasks/batches/${id}/cancel`, { method: "POST" }),
  taskSummary: () => request("/tasks/summary"),
  streamUrl: (batchId = null) => `${API_BASE}/tasks/stream${toQuery({ batch_id: batchId })}`,

  // AI
  aiActions: () => request("/ai/actions"),
  aiProviders: () => request("/ai/providers"),
  aiProcess: (payload) => request("/ai/process", { method: "POST", body: payload, timeout: 180_000 }),
  aiChat: (payload) => request("/ai/chat", { method: "POST", body: payload, timeout: 180_000 }),
  conversations: () => request("/ai/conversations"),
  conversation: (id) => request(`/ai/conversations/${id}`),
  deleteConversation: (id) => request(`/ai/conversations/${id}`, { method: "DELETE" }),

  // 历史
  history: (params = {}) => request(`/history${toQuery(params)}`),
  document: (id) => request(`/history/${id}`),
  updateDocument: (id, patch) => request(`/history/${id}`, { method: "PATCH", body: patch }),
  deleteDocument: (id) => request(`/history/${id}`, { method: "DELETE" }),
  bulkDelete: (ids) => request("/history/bulk-delete", { method: "POST", body: { ids } }),
  historyStats: () => request("/history/stats"),
  historyTags: () => request("/history/tags"),

  // 导出
  exportFormats: () => request("/export/formats"),
  async exportRecords(ids, format = "txt") {
    const result = await request("/export", {
      method: "POST",
      body: { ids, format },
      timeout: 120_000,
      raw: true,
    });
    return result;
  },

  // 网页
  webExtract: (payload) => request("/web/extract", { method: "POST", body: payload, timeout: 90_000 }),
  webOpen: (url) => request("/web/open", { method: "POST", body: { url }, timeout: 30_000 }),
  webHistory: (limit = 20) => request(`/web/history?limit=${limit}`),
  webRecord: (id) => request(`/web/records/${id}`),
  webToDocument: (id) => request(`/web/records/${id}/to-document`, { method: "POST" }),

  // 设置
  settings: () => request("/settings"),
  updateSettings: (values) => request("/settings", { method: "PUT", body: { values } }),
  testProvider: (kind, name) =>
    request("/settings/test", { method: "POST", body: { kind, name }, timeout: 120_000 }),
};
