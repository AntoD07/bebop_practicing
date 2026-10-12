"use client";

import * as React from "react";
import { Dialog } from "radix-ui";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

export const Sheet = Dialog.Root;
export const SheetTrigger = Dialog.Trigger;
export const SheetClose = Dialog.Close;

export function SheetContent({
  side = "right",
  title,
  description,
  className,
  children,
}: {
  side?: "right" | "bottom" | "left";
  title: React.ReactNode;
  description?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}) {
  const pos =
    side === "bottom"
      ? "inset-x-0 bottom-0 max-h-[88dvh] rounded-t-2xl"
      : side === "left"
        ? "inset-y-0 left-0 w-[88vw] max-w-sm"
        : "inset-y-0 right-0 w-[92vw] max-w-md";
  return (
    <Dialog.Portal>
      <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[1px]" />
      <Dialog.Content
        className={cn("fixed z-50 flex flex-col overflow-hidden border bg-bg shadow-xl outline-none", pos, className)}
        style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
      >
        <div className="flex items-center justify-between border-b px-4 py-3">
          <div>
            <Dialog.Title className="text-base font-semibold">{title}</Dialog.Title>
            {description ? <Dialog.Description className="text-xs text-fg-muted">{description}</Dialog.Description> : <Dialog.Description className="sr-only">{title}</Dialog.Description>}
          </div>
          <Dialog.Close className="rounded-md p-2 hover:bg-bg-muted" aria-label="Close">
            <X size={18} />
          </Dialog.Close>
        </div>
        <div className="scrollbar-thin flex-1 overflow-y-auto p-4">{children}</div>
      </Dialog.Content>
    </Dialog.Portal>
  );
}

export function DialogContent({ title, description, className, children }: { title: React.ReactNode; description?: React.ReactNode; className?: string; children: React.ReactNode }) {
  return (
    <Dialog.Portal>
      <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40" />
      <Dialog.Content className={cn("fixed left-1/2 top-1/2 z-50 w-[92vw] max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-xl border bg-bg p-5 shadow-xl outline-none", className)}>
        <Dialog.Title className="text-base font-semibold">{title}</Dialog.Title>
        {description ? <Dialog.Description className="mt-1 text-sm text-fg-muted">{description}</Dialog.Description> : <Dialog.Description className="sr-only">{title}</Dialog.Description>}
        <div className="mt-4">{children}</div>
      </Dialog.Content>
    </Dialog.Portal>
  );
}
