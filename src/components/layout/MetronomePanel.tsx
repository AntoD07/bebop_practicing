"use client";

import { useSession } from "@/lib/store/session";

/** The guitarapp.com metronome as an optional panel (lazy: only when shown).
 * Selecting it mutes the native click so the two never run together. */
export function MetronomePanel() {
  const tempo = useSession((s) => s.tempo);
  const show = useSession((s) => s.showIframe);
  if (!show) return null;
  return (
    <div className="mx-auto w-full max-w-5xl px-4 pt-3">
      <div className="overflow-hidden rounded-xl border bg-bg-elev">
        <iframe
          key={tempo}
          src={`https://guitarapp.com/metronome.html?embed=true&tempo=${tempo}&timeSignature=2&pattern=0`}
          title="Online Metronome"
          className="h-[520px] w-full border-0"
          loading="lazy"
        />
      </div>
    </div>
  );
}
