/// <reference lib="webworker" />
declare let self: ServiceWorkerGlobalScope;

// vite-plugin-pwa (injectManifest) requires this precache manifest injection
// point even though we don't do offline asset caching beyond the app shell.
import { precacheAndRoute } from "workbox-precaching";
precacheAndRoute(self.__WB_MANIFEST);

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

interface PushPayload {
  title: string;
  body: string;
  data?: { screen?: string; controller?: string };
}

// Handles a real Web Push message delivered while the app is closed/backgrounded.
self.addEventListener("push", (event: PushEvent) => {
  let payload: PushPayload = { title: "ATC Watch Beta", body: "" };
  try {
    if (event.data) payload = event.data.json();
  } catch {
    if (event.data) payload.body = event.data.text();
  }

  // `renotify` is a valid standard Notification option but missing from the
  // TS DOM lib's NotificationOptions type as of this toolchain; cast to keep
  // strict type-checking elsewhere while still setting it at runtime.
  const options = {
    body: payload.body,
    icon: "/icons/icon-192.png",
    badge: "/icons/icon-monochrome.png",
    tag: payload.data?.controller ?? "atc-watch-beta",
    renotify: true,
    data: payload.data ?? {},
    // iOS Safari (16.4+) supports Web Push including these standard options.
  } as NotificationOptions;

  event.waitUntil(self.registration.showNotification(payload.title, options));
});

// Navigates to (or focuses) the relevant screen when a notification is tapped.
self.addEventListener("notificationclick", (event: NotificationEvent) => {
  event.notification.close();
  const screen = (event.notification.data as PushPayload["data"])?.screen ?? "atc-ahead";
  const targetPath = screen === "settings" ? "/settings" : screen === "atc-ahead" ? "/atc" : `/${screen}`;

  event.waitUntil(
    (async () => {
      const allClients = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      const existing = allClients.find((c) => "focus" in c);
      if (existing) {
        await (existing as WindowClient).focus();
        existing.postMessage({ type: "navigate", path: targetPath });
      } else {
        await self.clients.openWindow(targetPath);
      }
    })(),
  );
});
