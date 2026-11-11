/**
 * 哈希路由。
 * 使用 #/route?param=value，避免服务器端 SPA 回退配置。
 */

import { $, $$ } from "./utils.js";
import { state, setState } from "./store.js";
import { t } from "./i18n.js";

const routes = new Map();
let current = null;
let cleanup = null;
let rendering = false;

export function register(name, config) {
  routes.set(name, config);
}

export function parseHash() {
  const raw = (window.location.hash || "#/dashboard").replace(/^#\/?/, "");
  const [path, queryString] = raw.split("?");
  const name = (path || "dashboard").split("/")[0];
  const params = {};
  if (queryString) {
    new URLSearchParams(queryString).forEach((value, key) => {
      params[key] = value;
    });
  }
  return { name: routes.has(name) ? name : "dashboard", params };
}

export function navigate(name, params = {}, { replace = false } = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== "") query.set(key, String(value));
  }
  const suffix = query.toString() ? `?${query}` : "";
  const hash = `#/${name}${suffix}`;
  if (replace) {
    window.history.replaceState(null, "", hash);
    render();
  } else if (window.location.hash === hash) {
    render();
  } else {
    window.location.hash = hash;
  }
}

export function currentRoute() {
  return current;
}

export async function render() {
  if (rendering) return;
  const { name, params } = parseHash();
  const route = routes.get(name);
  if (!route) return;

  rendering = true;
  const view = $("#view");
  try {
    if (typeof cleanup === "function") {
      try {
        cleanup();
      } catch (error) {
        console.warn("页面卸载异常", error);
      }
    }
    cleanup = null;

    current = { name, params, config: route };
    setState({ route: name });
    updateChrome(name, route, params);

    view.innerHTML = "";
    view.scrollTop = 0;

    const result = await route.render(view, params);
    if (result && typeof result.destroy === "function") cleanup = result.destroy;
  } catch (error) {
    console.error("页面渲染失败", error);
    view.innerHTML = `
      <div class="page">
        <div class="card">
          <div class="empty">
            <div class="empty-icon">
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round">
                <path d="M12 3 2.8 20h18.4L12 3Z"/><path d="M12 9v4M12 16.5h.01"/>
              </svg>
            </div>
            <strong>页面加载失败</strong>
            <p>${String(error.message || error)}</p>
            <button class="btn btn-secondary btn-sm" id="route-retry">重新加载</button>
          </div>
        </div>
      </div>
    `;
    $("#route-retry")?.addEventListener("click", () => render());
  } finally {
    rendering = false;
  }
}

function updateChrome(name, route, params) {
  const titleKey = route.titleKey || `page.${name}.title`;
  const subtitleKey = route.subtitleKey || `page.${name}.subtitle`;
  const title = typeof route.title === "function" ? route.title(params) : t(titleKey);
  const subtitle = typeof route.subtitle === "function" ? route.subtitle(params) : t(subtitleKey);

  const titleNode = $("#page-title");
  const subtitleNode = $("#page-subtitle");
  if (titleNode) titleNode.textContent = title;
  if (subtitleNode) subtitleNode.textContent = subtitle;
  document.title = `${title} · 识文台 InsightDesk`;

  $$(".nav-item").forEach((item) => {
    const active = item.dataset.route === name;
    item.classList.toggle("active", active);
    if (active) item.setAttribute("aria-current", "page");
    else item.removeAttribute("aria-current");
  });
}

export function initRouter() {
  window.addEventListener("hashchange", () => render());
  window.addEventListener("language-changed", () => render());
  if (!window.location.hash) {
    window.history.replaceState(null, "", "#/dashboard");
  }
  render();
}

export function routeNames() {
  return Array.from(routes.keys());
}

export function routeMeta(name) {
  return routes.get(name);
}

export function reload() {
  return render();
}

export function isRendering() {
  return rendering;
}

export function openRoute(name, params) {
  navigate(name, params || {});
}

export function linkTo(name, params) {
  const query = new URLSearchParams(params || {}).toString();
  return `#/${name}${query ? `?${query}` : ""}`;
}

export function highlightNav(name) {
  $$(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.route === name));
}

export function getState() {
  return state;
}
