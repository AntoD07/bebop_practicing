// A small priority queue for engine requests: at most `concurrency` in flight,
// lowest priority number first; priorities can be raised while waiting (the
// selected row / the drill's current pair jump the line).
type Waiter = { key: string; priority: number; seq: number; resolve: () => void; signal?: AbortSignal };

export class PriorityQueue {
  private running = 0;
  private seq = 0;
  private waiting: Waiter[] = [];
  constructor(public concurrency = 4) {}

  get pending() {
    return this.waiting.length;
  }
  get active() {
    return this.running;
  }

  setPriority(key: string, priority: number) {
    for (const w of this.waiting) if (w.key === key) w.priority = priority;
  }

  acquire(key: string, priority: number, signal?: AbortSignal): Promise<() => void> {
    return new Promise((resolve, reject) => {
      const release = () => {
        this.running--;
        this.pump();
      };
      const w: Waiter = { key, priority, seq: this.seq++, signal, resolve: () => resolve(release) };
      if (signal) {
        if (signal.aborted) {
          reject(new DOMException("aborted", "AbortError"));
          return;
        }
        signal.addEventListener("abort", () => {
          const i = this.waiting.indexOf(w);
          if (i >= 0) {
            this.waiting.splice(i, 1);
            reject(new DOMException("aborted", "AbortError"));
          }
        }, { once: true });
      }
      this.waiting.push(w);
      this.pump();
    });
  }

  private pump() {
    while (this.running < this.concurrency && this.waiting.length) {
      this.waiting.sort((a, b) => a.priority - b.priority || a.seq - b.seq);
      const w = this.waiting.shift()!;
      this.running++;
      w.resolve();
    }
  }
}

export const engineQueue = new PriorityQueue(4);

export async function queued<T>(key: string, priority: number, fn: (signal?: AbortSignal) => Promise<T>, signal?: AbortSignal): Promise<T> {
  const release = await engineQueue.acquire(key, priority, signal);
  try {
    return await fn(signal);
  } finally {
    release();
  }
}
