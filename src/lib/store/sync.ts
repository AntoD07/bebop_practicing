// Mirrors a zustand store slice to the settings table so phone and laptop
// agree. Last writer wins on `updatedAt` (ISO strings compare lexically).
import type { StoreApi } from "zustand";
import { debounce } from "@/lib/utils";

export type Synced = { updatedAt: string };

export function nowIso() {
  return new Date().toISOString();
}

export function startSettingsSync<T extends Synced>(
  store: StoreApi<T>,
  key: string,
  pick: (s: T) => Partial<T>,
  opts: { debounceMs?: number } = {},
): () => void {
  let applyingRemote = false;
  let lastSent = "";
  const put = debounce((value: Partial<T>, updatedAt: string) => {
    const body = JSON.stringify({ value, updatedAt });
    if (body === lastSent) return;
    lastSent = body;
    fetch(`/api/settings/${encodeURIComponent(key)}`, { method: "PUT", headers: { "content-type": "application/json" }, body }).catch(() => {});
  }, opts.debounceMs ?? 1000);

  fetch(`/api/settings/${encodeURIComponent(key)}`)
    .then((r) => (r.ok ? r.json() : null))
    .then((row: { value: Partial<T> | null; updatedAt: string | null } | null) => {
      if (!row || !row.value || !row.updatedAt) return;
      const local = store.getState().updatedAt;
      if (!local || row.updatedAt > local) {
        applyingRemote = true;
        store.setState({ ...row.value, updatedAt: row.updatedAt } as Partial<T> as T, false);
        applyingRemote = false;
      }
    })
    .catch(() => {});

  const unsub = store.subscribe((state, prev) => {
    if (applyingRemote) return;
    if (state === prev) return;
    const value = pick(state);
    const prevValue = pick(prev);
    if (JSON.stringify(value) === JSON.stringify(prevValue)) return;
    put(value, state.updatedAt);
  });
  return () => {
    unsub();
    put.cancel();
  };
}
