"use client";

import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Checkbox, Field, NumberStepper, Select, Slider, Switch } from "@/components/ui/field";
import { Badge, Card, Info, Spinner } from "@/components/ui/misc";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { usePageSettings } from "@/components/layout/PageSettings";
import { connectionRequest, useConnectionRows, useCuration, usePairs, usePairsRequest, usePickKey, type PairRow } from "@/lib/connections/useConnections";
import { buildItems, secondsPerItem } from "@/lib/drill/buildItems";
import { registerFingerings, useDrill } from "@/lib/drill/store";
import { DrillPanel } from "@/components/drill/DrillPanel";
import { toast } from "@/components/ui/misc";
import { enginePost } from "@/lib/engine/client";
import type { ConnectionJSON } from "@/lib/engine/types";
import { FREE_POSITION, POSITIONS } from "@/lib/music/constants";
import { useConnections } from "@/lib/store/connections";
import { useSession } from "@/lib/store/session";
import { ConnectionsTable, LoadProgress } from "./ConnectionsTable";
import { FingeringList } from "./FingeringList";
import { SetupPanel } from "./SetupPanel";

function PageOptions() {
  const s = useConnections();
  const position = useSession((x) => x.position);
  return (
    <div className="space-y-3">
      <Switch checked={s.enforce} onCheckedChange={(v) => s.set({ enforce: v })} label={s.enforce ? `Enforce today's position (${POSITIONS[position - 1]})` : "Free (cheapest anywhere)"} />
      <Checkbox label="Include bonus cells" checked={s.bonus} onChange={(e) => s.set({ bonus: e.target.checked, pivot: null })} />
      <Field label={`Max fingering cost: ${s.maxCost.toFixed(1)}`}>
        <Slider min={0} max={40} step={0.5} value={s.maxCost} onChange={(e) => s.set({ maxCost: Number(e.target.value) })} />
      </Field>
      <Field label="Line movement">
        <Select value={s.movement} onChange={(e) => s.set({ movement: e.target.value as "" | "A" | "D" })} className="w-32">
          <option value="">Any</option>
          <option value="A">A (+N)</option>
          <option value="D">D (+N)</option>
        </Select>
      </Field>
      <Field label="Exercise">
        <div className="flex flex-wrap items-center gap-3">
          <NumberStepper ariaLabel="Total practice minutes" value={s.totalMinutes} onChange={(v) => s.set({ totalMinutes: v })} min={1} max={120} />
          <span className="text-xs text-fg-muted">minutes in total</span>
        </div>
        <Checkbox className="mt-1" label="Show the tab during the exercise" checked={s.showTab} onChange={(e) => s.set({ showTab: e.target.checked })} />
        <Checkbox label="Practice all kept fingerings of each connection" checked={s.allFingerings} onChange={(e) => s.set({ allFingerings: e.target.checked })} />
      </Field>
    </div>
  );
}

export function ConnectionsPage() {
  const s = useConnections();
  const session = useSession();
  const qc = useQueryClient();
  const req = usePairsRequest();
  const pairsQ = usePairs(req);
  const pairs = pairsQ.data;
  const position = s.enforce ? POSITIONS[session.position - 1] : null;
  const pickKey = usePickKey(pairs, position);
  const cur = useCuration(pickKey, pairs);
  const priority = React.useMemo(() => (s.selectedPair ? [s.selectedPair] : []), [s.selectedPair]);
  const { list, queries } = useConnectionRows(pairs, position, priority);
  const [loadingAll, setLoadingAll] = React.useState<string | null>(null);
  const [selectedSig, setSelectedSig] = React.useState<string | null>(null);

  usePageSettings(<PageOptions />, []);

  const byId = React.useMemo(() => new Map((pairs?.ending ?? []).concat(pairs?.starting ?? []).map((c) => [c.id, c])), [pairs]);

  // (no manual memo: the React compiler owns memoization here)
  const rows: PairRow[] = (() => {
    return list.map((p, i) => {
      const q = queries[i];
      const data = (q?.data as ConnectionJSON | undefined) ?? null;
      const inBox = data ? data.fingerings.filter((f) => !position || f.positions.includes(position)) : [];
      const best = inBox[0] ?? null;
      const gone = cur.deleted(p.pair_key);
      const candidates = inBox.filter((f) => f.cost <= s.maxCost);
      const kept = candidates.filter((f) => !gone.has(f.layout));
      return {
        pairKey: p.pair_key,
        end: byId.get(p.end_id)!,
        start: byId.get(p.start_id)!,
        index: i,
        status: q?.isError ? "error" : q?.data ? "done" : q?.isFetching ? "loading" : "pending",
        data,
        error: q?.error ? (q.error as Error).message : null,
        inBox,
        candidates,
        kept,
        best,
        fits: inBox.length > 0,
        underMax: !!best && best.cost <= s.maxCost,
        isKept: cur.isKept(p.pair_key),
      } as PairRow;
    });
  })();

  const done = rows.filter((r) => r.status === "done");
  const errors = rows.filter((r) => r.status === "error");
  const visible = done.filter((r) => r.fits && r.underMax).sort((a, b) => a.best!.cost - b.best!.cost);
  const notFit = done.filter((r) => !r.fits).length;
  const hiddenByMax = done.filter((r) => r.fits && !r.underMax).length;
  const pending = rows.filter((r) => r.status !== "done");
  const selected = visible.find((r) => r.pairKey === s.selectedPair) ?? visible[0] ?? null;
  const items = buildItems(visible.map((r) => ({ pairKey: r.pairKey, end: r.end, start: r.start, candidates: r.candidates })), { kept: cur.isKept, deleted: cur.deleted, allFingerings: s.allFingerings });
  const nPairs = new Set(items.map((i) => i.pairKey)).size;
  const perItem = secondsPerItem(s.totalMinutes, items.length);
  const drill = useDrill();
  const fingeringByItem = (itemId: string) => {
    // item id = `${pairKey}#${layout}`; cell names may contain '#' (e.g. "#11"),
    // the layout never does, so split on the LAST one
    const cut = itemId.lastIndexOf("#");
    const pk = itemId.slice(0, cut);
    const sig = itemId.slice(cut + 1);
    return visible.find((r) => r.pairKey === pk)?.inBox.find((f) => f.layout === sig);
  };

  // keep the drill's fingerings (and item list) in sync with what is loaded;
  // the drill was started from THIS setup when its request matches
  const itemsSig = items.map((i) => i.id).join("|");
  const drillRequestSig = drill.config ? JSON.stringify(drill.config.request) : null;
  const currentRequestSig = JSON.stringify({ key: session.key, pairs: req, position, anchor: pairs?.single_chord ? "key" : s.anchor, flags: { bonus: s.bonus, domToMinor1: s.domToMinor1, domToMinor2: s.domToMinor2 } });
  React.useEffect(() => {
    registerFingerings(items.map((it) => [it.id, fingeringByItem(it.id)!]).filter((e) => e[1]) as [string, NonNullable<ReturnType<typeof fingeringByItem>>][]);
    // rebuild only once THIS setup's pairs are fully loaded (never from an
    // empty/partial list: that would wipe a live drill)
    if (drill.status !== "idle" && drillRequestSig === currentRequestSig && pairs && list.length > 0 && pending.length === 0 && items.length > 0) {
      const d = useDrill.getState();
      const cur = d.items[d.currentIndex];
      const same = d.items.map((i) => i.id).join("|") === itemsSig;
      if (!same) {
        d.setItems(items);
        if (cur && !items.some((i) => i.id === cur.id)) toast("The current item is no longer in the kept set", "danger");
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [itemsSig, pending.length, drillRequestSig, currentRequestSig]);

  function startDrill(from = 0) {
    if (!items.length) {
      toast("No playable combinations for this pivot/position", "danger");
      return;
    }
    registerFingerings(items.map((it) => [it.id, fingeringByItem(it.id)!]).filter((e) => e[1]) as [string, NonNullable<ReturnType<typeof fingeringByItem>>][]);
    drill.start(
      items,
      {
        pickKey,
        request: { key: session.key, pairs: req, position, anchor: pairs?.single_chord ? "key" : s.anchor, flags: { bonus: s.bonus, domToMinor1: s.domToMinor1, domToMinor2: s.domToMinor2 } },
        totalMinutes: s.totalMinutes,
        secondsPerItem: perItem,
        allFingerings: s.allFingerings,
        showTab: s.showTab,
        switchMode: "reset",
        cue: true,
        loopSession: drill.config?.loopSession ?? false,
      },
      from,
    );
  }

  function practiceFrom(pk: string) {
    const idx = items.findIndex((i) => i.pairKey === pk);
    startDrill(Math.max(0, idx));
  }

  async function loadAll(row: PairRow) {
    if (!pairs) return;
    setLoadingAll(row.pairKey);
    try {
      const pair = list.find((p) => p.pair_key === row.pairKey)!;
      const base = connectionRequest(pairs, pair, session.key, position, s.anchor, { bonus: s.bonus, domToMinor1: s.domToMinor1, domToMinor2: s.domToMinor2 });
      const parts = await Promise.all([0, 1].map((box) => enginePost<ConnectionJSON>("fingering/connection", { ...base, box, max_layouts: 10000 })));
      const seen = new Map<string, ConnectionJSON["fingerings"][number]>();
      for (const part of parts) for (const f of part.fingerings) if (!seen.has(f.layout)) seen.set(f.layout, f);
      const merged: ConnectionJSON = { ...parts[0], fingerings: Array.from(seen.values()).sort((a, b) => a.cost - b.cost || a.layout.localeCompare(b.layout)), truncated: parts.some((p) => p.truncated), chunks: parts.flatMap((p) => p.chunks), n_total: seen.size };
      qc.setQueryData(["engine", "fingering/connection", base], merged);
    } finally {
      setLoadingAll(null);
    }
  }

  const positionLabel = position ?? FREE_POSITION;
  const listPane = selected ? (
    <FingeringList
      row={selected}
      deleted={cur.deleted(selected.pairKey)}
      showDeleted={cur.curation.showDeleted}
      onShowDeleted={cur.setShowDeleted}
      onDelete={(sig) => cur.deleteFingering(selected.pairKey, sig)}
      onRestore={(sig) => cur.restoreFingering(selected.pairKey, sig)}
      onKeepOnly={(sig, all) => cur.keepOnly(selected.pairKey, sig, all)}
      onRestoreAll={() => cur.restoreAll(selected.pairKey)}
      onLoadAll={selected.data?.truncated ? () => loadAll(selected) : undefined}
      loadingAll={loadingAll === selected.pairKey}
      maxCost={s.maxCost}
      positionLabel={positionLabel}
      selectedSig={selectedSig}
      onSelectSig={setSelectedSig}
    />
  ) : (
    <p className="text-sm text-fg-muted">Select a connection in the table to browse its fingerings.</p>
  );

  const tablePane = (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold">
          Connections on <span className="text-accent">{pairs?.pivot ?? "…"}</span> <span className="text-fg-muted">· {visible.length} shown</span>
        </h2>
        <LoadProgress done={done.length + errors.length} total={rows.length} errors={errors.length} />
      </div>
      <p className="text-xs text-fg-muted">
        {position ? (
          <>
            Enforced position <strong>{position}</strong>, anchored on <strong>{selected?.data?.anchor.sym ?? pairs?.anchors?.[pairs.single_chord ? "key" : s.anchor] ?? "…"}</strong>.{" "}
          </>
        ) : (
          <>Free: no position enforced (cheapest fingering anywhere). </>
        )}
        {notFit > 0 && <>{notFit} combination(s) do not fit the position. </>}
        {hiddenByMax > 0 && <>{hiddenByMax} hidden: their cheapest fingering costs more than {s.maxCost}. </>}
        {cur.serverSaved && <>Saved selection loaded ({cur.serverSaved.slice(0, 10)}). </>}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" variant="outline" onClick={cur.keepAll}>
          Keep all
        </Button>
        <Button size="sm" variant="outline" onClick={cur.keepNone}>
          Keep none
        </Button>
        <Badge tone={cur.saving === "saved" ? "ok" : cur.saving === "error" ? "danger" : "default"}>{cur.saving === "saving" ? "Saving…" : cur.saving === "saved" ? "Saved ✓" : cur.saving === "error" ? "Save failed" : cur.curation.dirty ? "Unsaved" : cur.serverSaved ? "Saved" : "No saved selection (all kept)"}</Badge>
        {cur.serverSaved && (
          <Button size="sm" variant="ghost" onClick={cur.deleteSaved}>
            Delete saved selection
          </Button>
        )}
        <span className="ml-auto text-xs text-fg-muted">
          <strong>{items.length}</strong> fingerings across <strong>{nPairs}</strong> combinations · {perItem}s each over {s.totalMinutes} min
        </span>
      </div>
      <ConnectionsTable rows={visible} pending={pending} selected={selected?.pairKey ?? null} onSelect={(pk) => { s.set({ selectedPair: pk }); setSelectedSig(null); }} onKept={cur.setKept} onPractice={practiceFrom} />
    </div>
  );

  const drillSummary = (
    <>
      <strong>{items.length}</strong> fingerings across <strong>{nPairs}</strong> combinations, easiest → hardest; each shown for <strong>{perItem}s</strong> ({s.totalMinutes} min).
      {pending.length > 0 && <> {pending.length} still loading — you can start now.</>}
    </>
  );
  const drillPanel = <DrillPanel onStart={() => startDrill(0)} summary={drillSummary} />;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Cell connections</h1>
      {pairsQ.error && <Info tone="danger">{(pairsQ.error as Error).message}</Info>}
      {/* phone: tabs; desktop: setup + table on the left, the selected pair on the right */}
      <div className="lg:hidden">
        <Tabs defaultValue="table">
          <TabsList className="w-full">
            <TabsTrigger value="setup">Setup</TabsTrigger>
            <TabsTrigger value="table">Table</TabsTrigger>
            <TabsTrigger value="pair">Pair</TabsTrigger>
            <TabsTrigger value="drill">Drill</TabsTrigger>
          </TabsList>
          <TabsContent value="setup" className="mt-3">
            <Card>
              <SetupPanel pairs={pairs} />
            </Card>
          </TabsContent>
          <TabsContent value="table" className="mt-3">
            {pairsQ.isLoading ? <Spinner /> : tablePane}
          </TabsContent>
          <TabsContent value="pair" className="mt-3">
            {listPane}
          </TabsContent>
          <TabsContent value="drill" className="mt-3">
            <Card>
              <p className="mb-3 text-sm text-fg-muted">{drillSummary}</p>
              <Button size="lg" className="w-full" onClick={() => startDrill(0)} disabled={!items.length}>
                {drill.status === "idle" ? "Start exercise" : "Restart from the first item"}
              </Button>
              <p className="mt-3 text-xs text-fg-muted">The running exercise lives in the bar at the bottom of the screen: tap it to expand the tab, the countdown and the item strip.</p>
            </Card>
          </TabsContent>
        </Tabs>
        {drillPanel}
        {drill.status !== "idle" && <div className="h-[80px]" />}
      </div>
      <div className="hidden gap-4 lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          <details className="rounded-xl border bg-bg-elev p-3" open>
            <summary className="cursor-pointer text-sm font-semibold">Setup</summary>
            <div className="mt-3">
              <SetupPanel pairs={pairs} compact />
            </div>
          </details>
          {pairsQ.isLoading ? <Spinner /> : tablePane}
        </div>
        <div className="space-y-4 lg:sticky lg:top-[calc(var(--header-h)+8px)] lg:max-h-[calc(100dvh-var(--header-h)-16px)] lg:overflow-y-auto">
          <Card>{drillPanel}</Card>
          <Card>{listPane}</Card>
        </div>
      </div>
    </div>
  );
}
