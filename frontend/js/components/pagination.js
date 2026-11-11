/**
 * 分页组件。
 */

import { el } from "../utils.js";
import { icon } from "../icons.js";

export function renderPagination({
  page = 1,
  pageSize = 20,
  total = 0,
  onChange = null,
  compact = false,
} = {}) {
  const pages = Math.max(1, Math.ceil(total / Math.max(1, pageSize)));
  const root = el("div", { class: "pagination" });

  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);
  root.append(
    el("span", {
      class: "pagination-info",
      text: compact ? `${from}-${to} / ${total}` : `显示 ${from}–${to} 条，共 ${total} 条`,
    }),
  );

  const controls = el("div", { class: "pagination-controls" });

  const prev = el("button", {
    class: "page-btn",
    type: "button",
    "aria-label": "上一页",
    disabled: page <= 1,
    html: icon("chevronLeft", 14),
  });
  prev.addEventListener("click", () => onChange?.(page - 1));
  controls.append(prev);

  const windowSize = 5;
  let start = Math.max(1, page - Math.floor(windowSize / 2));
  const end = Math.min(pages, start + windowSize - 1);
  start = Math.max(1, end - windowSize + 1);

  if (start > 1) {
    controls.append(makeNumberButton(1));
    if (start > 2) controls.append(el("span", { class: "text-xs muted", text: "…" }));
  }

  for (let index = start; index <= end; index += 1) {
    controls.append(makeNumberButton(index));
  }

  if (end < pages) {
    if (end < pages - 1) controls.append(el("span", { class: "text-xs muted", text: "…" }));
    controls.append(makeNumberButton(pages));
  }

  const next = el("button", {
    class: "page-btn",
    type: "button",
    "aria-label": "下一页",
    disabled: page >= pages,
    html: icon("chevronRight", 14),
  });
  next.addEventListener("click", () => onChange?.(page + 1));
  controls.append(next);

  function makeNumberButton(index) {
    const button = el("button", {
      class: `page-btn${index === page ? " active" : ""}`,
      type: "button",
      text: String(index),
    });
    button.addEventListener("click", () => {
      if (index !== page) onChange?.(index);
    });
    return button;
  }

  root.append(controls);
  return root;
}
