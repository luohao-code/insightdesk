/**
 * 图片上传组件。
 * 支持点击选择、拖拽、剪贴板粘贴、上传进度、缩略图管理与单选高亮。
 */

import { api } from "../api.js";
import { el, formatBytes, titleFromFilename } from "../utils.js";
import { icon } from "../icons.js";
import { toastError, toastInfo, toastSuccess, toastWarning } from "./toast.js";

const IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp", "image/bmp", "image/tiff", "image/gif"];

function isImage(file) {
  if (file.type && file.type.startsWith("image/")) return true;
  return /\.(png|jpe?g|webp|bmp|tiff?|gif)$/i.test(file.name || "");
}

export function createUploader({
  multiple = true,
  maxFiles = 100,
  onUploaded = null,
  onChange = null,
  onSelect = null,
  title = "拖拽图片到这里，或点击选择",
  subtitle = "支持 PNG / JPG / WEBP / BMP / TIFF，也可直接粘贴截图",
  compact = false,
} = {}) {
  const images = [];
  let uploading = false;
  let activeId = null;

  const input = el("input", {
    type: "file",
    class: "file-input",
    accept: "image/*",
    multiple,
  });

  const dropzone = el(
    "div",
    { class: "dropzone", role: "button", tabindex: "0", "aria-label": "上传图片" },
    el("div", { class: "dropzone-icon", html: icon("upload", compact ? 20 : 24) }),
    el("strong", { text: title }),
    el("span", { text: subtitle }),
    compact
      ? null
      : el("span", {
          class: "dropzone-hint text-xs muted",
          html: `也可以按 <kbd>Ctrl</kbd> + <kbd>V</kbd> 粘贴剪贴板截图`,
        }),
    input,
  );

  const progressBar = el("div", { class: "progress-bar striped", style: { width: "0%" } });
  const progressText = el("span", { class: "text-xs muted", text: "准备上传…" });
  const progressWrap = el(
    "div",
    { class: "upload-progress col", hidden: true, style: { gap: "6px" } },
    el("div", { class: "progress" }, progressBar),
    progressText,
  );

  const grid = el("div", { class: "thumb-grid", hidden: true });
  const root = el("div", { class: "col", style: { gap: "12px" } }, dropzone, progressWrap, grid);

  function notifyChange() {
    onChange?.(images.slice());
  }

  function setActive(id) {
    activeId = id;
    grid.querySelectorAll(".thumb-card").forEach((card) => {
      card.classList.toggle("active", card.dataset.id === id);
    });
  }

  function render() {
    grid.innerHTML = "";
    grid.hidden = images.length === 0;
    for (const image of images) {
      const card = el(
        "div",
        {
          class: `thumb-card${image.id === activeId ? " active" : ""}`,
          dataset: { id: image.id },
          title: image.filename,
        },
        el("img", {
          class: "thumb-img",
          src: image.thumbnail_url || image.url,
          alt: image.filename,
          loading: "lazy",
        }),
        el("span", { class: "thumb-remove", html: icon("x", 12), title: "移除" }),
        el(
          "div",
          { class: "thumb-meta" },
          el("div", { class: "thumb-name", text: image.filename }),
          el("div", {
            class: "thumb-sub",
            text: `${image.width}×${image.height} · ${formatBytes(image.size_bytes)}`,
          }),
        ),
      );

      card.addEventListener("click", (event) => {
        if (event.target.closest(".thumb-remove")) return;
        setActive(image.id);
        onSelect?.(image, images.indexOf(image));
      });

      card.querySelector(".thumb-remove").addEventListener("click", (event) => {
        event.stopPropagation();
        const index = images.findIndex((item) => item.id === image.id);
        if (index >= 0) images.splice(index, 1);
        if (activeId === image.id) activeId = null;
        render();
        notifyChange();
      });

      grid.append(card);
    }
  }

  function validateFiles(fileList) {
    const accepted = [];
    const rejected = [];
    for (const file of fileList) {
      if (!isImage(file)) {
        rejected.push(`${file.name}：不是图片文件`);
        continue;
      }
      if (file.size > 20 * 1024 * 1024) {
        rejected.push(`${file.name}：超过 20MB`);
        continue;
      }
      accepted.push(file);
    }
    return { accepted, rejected };
  }

  async function uploadFiles(fileList) {
    if (uploading) return;
    const list = Array.from(fileList || []);
    if (!list.length) return;

    const { accepted, rejected } = validateFiles(list);
    if (rejected.length) toastWarning("部分文件已跳过", rejected.slice(0, 3).join("；"));

    const remaining = Math.max(0, maxFiles - images.length);
    const files = accepted.slice(0, remaining);
    if (accepted.length > remaining) {
      toastWarning("超出数量限制", `最多 ${maxFiles} 张，本次仅上传前 ${remaining} 张`);
    }
    if (!files.length) {
      if (!rejected.length) toastWarning("无法继续上传", `最多只能添加 ${maxFiles} 张图片`);
      return;
    }

    uploading = true;
    input.value = "";
    progressWrap.hidden = false;
    progressBar.style.width = "4%";
    progressText.textContent = `正在上传 ${files.length} 张图片…`;

    try {
      const result = await api.upload(files, {
        onProgress: (percent) => {
          progressBar.style.width = `${percent}%`;
          progressText.textContent = percent >= 100 ? "服务端处理中…" : `上传中 ${percent}%`;
        },
      });
      const uploaded = result?.images || [];
      images.push(...uploaded);
      render();
      if (uploaded.length) {
        setActive(uploaded[uploaded.length - 1].id);
        onUploaded?.(uploaded, images.slice());
        notifyChange();
        toastSuccess(
          "图片已就绪",
          `成功上传 ${uploaded.length} 张${result?.rejected?.length ? `，${result.rejected.length} 张被拒绝` : ""}`,
        );
      }
      if (result?.rejected?.length) {
        toastWarning(
          "部分图片被拒绝",
          result.rejected
            .slice(0, 2)
            .map((item) => `${item.filename}：${item.reason}`)
            .join("；"),
        );
      }
    } catch (error) {
      toastError("上传失败", error.message || String(error));
    } finally {
      uploading = false;
      setTimeout(() => {
        progressWrap.hidden = true;
        progressBar.style.width = "0%";
      }, 500);
    }
  }

  function onPaste(event) {
    if (!root.isConnected) return;
    const items = Array.from(event.clipboardData?.items || []);
    const files = items.filter((item) => item.kind === "file").map((item) => item.getAsFile()).filter(Boolean);
    if (!files.length) return;
    const imageFiles = files.filter(isImage);
    if (!imageFiles.length) return;
    event.preventDefault();
    toastInfo("检测到剪贴板图片", `正在上传 ${imageFiles.length} 张…`);
    uploadFiles(imageFiles);
  }

  dropzone.addEventListener("click", () => {
    if (!uploading) input.click();
  });
  dropzone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (!uploading) input.click();
    }
  });
  input.addEventListener("change", () => uploadFiles(input.files));

  for (const name of ["dragenter", "dragover"]) {
    dropzone.addEventListener(name, (event) => {
      event.preventDefault();
      event.stopPropagation();
      dropzone.classList.add("is-dragover");
    });
  }
  for (const name of ["dragleave", "dragend"]) {
    dropzone.addEventListener(name, (event) => {
      event.preventDefault();
      event.stopPropagation();
      dropzone.classList.remove("is-dragover");
    });
  }
  dropzone.addEventListener("drop", (event) => {
    event.preventDefault();
    event.stopPropagation();
    dropzone.classList.remove("is-dragover");
    uploadFiles(event.dataTransfer?.files);
  });
  document.addEventListener("paste", onPaste);

  return {
    element: root,
    dropzone,
    input,
    getImages: () => images.slice(),
    getActiveId: () => activeId,
    setActive,
    setImages(next) {
      images.length = 0;
      images.push(...(next || []));
      render();
      notifyChange();
    },
    clear() {
      images.length = 0;
      activeId = null;
      render();
      notifyChange();
    },
    focus() {
      dropzone.focus();
    },
    setDisabled(value) {
      uploading = value;
      dropzone.style.pointerEvents = value ? "none" : "";
      dropzone.style.opacity = value ? "0.6" : "";
    },
    destroy() {
      document.removeEventListener("paste", onPaste);
      root.remove();
    },
    imageTitle: titleFromFilename,
  };
}
