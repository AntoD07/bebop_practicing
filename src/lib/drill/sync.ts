"use client";

import { useEffect, useRef } from "react";
import { debounce } from "@/lib/utils";
import { useDrill } from "./store";
import type { DrillState } from "./types";

const ID = "connections";

export function pickState(s: DrillState): DrillState {
  return { status: s.status, config: s.config, items: s.items, currentIndex: s.currentIndex, itemRemainingMs: s.itemRemainingMs, itemDeadlineAt: s.itemDeadlineAt, sessionStartedAt: s.sessionStartedAt, updatedAt: s.updatedAt, deviceId: s.deviceId, lastEvent: null };
}

export async function fetchRemoteDrill(): Promise<DrillState | null> {
  try {
    const r = await fetch(`/api/drill/${ID}`);
    if (!r.ok) return null;
    const j = (await r.json()) as { exists: boolean; state?: DrillState };
    return j.exists && j.state ? j.state : null;
  } catch {
    return null;
  }
}

/** Mirrors the drill state to the server (debounced 2 s, immediately on a
 * status change) and, on mount, adopts a NEWER remote state — paused, so a
 * drill started on the laptop never auto-plays on the phone. Returns whether
 * a remote state was adopted (the page then rebuilds the items). */
export function useDrillSync(onAdopted?: () => void) {
  const adoptedRef = useRef(false);
  useEffect(() => {
    let cancelled = false;
    const put = debounce((state: DrillState) => {
      fetch(`/api/drill/${ID}`, { method: "PUT", headers: { "content-type": "application/json" }, body: JSON.stringify({ state }) }).catch(() => {});
    }, 2000);
    fetchRemoteDrill().then((remote) => {
      if (cancelled || !remote) return;
      const local = useDrill.getState();
      if (remote.updatedAt > local.updatedAt && remote.deviceId !== local.deviceId && remote.items.length) {
        useDrill.getState().hydrate(remote);
        adoptedRef.current = true;
        onAdopted?.();
      }
    });
    const unsub = useDrill.subscribe((s, prev) => {
      if (s.updatedAt === prev.updatedAt && s.currentIndex === prev.currentIndex && s.status === prev.status) return;
      const state = pickState(s);
      if (s.status !== prev.status) put.flush(state);
      else put(state);
    });
    return () => {
      cancelled = true;
      unsub();
      put.cancel();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return adoptedRef;
}
