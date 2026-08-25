import { api } from "./api";

function urlBase64ToUint8Array(base64String: string): BufferSource {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  const buffer = new ArrayBuffer(rawData.length);
  const view = new Uint8Array(buffer);
  for (let i = 0; i < rawData.length; i++) view[i] = rawData.charCodeAt(i);
  return buffer;
}

export function isStandalonePwa(): boolean {
  // iOS Safari exposes navigator.standalone; other browsers use the display-mode media query.
  const iosStandalone = (navigator as unknown as { standalone?: boolean }).standalone === true;
  return iosStandalone || window.matchMedia("(display-mode: standalone)").matches;
}

export function isIos(): boolean {
  return /iphone|ipad|ipod/i.test(navigator.userAgent);
}

export function isAndroid(): boolean {
  return /android/i.test(navigator.userAgent);
}

export function pushSupported(): boolean {
  const hasApis = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
  if (!hasApis) return false;
  // iOS Safari (16.4+) reports these APIs as present even in a regular
  // browser tab, but Notification.requestPermission()/pushManager.subscribe()
  // only actually work once the page has been added to the Home Screen and
  // is running standalone. Outside that context, iOS silently blocks the
  // subscription instead of throwing something callers can act on cleanly —
  // so treat "iOS but not installed" as unsupported up front.
  if (isIos() && !isStandalonePwa()) return false;
  return true;
}

/**
 * Requests notification permission and creates a Web Push subscription.
 * MUST be called directly from a user gesture (e.g. an onClick handler) —
 * iOS Safari silently ignores Notification.requestPermission() calls that
 * aren't the direct result of a tap.
 */
export async function enableNotifications(): Promise<"granted" | "denied" | "unsupported"> {
  if (!pushSupported()) return "unsupported";

  const permission = await Notification.requestPermission();
  if (permission !== "granted") return "denied";

  const registration = await navigator.serviceWorker.ready;
  const { publicKey } = await api.vapidPublicKey();

  let subscription = await registration.pushManager.getSubscription();
  if (!subscription) {
    subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true, // required — every push must show a visible notification
      applicationServerKey: urlBase64ToUint8Array(publicKey),
    });
  }

  await api.subscribePush(subscription.toJSON() as PushSubscriptionJSON);
  return "granted";
}

export async function disableNotifications(): Promise<void> {
  if (!pushSupported()) return;
  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.getSubscription();
  if (subscription) {
    await api.unsubscribePush(subscription.endpoint);
    await subscription.unsubscribe();
  }
  await api.updateSettings({ notifications_enabled: false });
}

export async function registerServiceWorker(): Promise<void> {
  if (!("serviceWorker" in navigator)) return;
  await navigator.serviceWorker.register("/sw.js", { type: "module" });
}
