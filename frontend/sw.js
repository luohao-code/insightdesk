/**
 * Service Worker：为前端静态资源提供离线壳。
 * 策略：网络优先，失败时回退缓存；API 请求不缓存。
 */

const CACHE_NAME = "insightdesk-shell-v2";

const PRECACHE = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./assets/favicon.svg",
  "./css/tokens.css",
  "./css/base.css",
  "./css/layout.css",
  "./css/components.css",
  "./css/pages.css",
  "./css/animations.css",
  "./js/app.js",
  "./js/api.js",
  "./js/router.js",
  "./js/store.js",
  "./js/utils.js",
  "./js/icons.js",
  "./js/i18n.js",
  "./js/config.js",
  "./js/components/toast.js",
  "./js/components/modal.js",
  "./js/components/chart.js",
  "./js/components/uploader.js",
  "./js/components/editor.js",
  "./js/components/pagination.js",
  "./js/components/commandPalette.js",
  "./js/components/exportDialog.js",
  "./js/pages/dashboard.js",
  "./js/pages/ocr.js",
  "./js/pages/batch.js",
  "./js/pages/ai.js",
  "./js/pages/history.js",
  "./js/pages/web.js",
  "./js/pages/settings.js",
  "./js/pages/help.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(async (cache) => {
      await Promise.allSettled(PRECACHE.map((url) => cache.add(url)));
      await self.skipWaiting();
    }),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) return;

  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
        }
        return response;
      })
      .catch(async () => {
        const cached = await caches.match(request);
        if (cached) return cached;
        if (request.mode === "navigate") {
          const shell = await caches.match("./index.html");
          if (shell) return shell;
        }
        return new Response("离线状态下无法加载该资源", {
          status: 503,
          headers: { "Content-Type": "text/plain; charset=utf-8" },
        });
      }),
  );
});
