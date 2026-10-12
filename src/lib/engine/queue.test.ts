import { describe, expect, it } from "vitest";
import { PriorityQueue } from "./queue";

describe("PriorityQueue", () => {
  it("runs lowest priority first with bounded concurrency", async () => {
    const q = new PriorityQueue(2);
    const order: string[] = [];
    const releases: (() => void)[] = [];
    // fill both slots
    releases.push(await q.acquire("a", 5));
    releases.push(await q.acquire("b", 5));
    const c = q.acquire("c", 9).then((r) => { order.push("c"); r(); });
    const d = q.acquire("d", 1).then((r) => { order.push("d"); r(); });
    q.setPriority("c", 0);
    expect(q.pending).toBe(2);
    releases[0]();
    releases[1]();
    await Promise.all([c, d]);
    expect(order).toEqual(["c", "d"]);
  });
  it("rejects aborted waiters", async () => {
    const q = new PriorityQueue(1);
    const r = await q.acquire("a", 0);
    const ac = new AbortController();
    const p = q.acquire("b", 0, ac.signal);
    ac.abort();
    await expect(p).rejects.toThrow();
    r();
  });
});
