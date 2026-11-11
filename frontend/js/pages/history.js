/**
 * 历史记录页。
 * 支持全文检索、筛选、批量操作、详情编辑与多格式导出。
 */

import { api } from "../api.js";
import { debounce, el, formatDate, formatNumber, timeAgo, truncate } from "../utils.js";
import { icon } from "../icons.js";
import { navigate } from "../router.js";
import { openModal, confirmDialog } from "../components/modal.js";
import { renderPagination } from "../components/pagination.js";
import { openExportDialog } from "../components/exportDialog.js";
import { toastError, toastSuccess } from "../components/toast.js";

const SOURCE_LABELS = {
  image: "图片识别",
  web: "网页提取",
  manual: "手动创建",
  ai: "AI 生成",
};

export async function render(container, params = {}) {
  const page = el("div", { class: "page" });
  page.innerHTML = `
    <div class="page-header">
      <div>
        <h2>${icon("archive", 20)} 历史记录</h2>
        <p>所有识别与提取结果保存在本机 SQLite 中。支持关键词全文检索、按来源/引擎筛选、批量导出与删除。</p>
      </div>
      <div class="page-actions">
        <button class="btn btn-ghost btn-sm" type="button" id="history-refresh">${icon("refresh", 14)}刷新</button>
        <button class="btn btn-ghost btn-sm" type="button" data-go="ocr">${icon("scan", 14)}去识别</button>
      </div>
    </div>

    <section class="card">
      <div class="card-body" style="padding:14px 16px">
        <div class="history-filters">
          <div class="toolbar-search" style="min-width:260px">
            ${icon("search", 15)}
            <input class="input" id="history-search" placeholder="搜索标题、正文或标签…" autocomplete="off" />
          </div>
          <select class="select" id="filter-source">
            <option value="">全部来源</option>
            <option value="image">图片识别</option>
            <option value="web">网页提取</option>
            <option value="manual">手动创建</option>
          </select>
          <select class="select" id="filter-engine">
            <option value="">全部引擎</option>
          </select>
          <select class="select" id="filter-sort">
            <option value="updated_desc">最近更新</option>
            <option value="created_desc">最近创建</option>
            <option value="created_asc">最早创建</option>
            <option value="chars_desc">字数最多</option>
            <option value="title_asc">标题排序</option>
          </select>
          <label class="chip" id="filter-favorite">${icon("star", 13)}<span>只看收藏</span></label>
          <span class="spacer"></span>
          <span class="text-xs muted" id="history-took"></span>
        </div>
        <div class="filter-chip-bar" id="tag-bar" style="margin-top:10px"></div>
      </div>
      <div class="bulk-bar" id="bulk-bar" hidden>
        <span>已选择 <strong id="bulk-count">0</strong> 条</span>
        <span class="spacer"></span>
        <button class="btn btn-secondary btn-sm" type="button" id="bulk-export">${icon("download", 13)}导出</button>
        <button class="btn btn-danger btn-sm" type="button" id="bulk-delete">${icon("trash", 13)}删除</button>
        <button class="btn btn-ghost btn-sm" type="button" id="bulk-clear">取消选择</button>
      </div>
      <div class="table-wrap" id="history-table-wrap"></div>
      <div class="card-body" id="history-pagination" style="padding-top:6px"></div>
    </section>
  `;
  container.append(page);

  page.querySelectorAll("[data-go]").forEach((button) => {
    button.addEventListener("click", () => navigate(button.dataset.go));
  });

  const state = {
    q: params.q || "",
    source: "",
    engine: "",
    favorite: false,
    tag: "",
    sort: "updated_desc",
    page: 1,
    pageSize: 12,
    selected: new Set(),
    documents: [],
    total: 0,
    pages: 0,
  };

  const searchInput = page.querySelector("#history-search");
  const sourceSelect = page.querySelector("#filter-source");
  const engineSelect = page.querySelector("#filter-engine");
  const sortSelect = page.querySelector("#filter-sort");
  const favoriteChip = page.querySelector("#filter-favorite");
  const tableWrap = page.querySelector("#history-table-wrap");
  const paginationWrap = page.querySelector("#history-pagination");
  const tagBar = page.querySelector("#tag-bar");
  const bulkBar = page.querySelector("#bulk-bar");
  const bulkCount = page.querySelector("#bulk-count");

  searchInput.value = state.q;

  const debouncedSearch = debounce(() => {
    state.q = searchInput.value.trim();
    state.page = 1;
    load();
  }, 320);

  searchInput.addEventListener("input", debouncedSearch);
  sourceSelect.addEventListener("change", () => {
    state.source = sourceSelect.value;
    state.page = 1;
    load();
  });
  engineSelect.addEventListener("change", () => {
    state.engine = engineSelect.value;
    state.page = 1;
    load();
  });
  sortSelect.addEventListener("change", () => {
    state.sort = sortSelect.value;
    state.page = 1;
    load();
  });
  favoriteChip.addEventListener("click", () => {
    state.favorite = !state.favorite;
    favoriteChip.classList.toggle("active", state.favorite);
    state.page = 1;
    load();
  });

  async function loadTags() {
    try {
      const result = await api.historyTags();
      tagBar.innerHTML = "";
      if (!result.items?.length) return;
      const all = el("button", { class: `chip${state.tag ? "" : " active"}`, type: "button", text: "全部标签" });
      all.addEventListener("click", () => {
        state.tag = "";
        state.page = 1;
        load();
        loadTags();
      });
      tagBar.append(all);
      for (const item of result.items.slice(0, 12)) {
        const chip = el("button", {
          class: `chip${state.tag === item.tag ? " active" : ""}`,
          type: "button",
          text: `${item.tag} (${item.count})`,
        });
        chip.addEventListener("click", () => {
          state.tag = state.tag === item.tag ? "" : item.tag;
          state.page = 1;
          load();
          loadTags();
        });
        tagBar.append(chip);
      }
    } catch {
      /* 标签为增强信息，不阻断主流程 */
    }
  }

  async function loadEngines() {
    try {
      const stats = await api.historyStats();
      const engines = Object.keys(stats.engines || {});
      engineSelect.innerHTML = '<option value="">全部引擎</option>';
      for (const name of engines) {
        engineSelect.append(el("option", { value: name, text: name }));
      }
      engineSelect.value = state.engine;
    } catch {
      /* ignore */
    }
  }

  function syncBulkBar() {
    const count = state.selected.size;
    bulkBar.hidden = count === 0;
    bulkCount.textContent = String(count);
  }

  function clearSelection() {
    state.selected.clear();
    document.querySelectorAll("#history-table-wrap .row-checkbox").forEach((input) => {
      input.checked = false;
    });
    syncBulkBar();
  }

  async function load() {
    tableWrap.innerHTML = `
      <div style="padding:24px">
        <div class="skeleton skeleton-title"></div>
        <div class="skeleton skeleton-text"></div>
        <div class="skeleton skeleton-text" style="width:70%"></div>
      </div>`;
    try {
      const result = await api.history({
        q: state.q || undefined,
        source_type: state.source || undefined,
        engine: state.engine || undefined,
        favorite: state.favorite || undefined,
        tag: state.tag || undefined,
        sort: state.sort,
        page: state.page,
        page_size: state.pageSize,
      });
      state.documents = result.items || [];
      state.total = result.total || 0;
      state.pages = result.pages || 0;
      page.querySelector("#history-took").textContent = `检索耗时 ${result.took_ms} ms`;
      clearSelection();
      renderTable();
      renderPager();
    } catch (error) {
      tableWrap.innerHTML = "";
      tableWrap.append(
        el(
          "div",
          { class: "empty" },
          el("div", { class: "empty-icon", html: icon("alert", 22) }),
          el("strong", { text: "加载失败" }),
          el("p", { text: error.message || String(error) }),
          el("button", {
            class: "btn btn-secondary btn-sm",
            type: "button",
            text: "重试",
            onclick: () => load(),
          }),
        ),
      );
      toastError("历史记录加载失败", error.message || String(error));
    }
  }

  function renderTable() {
    tableWrap.innerHTML = "";
    if (!state.documents.length) {
      tableWrap.innerHTML = `
        <div class="empty">
          <div class="empty-icon">${icon("inbox", 24)}</div>
          <strong>${state.q ? "没有匹配的记录" : "还没有文字资产"}</strong>
          <p>${state.q ? "试试更短的关键词，或清除筛选条件。" : "完成一次图片识别或网页提取后，记录会自动保存到这里。"}</p>
          <button class="btn btn-primary btn-sm" type="button" data-empty-ocr>开始识别</button>
        </div>`;
      tableWrap.querySelector("[data-empty-ocr]")?.addEventListener("click", () => navigate("ocr"));
      return;
    }

    const table = el("table", { class: "table" });
    const thead = el("thead");
    const headRow = el("tr");
    const selectAll = el("input", { class: "row-checkbox", type: "checkbox", "aria-label": "全选当前页" });
    selectAll.addEventListener("change", () => {
      for (const doc of state.documents) {
        if (selectAll.checked) state.selected.add(doc.id);
        else state.selected.delete(doc.id);
      }
      tableWrap.querySelectorAll("tbody .row-checkbox").forEach((input) => {
        input.checked = selectAll.checked;
      });
      syncBulkBar();
    });
    headRow.append(
      el("th", { style: { width: "38px" } }, selectAll),
      el("th", { text: "标题" }),
      el("th", { text: "来源" }),
      el("th", { text: "引擎" }),
      el("th", { text: "字数" }),
      el("th", { text: "更新时间" }),
      el("th", { text: "操作", style: { textAlign: "right" } }),
    );
    thead.append(headRow);
    table.append(thead);

    const tbody = el("tbody");
    for (const doc of state.documents) {
      const row = el("tr", { dataset: { id: String(doc.id) } });
      const checkbox = el("input", {
        class: "row-checkbox",
        type: "checkbox",
        "aria-label": `选择 ${doc.title}`,
        checked: state.selected.has(doc.id),
      });
      checkbox.addEventListener("change", () => {
        if (checkbox.checked) state.selected.add(doc.id);
        else state.selected.delete(doc.id);
        row.classList.toggle("selected", checkbox.checked);
        syncBulkBar();
      });

      const titleCell = el(
        "td",
        {},
        el(
          "div",
          { class: "table-title" },
          el("span", { html: icon(doc.source_type === "web" ? "globe" : "fileText", 14) }),
          el("span", { class: "title-text", text: doc.title || "未命名文档", title: doc.title }),
        ),
        el(
          "div",
          { class: "row", style: { gap: "5px", marginTop: "3px" } },
          doc.tags?.slice(0, 3).map((tag) => el("span", { class: "tag", text: tag })),
          doc.excerpt
            ? el("span", { class: "text-xs muted truncate", style: { maxWidth: "260px" }, text: truncate(doc.excerpt, 60) })
            : null,
        ),
      );

      const sourceCell = el(
        "td",
        {},
        el("span", { class: "pill pill-soft", text: SOURCE_LABELS[doc.source_type] || doc.source_type }),
      );

      const engineCell = el("td", {}, el("span", { class: "mono text-xs", text: doc.engine || "—" }));

      const charsCell = el("td", {}, el("span", { class: "mono text-xs", text: formatNumber(doc.char_count) }));

      const timeCell = el(
        "td",
        {},
        el("span", { class: "text-xs", text: timeAgo(doc.updated_at), title: formatDate(doc.updated_at) }),
      );

      const actions = el(
        "td",
        {},
        el(
          "div",
          { class: "table-actions" },
          el("button", {
            class: "icon-btn",
            type: "button",
            title: doc.favorite ? "取消收藏" : "收藏",
            style: doc.favorite ? { color: "var(--amber)" } : {},
            html: icon("star", 15),
            onclick: async (event) => {
              event.stopPropagation();
              try {
                await api.updateDocument(doc.id, { favorite: !doc.favorite });
                doc.favorite = !doc.favorite;
                event.currentTarget.style.color = doc.favorite ? "var(--amber)" : "";
                toastSuccess(doc.favorite ? "已收藏" : "已取消收藏", doc.title);
              } catch (error) {
                toastError("操作失败", error.message || String(error));
              }
            },
          }),
          el("button", {
            class: "icon-btn",
            type: "button",
            title: "查看",
            html: icon("eye", 15),
            onclick: (event) => {
              event.stopPropagation();
              openDetail(doc.id);
            },
          }),
          el("button", {
            class: "icon-btn",
            type: "button",
            title: "导出",
            html: icon("download", 15),
            onclick: (event) => {
              event.stopPropagation();
              openExportDialog([doc.id], { title: "导出记录" });
            },
          }),
          el("button", {
            class: "icon-btn",
            type: "button",
            title: "删除",
            html: icon("trash", 15),
            onclick: async (event) => {
              event.stopPropagation();
              const confirmed = await confirmDialog({
                title: "删除这条记录？",
                message: `「${doc.title}」的原图、缩略图与正文都会被删除，且无法恢复。`,
                confirmText: "删除",
                danger: true,
              });
              if (!confirmed) return;
              try {
                await api.deleteDocument(doc.id);
                toastSuccess("已删除", doc.title);
                load();
                loadTags();
              } catch (error) {
                toastError("删除失败", error.message || String(error));
              }
            },
          }),
        ),
      );

      row.append(el("td", {}, checkbox), titleCell, sourceCell, engineCell, charsCell, timeCell, actions);
      row.addEventListener("dblclick", () => openDetail(doc.id));
      tbody.append(row);
    }
    table.append(tbody);
    tableWrap.append(table);
  }

  function renderPager() {
    paginationWrap.innerHTML = "";
    paginationWrap.append(
      renderPagination({
        page: state.page,
        pageSize: state.pageSize,
        total: state.total,
        onChange: (next) => {
          state.page = Math.max(1, Math.min(state.pages || 1, next));
          load();
          window.scrollTo({ top: 0, behavior: "smooth" });
        },
      }),
    );
  }

  /* ------------------------------------------------------------------ */
  /* 详情弹窗                                                            */
  /* ------------------------------------------------------------------ */

  async function openDetail(id) {
    let doc;
    try {
      doc = await api.document(id);
    } catch (error) {
      toastError("记录加载失败", error.message || String(error));
      return;
    }

    const titleInput = el("input", { class: "input", value: doc.title || "", maxLength: 120 });
    const contentArea = el("textarea", { class: "textarea", style: { minHeight: "300px", fontFamily: "var(--font-sans)", lineHeight: "1.8" } });
    contentArea.value = doc.content || "";
    const tags = [...(doc.tags || [])];
    const tagBox = el("div", { class: "tag-editor" });
    const tagInput = el("input", { class: "input input-sm", placeholder: "添加标签后回车", style: { width: "150px" } });
    const favoriteToggle = el("input", { type: "checkbox", checked: Boolean(doc.favorite) });

    function renderTags() {
      tagBox.innerHTML = "";
      for (const tag of tags) {
        const chip = el(
          "span",
          { class: "chip active" },
          `#${tag}`,
          el("span", {
            class: "chip-remove",
            text: "×",
            onclick: () => {
              const index = tags.indexOf(tag);
              if (index >= 0) tags.splice(index, 1);
              renderTags();
            },
          }),
        );
        tagBox.append(chip);
      }
      tagBox.append(tagInput);
    }
    renderTags();

    tagInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        const value = tagInput.value.trim().replace(/^#/, "");
        if (value && !tags.includes(value) && tags.length < 20) {
          tags.push(value.slice(0, 24));
          tagInput.value = "";
          renderTags();
          tagInput.focus();
        }
      }
    });

    const meta = el(
      "div",
      { class: "meta-grid" },
      metaItem("来源", SOURCE_LABELS[doc.source_type] || doc.source_type),
      metaItem("识别引擎", doc.engine || "—"),
      metaItem("字数", formatNumber(doc.char_count)),
      metaItem("置信度", doc.confidence ? `${(doc.confidence * 100).toFixed(1)}%` : "—"),
      metaItem("创建时间", formatDate(doc.created_at)),
      metaItem("更新时间", formatDate(doc.updated_at)),
    );

    const header = el(
      "div",
      { class: "doc-detail-head" },
      doc.thumbnail_url
        ? el("img", { class: "doc-detail-thumb", src: doc.thumbnail_url, alt: doc.title })
        : el("div", { class: "doc-detail-thumb", style: { display: "grid", placeItems: "center", color: "var(--muted)" }, html: icon(doc.source_type === "web" ? "globe" : "fileText", 30) }),
      el(
        "div",
        { class: "doc-detail-meta" },
        meta,
        doc.source_url
          ? el("a", { href: doc.source_url, target: "_blank", rel: "noopener noreferrer", class: "text-xs", text: truncate(doc.source_url, 80) })
          : null,
      ),
    );

    const body = el(
      "div",
      { class: "col", style: { gap: "14px" } },
      header,
      el("div", { class: "field" }, el("label", { class: "field-label", text: "标题" }), titleInput),
      el("div", { class: "field" }, el("label", { class: "field-label", text: "标签" }), tagBox),
      el("div", { class: "field" }, el("label", { class: "field-label", text: "正文" }), contentArea),
      el("div", { class: "row", style: { gap: "8px" } },
        el("label", { class: "switch" }, favoriteToggle, el("span", { class: "track" }), el("span", { class: "text-sm muted", text: "收藏这条记录" })),
        el("span", { class: "spacer" }),
        doc.source_type === "web" && doc.source_url
          ? el("button", {
              class: "btn btn-ghost btn-sm",
              type: "button",
              html: `${icon("external", 13)}打开原文`,
              onclick: () => window.open(doc.source_url, "_blank", "noopener,noreferrer"),
            })
          : null,
      ),
    );

    const footer = el(
      "div",
      { class: "row", style: { width: "100%", justifyContent: "space-between" } },
      el(
        "div",
        { class: "row", style: { gap: "6px" } },
        el("button", {
          class: "btn btn-ghost btn-sm",
          type: "button",
          html: `${icon("download", 13)}导出`,
          onclick: () => openExportDialog([doc.id], { title: "导出记录" }),
        }),
        el("button", {
          class: "btn btn-ghost btn-sm",
          type: "button",
          html: `${icon("trash", 13)}删除`,
          onclick: async () => {
            const confirmed = await confirmDialog({
              title: "删除这条记录？",
              message: "删除后无法恢复。",
              confirmText: "删除",
              danger: true,
            });
            if (!confirmed) return;
            try {
              await api.deleteDocument(doc.id);
              close();
              toastSuccess("已删除", doc.title);
              load();
              loadTags();
            } catch (error) {
              toastError("删除失败", error.message || String(error));
            }
          },
        }),
      ),
      el(
        "div",
        { class: "row", style: { gap: "6px" } },
        el("button", { class: "btn btn-ghost", type: "button", text: "关闭", onclick: () => close() }),
        el("button", {
          class: "btn btn-primary",
          type: "button",
          text: "保存修改",
          onclick: async (event) => {
            const button = event.currentTarget;
            button.disabled = true;
            button.textContent = "保存中…";
            try {
              await api.updateDocument(doc.id, {
                title: titleInput.value.trim() || doc.title,
                content: contentArea.value,
                tags,
                favorite: favoriteToggle.checked,
              });
              toastSuccess("已保存", "标题、正文与标签已更新");
              close();
              load();
              loadTags();
            } catch (error) {
              toastError("保存失败", error.message || String(error));
              button.disabled = false;
              button.textContent = "保存修改";
            }
          },
        }),
      ),
    );

    const { close } = openModal({
      title: doc.title || "记录详情",
      subtitle: `ID ${doc.id} · ${SOURCE_LABELS[doc.source_type] || doc.source_type}`,
      content: body,
      footer,
      size: "lg",
    });
  }

  function metaItem(label, value) {
    return el(
      "div",
      { class: "meta-item" },
      el("div", { class: "meta-label", text: label }),
      el("div", { class: "meta-value", text: value }),
    );
  }

  /* ------------------------------------------------------------------ */
  /* 批量操作                                                            */
  /* ------------------------------------------------------------------ */

  page.querySelector("#bulk-export").addEventListener("click", () => {
    const ids = Array.from(state.selected);
    if (!ids.length) return;
    openExportDialog(ids, { title: `批量导出 ${ids.length} 条记录` });
  });

  page.querySelector("#bulk-delete").addEventListener("click", async () => {
    const ids = Array.from(state.selected);
    if (!ids.length) return;
    const confirmed = await confirmDialog({
      title: `删除 ${ids.length} 条记录？`,
      message: "这些记录的原图、缩略图与正文都会被删除，且无法恢复。",
      confirmText: "批量删除",
      danger: true,
    });
    if (!confirmed) return;
    try {
      const result = await api.bulkDelete(ids);
      toastSuccess("已删除", `共删除 ${result.deleted} 条记录`);
      clearSelection();
      load();
      loadTags();
    } catch (error) {
      toastError("批量删除失败", error.message || String(error));
    }
  });

  page.querySelector("#bulk-clear").addEventListener("click", clearSelection);

  page.querySelector("#history-refresh").addEventListener("click", () => {
    load();
    loadTags();
    loadEngines();
    toastSuccess("已刷新", "历史记录已更新");
  });

  await load();
  await Promise.all([loadTags(), loadEngines()]);

  if (params.doc) {
    const id = Number(params.doc);
    if (Number.isFinite(id)) {
      setTimeout(() => openDetail(id), 260);
    }
  }
}
