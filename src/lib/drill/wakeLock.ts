// Keep the screen on while the drill runs (feature-detected; re-requested
// when the tab becomes visible again — the lock is released on hide).
let sentinel: WakeLockSentinel | null = null;
let wanted = false;

async function request() {
  if (!wanted || typeof navigator === "undefined" || !("wakeLock" in navigator)) return;
  try {
    if (sentinel && !sentinel.released) return;
    sentinel = await navigator.wakeLock.request("screen");
    sentinel.addEventListener("release", () => {
      sentinel = null;
    });
  } catch {
    sentinel = null;
  }
}

function onVisibility() {
  if (document.visibilityState === "visible") request();
}

export function acquireWakeLock() {
  if (wanted) return;
  wanted = true;
  document.addEventListener("visibilitychange", onVisibility);
  request();
}

export function releaseWakeLock() {
  wanted = false;
  document.removeEventListener("visibilitychange", onVisibility);
  const s = sentinel;
  sentinel = null;
  s?.release().catch(() => {});
}
