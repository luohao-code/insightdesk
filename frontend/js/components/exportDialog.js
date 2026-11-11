/**
 * 导出弹窗：选择格式并下载。
 */

import { api } from "../api.js";
import { downloadBlob, el, formatBytes, parseFilename } from "../utils.js";
import { icon } from "../icons.js";
import { EXPORT_FORMATS } from "../config.js";
import { openModal } from "./modal.js";
import { toastError, toastSuccess } from "./toast.js";

export function openExportDialog(ids, { title = "导出记录", subtitle = "" } = {}) {
  const targetIds = Array.isArray(ids) ? ids.filter(Boolean) : [ids].filter(Boolean);
  if (!targetIds.length) {
    toastError("没有可导出的内容", "请先选择至少一条记录");
    return;
  }

  let busy = false;
  const grid = el("div", { class: "grid", style: { gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: "10px" } });

  for (const format of EXPORT_FORMATS) {
    const button = el(
      "button",
      { class: "card card-interactive", type: "button", style: { padding: "14px", textAlign: "left" } },
      el(
        "div",
        { class: "row", style: { gap: "10px", alignItems: "flex-start" } },
        el("span", {
          class: "qa-icon",
          html: icon(format.value === "zip" ? "archive" : format.value === "xlsx" || format.value === "csv" ? "barChart" : "fileText", 15),
        }),
        el(
          "span",
          { style: { flex: "1", minWidth: "0" } },
          el("strong", { style: { fontSize: "12.5px", display: "block" }, text: `${format.label} · ${format.extension}` }),
          el("span", { class: "text-xs muted", text: format.description }),
        ),
      ),
    );

    button.addEventListener("click", async () => {
      if (busy) return;
      busy = true;
      const original = button.innerHTML;
      button.disabled = true;
      button.innerHTML = '<span class="row" style="gap:8px"><span class="spinner" style="border-color:var(--border);border-top-color:var(--accent)"></span>正在生成…</span>';
      try {
        const result = await api.exportRecords(targetIds, format.value);
        const filename = parseFilename(result.filename, `insightdesk_export.${format.value}`);
        downloadBlob(result.blob, filename);
        toastSuccess("导出完成", `${filename} · ${formatBytes(result.blob.size)}`);
        close();
      } catch (error) {
        toastError("导出失败", error.message || String(error));
        button.disabled = false;
        button.innerHTML = original;
      } finally {
        busy = false;
      }
    });

    grid.append(button);
  }

  const notice = el(
    "div",
    { class: "notice", style: { marginBottom: "14px" } },
    el("span", { html: icon("info", 15) }),
    el("span", {
      text: `将导出 ${targetIds.length} 条记录。Word/Excel 会包含标题、来源、引擎与时间等元信息；CSV 使用 UTF-8 BOM，避免 Excel 中文乱码。`,
    }),
  );

  const content = el("div", { class: "col", style: { gap: "12px" } }, notice, grid);
  const { close } = openModal({
    title,
    subtitle: subtitle || "选择一种格式，文件将直接下载到浏览器默认目录",
    content,
    footer: el("button", { class: "btn btn-ghost", type: "button", text: "取消", onclick: () => close() }),
  });

  return { close };
}
