"use client";

import * as React from "react";
import { Tabs as RTabs } from "radix-ui";
import { cn } from "@/lib/utils";

export const Tabs = RTabs.Root;

export function TabsList({ className, ...props }: React.ComponentProps<typeof RTabs.List>) {
  return <RTabs.List className={cn("inline-flex h-10 items-center gap-1 rounded-lg bg-bg-muted p-1", className)} {...props} />;
}

export function TabsTrigger({ className, ...props }: React.ComponentProps<typeof RTabs.Trigger>) {
  return (
    <RTabs.Trigger
      className={cn(
        "inline-flex h-8 flex-1 items-center justify-center whitespace-nowrap rounded-md px-3 text-sm font-medium text-fg-muted transition-colors data-[state=active]:bg-bg-elev data-[state=active]:text-fg data-[state=active]:shadow-sm",
        className,
      )}
      {...props}
    />
  );
}

export function TabsContent({ className, ...props }: React.ComponentProps<typeof RTabs.Content>) {
  return <RTabs.Content className={cn("outline-none", className)} {...props} />;
}
