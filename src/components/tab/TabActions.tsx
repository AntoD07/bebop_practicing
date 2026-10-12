"use client";

import * as React from "react";
import { Copy, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/misc";

export function downloadSvg(svg: SVGSVGElement | null, filename = "tab.svg") {
  if (!svg) return;
  const xml = new XMLSerializer().serializeToString(svg);
  const blob = new Blob([xml], { type: "image/svg+xml" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function copyText(text: string, label = "Copied") {
  try {
    await navigator.clipboard.writeText(text);
    toast(label, "ok");
  } catch {
    toast("Clipboard unavailable", "danger");
  }
}

export function TabActions({ svgRef, encoding, filename }: { svgRef: React.RefObject<SVGSVGElement | null>; encoding: string; filename?: string }) {
  return (
    <div className="flex flex-wrap gap-2">
      <Button size="sm" variant="outline" onClick={() => downloadSvg(svgRef.current, filename)}>
        <Download size={14} /> SVG
      </Button>
      <Button size="sm" variant="outline" onClick={() => copyText(encoding, "Encoding copied")}>
        <Copy size={14} /> Copy encoding
      </Button>
    </div>
  );
}
