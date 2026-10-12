"use client";

import { useQuery } from "@tanstack/react-query";
import { engineGet } from "./client";
import type { CellsJSON } from "./types";

export function translationFor(mode: string, domToMinor: boolean, myxoToDorian = false): string {
  if (myxoToDorian && mode === "Myxolidian") return "dom_to_dorian";
  if (domToMinor && (mode === "MinorResolutions" || mode === "Locrian")) return "dom_to_minor";
  if (domToMinor && (mode === "Myxolidian" || mode === "MajorResolutions")) return "dom_to_major";
  return "none";
}

export function useCells(mode: string, bonus: boolean, translate = "none") {
  return useQuery({
    queryKey: ["engine", "cells", mode, bonus, translate],
    queryFn: () => engineGet<CellsJSON>("cells", { mode, bonus, translate }),
    staleTime: Infinity,
  });
}
