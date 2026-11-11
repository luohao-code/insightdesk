/**
 * 轻量 SVG 图表。
 * 不引入图表库，保持零依赖与离线可用。
 */

import { escapeHtml, formatNumber, relativeDayLabel } from "../utils.js";

/**
 * 绘制近 7 日趋势折线图。
 * @param {HTMLElement} container
 * @param {Array<{date: string, count: number}>} data
 */
export function renderTrendChart(container, data = []) {
  container.innerHTML = "";
  if (!data.length) {
    container.innerHTML = '<div class="empty" style="padding:32px"><p>暂无趋势数据</p></div>';
    return;
  }

  const width = 760;
  const height = 190;
  const padding = { top: 16, right: 16, bottom: 26, left: 32 };
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;
  const maxValue = Math.max(4, ...data.map((item) => item.count));
  const stepX = data.length > 1 ? innerWidth / (data.length - 1) : innerWidth;

  const points = data.map((item, index) => {
    const x = padding.left + index * stepX;
    const y = padding.top + innerHeight - (item.count / maxValue) * innerHeight;
    return { x, y, ...item };
  });

  const linePath = points.map((point, index) => `${index === 0 ? "M" : "L"}${point.x},${point.y}`).join(" ");
  const areaPath = `${linePath} L${points[points.length - 1].x},${padding.top + innerHeight} L${points[0].x},${padding.top + innerHeight} Z`;

  const gridLines = [0, 0.25, 0.5, 0.75, 1]
    .map((ratio) => {
      const y = padding.top + innerHeight * ratio;
      const value = Math.round(maxValue * (1 - ratio));
      return `
        <line class="grid-line" x1="${padding.left}" y1="${y}" x2="${width - padding.right}" y2="${y}" />
        <text class="axis-label" x="${padding.left - 8}" y="${y + 3}" text-anchor="end">${value}</text>
      `;
    })
    .join("");

  const labels = points
    .map(
      (point) => `
        <text class="axis-label" x="${point.x}" y="${height - 6}" text-anchor="middle">${escapeHtml(relativeDayLabel(point.date))}</text>
      `,
    )
    .join("");

  const dots = points
    .map(
      (point) => `
        <circle class="trend-dot" cx="${point.x}" cy="${point.y}" r="3.2">
          <title>${escapeHtml(point.date)}：${point.count} 条</title>
        </circle>
      `,
    )
    .join("");

  container.innerHTML = `
    <svg class="trend-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="近七日识别量趋势">
      <defs>
        <linearGradient id="trendGradient" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="rgba(99,102,241,0.35)" />
          <stop offset="100%" stop-color="rgba(99,102,241,0.02)" />
        </linearGradient>
      </defs>
      ${gridLines}
      <path class="trend-area" d="${areaPath}" />
      <path class="trend-line" d="${linePath}" />
      ${dots}
      ${labels}
    </svg>
  `;
}

/**
 * 引擎使用分布横向条形图。
 */
export function renderEngineBars(container, items = [], { emptyText = "暂无引擎使用数据" } = {}) {
  container.innerHTML = "";
  if (!items.length) {
    container.innerHTML = `<p class="text-xs muted" style="padding:8px 0">${escapeHtml(emptyText)}</p>`;
    return;
  }
  const max = Math.max(...items.map((item) => item.count), 1);
  const wrapper = document.createElement("div");
  wrapper.className = "engine-bars";

  const labelMap = {
    mock: "演示引擎",
    rapidocr: "RapidOCR",
    baidu: "百度 OCR",
    tencent: "腾讯 OCR",
    web: "网页提取",
  };

  for (const item of items.slice(0, 6)) {
    const row = document.createElement("div");
    row.className = "engine-bar-row";
    const name = labelMap[item.engine] || item.engine || "未知";
    row.innerHTML = `
      <span class="engine-bar-name" title="${escapeHtml(name)}">${escapeHtml(name)}</span>
      <span class="engine-bar-track"><span class="engine-bar-fill" style="width:${Math.max(4, (item.count / max) * 100)}%"></span></span>
      <span class="engine-bar-count">${formatNumber(item.count)}</span>
    `;
    wrapper.append(row);
  }
  container.append(wrapper);
}

/**
 * 环形图（用于来源分布）。
 * @param {HTMLElement} container
 * @param {Array<{label: string, value: number, color: string}>} segments
 */
export function renderDonut(container, segments = [], { centerLabel = "总计", centerValue = 0 } = {}) {
  const total = segments.reduce((sum, item) => sum + item.value, 0);
  if (!total) {
    container.innerHTML = '<p class="text-xs muted">暂无分布数据</p>';
    return;
  }

  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;
  const circles = segments
    .map((segment) => {
      const ratio = segment.value / total;
      const dash = ratio * circumference;
      const circle = `
        <circle cx="70" cy="70" r="${radius}" fill="none"
          stroke="${segment.color}" stroke-width="14"
          stroke-dasharray="${dash} ${circumference - dash}"
          stroke-dashoffset="${-offset}"
          transform="rotate(-90 70 70)" stroke-linecap="butt" />
      `;
      offset += dash;
      return circle;
    })
    .join("");

  const legend = segments
    .map(
      (segment) => `
      <div class="row" style="justify-content:space-between;font-size:10.5px;color:var(--muted)">
        <span class="row" style="gap:6px">
          <i style="width:8px;height:8px;border-radius:2px;background:${segment.color};display:inline-block"></i>
          ${escapeHtml(segment.label)}
        </span>
        <span>${formatNumber(segment.value)}</span>
      </div>
    `,
    )
    .join("");

  container.innerHTML = `
    <div class="row" style="gap:18px;align-items:center">
      <svg width="140" height="140" viewBox="0 0 140 140" aria-hidden="true">
        <circle cx="70" cy="70" r="${radius}" fill="none" stroke="var(--panel-3)" stroke-width="14" />
        ${circles}
        <text x="70" y="66" text-anchor="middle" fill="var(--text)" font-size="18" font-weight="700">${formatNumber(centerValue)}</text>
        <text x="70" y="82" text-anchor="middle" fill="var(--muted)" font-size="9">${escapeHtml(centerLabel)}</text>
      </svg>
      <div class="col" style="flex:1;gap:6px">${legend}</div>
    </div>
  `;
}

/** 迷你趋势线（用于统计卡片的背景装饰）。 */
export function sparkline(values = [], width = 90, height = 28) {
  if (!values.length) return "";
  const max = Math.max(...values, 1);
  const step = values.length > 1 ? width / (values.length - 1) : width;
  const path = values
    .map((value, index) => {
      const x = index * step;
      const y = height - (value / max) * height;
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return `<svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" fill="none" aria-hidden="true">
    <path d="${path}" stroke="var(--accent-strong)" stroke-width="1.8" stroke-linecap="round" opacity="0.7" />
  </svg>`;
}
