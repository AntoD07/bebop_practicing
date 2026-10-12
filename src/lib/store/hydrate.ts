"use client";

import { useEffect, useState } from "react";
import { useDrill } from "@/lib/drill/store";
import { useConnections } from "./connections";
import { useHome } from "./home";
import { useLines } from "./lines";
import { usePenta } from "./pentatonics";
import { useScore } from "./score";
import { useSession } from "./session";
import { useTriads } from "./triads";

const STORES = [useSession, useHome, useConnections, useLines, useScore, usePenta, useTriads, useDrill] as const;

/** Persisted stores skip automatic hydration (the server-rendered HTML must
 * match the first client render); this rehydrates them all right after mount. */
export function useRehydrateStores(): boolean {
  const [done, setDone] = useState(false);
  useEffect(() => {
    Promise.all(STORES.map((s) => s.persist.rehydrate())).finally(() => setDone(true));
  }, []);
  return done;
}
