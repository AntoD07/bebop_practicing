"use client";

import { Checkbox, Field, Select, Slider, Switch } from "@/components/ui/field";
import { Info } from "@/components/ui/misc";
import type { PairsJSON } from "@/lib/engine/types";
import { CHORD_MODES, POSITIONS } from "@/lib/music/constants";
import { useConnections } from "@/lib/store/connections";
import { useSession } from "@/lib/store/session";

const TRANSLATABLE = new Set(["MinorResolutions", "MajorResolutions", "Locrian", "Myxolidian"]);

export function SetupPanel({ pairs, compact = false }: { pairs: PairsJSON | undefined; compact?: boolean }) {
  const s = useConnections();
  const position = useSession((x) => x.position);
  const myxoToDorian = (s.chord1 === "Dorian" || s.chord1 === "Minor") && s.chord2 === "Myxolidian";
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="First chord (ending cells)">
          <Select value={s.chord1} onChange={(e) => s.set({ chord1: e.target.value, pivot: null, selectedPair: null })}>
            {CHORD_MODES.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </Select>
          {TRANSLATABLE.has(s.chord1) && <Checkbox className="mt-1" label="Translate Dominant to Minor/Major-I" checked={s.domToMinor1} onChange={(e) => s.set({ domToMinor1: e.target.checked, pivot: null })} />}
        </Field>
        <Field label="Second chord (starting cells)">
          <Select value={s.chord2} onChange={(e) => s.set({ chord2: e.target.value, pivot: null, selectedPair: null })}>
            {CHORD_MODES.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </Select>
          {TRANSLATABLE.has(s.chord2) && !myxoToDorian && <Checkbox className="mt-1" label="Translate Dominant to Minor/Major-I" checked={s.domToMinor2} onChange={(e) => s.set({ domToMinor2: e.target.checked, pivot: null })} />}
        </Field>
      </div>
      {pairs?.mapping_info && <Info>{pairs.mapping_info.replace(/\*\*/g, "")}</Info>}
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="Pivot note (starts the second cell)">
          <Select value={pairs?.pivot ?? ""} onChange={(e) => s.set({ pivot: e.target.value, selectedPair: null })} disabled={!pairs}>
            {(pairs?.pivots ?? []).map((p) => (
              <option key={p.value} value={p.value}>
                {p.value}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Line movement (optional)">
          <Select value={s.movement} onChange={(e) => s.set({ movement: e.target.value as "" | "A" | "D", selectedPair: null })}>
            <option value="">Any</option>
            <option value="A">A (+N)</option>
            <option value="D">D (+N)</option>
          </Select>
        </Field>
        <Field label="Cells">
          <Checkbox label="Include bonus cells" checked={s.bonus} onChange={(e) => s.set({ bonus: e.target.checked, pivot: null, selectedPair: null })} />
        </Field>
      </div>
      {pairs?.harmony_info && <Info>{pairs.harmony_info}</Info>}
      {!compact && (
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Position" hint={s.enforce ? `Every fingering of each connection inside ${POSITIONS[position - 1]} (today's position, hard box) is listed.` : "Free: the single cheapest fingering anywhere on the neck."}>
            <Switch checked={s.enforce} onCheckedChange={(v) => s.set({ enforce: v })} label={s.enforce ? `Enforce today's position (${position})` : "Free"} />
          </Field>
          {s.enforce && pairs && !pairs.single_chord && (
            <Field label="Anchor the position on" hint="The box, the CAGED root strings and the Position label are built on this root.">
              <Select value={s.anchor} onChange={(e) => s.set({ anchor: e.target.value as "key" | "chord1" | "chord2" })}>
                {Object.entries(pairs.anchors ?? {}).map(([k, label]) => (
                  <option key={k} value={k}>
                    {label}
                  </option>
                ))}
              </Select>
            </Field>
          )}
        </div>
      )}
      <Field label={`Max fingering cost to display: ${s.maxCost.toFixed(1)}`} hint="Connections whose cheapest in-box fingering costs more are hidden; the exercise never practises hidden or deleted fingerings.">
        <Slider min={0} max={40} step={0.5} value={s.maxCost} onChange={(e) => s.set({ maxCost: Number(e.target.value) })} />
      </Field>
    </div>
  );
}
