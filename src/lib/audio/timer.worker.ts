// The scheduler's clock: a Worker keeps ticking when the tab is backgrounded
// (setInterval on the main thread is throttled to >= 1 s there).
let timer: ReturnType<typeof setInterval> | null = null;
let interval = 25;

self.onmessage = (e: MessageEvent<{ cmd: "start" | "stop"; interval?: number }>) => {
  const { cmd } = e.data;
  if (cmd === "start") {
    interval = e.data.interval ?? interval;
    if (timer) clearInterval(timer);
    timer = setInterval(() => self.postMessage("tick"), interval);
  } else if (cmd === "stop") {
    if (timer) clearInterval(timer);
    timer = null;
  }
};
