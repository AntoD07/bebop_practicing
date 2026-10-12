import type { FingeringJSON } from "@/lib/engine/types";

/** The API's format_report text (never diverges from Python); falls back to
 * the structured fields when a response was fetched without reports. */
export function FullReport({ fingering }: { fingering: FingeringJSON }) {
  const f = fingering;
  const text =
    f.report ??
    [
      `total cost: ${f.cost}   upstrokes: ${f.n_up}   frets ${f.fret_lo}–${f.fret_hi}`,
      `layout: ${f.layout}`,
      `encoding: ${f.encoding}`,
      "",
      "FLAGS:",
      ...(f.flags.length ? f.flags.map((x) => `  - ${x}`) : ["  (none)"]),
      "",
      "Top cost contributors: " + f.contributions.filter(([, a]) => a > 0).slice(0, 4).map(([t, a]) => `${t}=${a.toFixed(2)}`).join(", "),
      ...(f.warnings.length ? ["", ...f.warnings.map((w) => `!! ${w}`)] : []),
    ].join("\n");
  return <pre className="scrollbar-thin max-h-[28rem] overflow-auto rounded-md border bg-bg-muted p-3 text-[11px] leading-snug">{text}</pre>;
}
