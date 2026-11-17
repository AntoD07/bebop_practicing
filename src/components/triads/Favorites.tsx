"use client";

import * as React from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Field, Select } from "@/components/ui/field";
import { Card, Info, Spinner, toast } from "@/components/ui/misc";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { FingeringCard } from "@/components/tab/FingeringCard";
import { enginePost } from "@/lib/engine/client";
import type { Favorite, FavoriteRenderJSON } from "@/lib/engine/types";
import { PRACTICE_KEYS } from "@/lib/music/constants";
import type { Weights } from "@/lib/store/pentatonics";
import { fmtCost } from "@/lib/utils";

export const FAVORITES_PAGE = "triad_pairs";
export const favoritesQueryKey = ["favorites", FAVORITES_PAGE] as const;

const triadName = (root: string, quality: string) => (quality === "major" ? root : `${root} ${quality}`);
export const pairName = (p: Favorite["pair"]) => `${triadName(p.roots[0], p.qualities[0])} + ${triadName(p.roots[1], p.qualities[1])}`;
const layoutSig = (layout: number[][]) => layout.map(([s, f]) => `${s}/${f}`).join(" ");

/** Saved layouts, replayed as saved or mimicked in any key (same position). */
export function Favorites({ pageKey, weights }: { pageKey: string; weights: Weights }) {
  const qc = useQueryClient();
  const favQ = useQuery({
    queryKey: favoritesQueryKey,
    queryFn: async () => {
      const r = await fetch(`/api/favorites?page=${FAVORITES_PAGE}`);
      if (!r.ok) throw new Error(`favourites: HTTP ${r.status}`);
      return ((await r.json()) as { favorites: Favorite[] }).favorites;
    },
  });
  const favs = favQ.data ?? [];
  const [selId, setSelId] = React.useState<string | null>(null);
  const [showKey, setShowKey] = React.useState<string | null>(null); // null = the page's key
  const sel = favs.find((f) => f.id === selId) ?? null;
  const key = showKey ?? pageKey;
  const body = sel ? { favorite: { key: sel.key, position: sel.position, pair: sel.pair, layout: sel.layout, line: sel.line }, key, config: weights } : null;
  const renderQ = useQuery({ queryKey: ["engine", "triads/favorites/render", body], queryFn: () => enginePost<FavoriteRenderJSON>("triads/favorites/render", body), enabled: !!body, staleTime: Infinity });
  const r = renderQ.data;

  async function remove(id: string) {
    const res = await fetch(`/api/favorites/${encodeURIComponent(id)}`, { method: "DELETE" });
    if (!res.ok) return toast(`Could not delete the favourite (HTTP ${res.status})`, "danger");
    setSelId(null);
    qc.invalidateQueries({ queryKey: favoritesQueryKey });
  }

  let caption: React.ReactNode = null;
  if (sel && r && r.pair_title) {
    caption = r.as_saved ? (
      <>
        <strong>{r.pair_title}</strong> in {sel.key} — as saved ({sel.position ?? "Free"}, start on {sel.start})
      </>
    ) : (
      <>
        <strong>{r.pair_title}</strong> in {r.key} — mimicked from {sel.key} ({pairName(sel.pair)}): layout slid {r.fret_delta > 0 ? "+" : ""}
        {r.fret_delta} frets
        {sel.position ? (r.in_box ? `, inside the ${sel.position} box` : `, OUTSIDE the ${sel.position} box for ${r.key}`) : ""}
      </>
    );
  }

  return (
    <Card className="space-y-3">
      <h2 className="text-base font-semibold">⭐ Favourite fingerings</h2>
      {favQ.isLoading && <Spinner />}
      {favQ.error && <Info tone="danger">{(favQ.error as Error).message}</Info>}
      {favQ.data && !favs.length && <p className="text-xs text-fg-muted">None yet — generate an exercise, pick a fingering and press &quot;Save as favourite&quot;.</p>}
      {favs.length > 0 && (
        <>
          <p className="text-xs text-fg-muted">Select a favourite to replay it. Choose another key to see the SAME fingering mimicked there — the layout slides to that key&apos;s root fret, the triads move with the key, the engine re-derives the picking.</p>
          <Table>
            <thead>
              <tr>
                <Th>Saved</Th>
                <Th>Exercise</Th>
                <Th>Pair</Th>
                <Th>Key</Th>
                <Th>Position</Th>
                <Th>Start</Th>
                <Th>Params</Th>
                <Th className="text-right">Cost</Th>
                <Th>Layout</Th>
              </tr>
            </thead>
            <tbody>
              {favs.map((f) => (
                <Tr key={f.id} selected={f.id === selId} onClick={() => setSelId(f.id === selId ? null : f.id)}>
                  <Td>{f.createdAt.slice(0, 10)}</Td>
                  <Td>{f.exercise}</Td>
                  <Td>{pairName(f.pair)}</Td>
                  <Td>{f.key}</Td>
                  <Td>{f.position ?? "Free"}</Td>
                  <Td>{f.start}</Td>
                  <Td className="max-w-[14rem] truncate">{Object.entries(f.params).map(([k, v]) => `${k}=${v}`).join(", ")}</Td>
                  <Td className="text-right tabular-nums">{fmtCost(f.cost)}</Td>
                  <Td className="max-w-[16rem] truncate font-mono text-[11px]">{layoutSig(f.layout)}</Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        </>
      )}
      {sel && (
        <>
          <div className="flex flex-wrap items-end gap-3">
            <Field label="Show in key" className="w-56">
              <Select value={showKey ?? ""} onChange={(e) => setShowKey(e.target.value || null)}>
                <option value="">The page&apos;s key ({pageKey})</option>
                {PRACTICE_KEYS.map((k) => (
                  <option key={k} value={k}>
                    {k}
                    {k === sel.key ? " (as saved)" : ""}
                  </option>
                ))}
              </Select>
            </Field>
            <Button size="sm" variant="ghost" onClick={() => remove(sel.id)}>
              Delete this favourite
            </Button>
          </div>
          {renderQ.isLoading && <Spinner />}
          {renderQ.error && <Info tone="danger">{(renderQ.error as Error).message}</Info>}
          {r?.message && <Info tone="warn">{r.message}</Info>}
          {r?.fingering && <FingeringCard fingering={r.fingering} caption={caption} filename="triad_pair_favourite.svg" options={{ showChords: false }} />}
        </>
      )}
    </Card>
  );
}
