import * as React from "react";
import { cn } from "@/lib/utils";

export function Table({ className, ...props }: React.TableHTMLAttributes<HTMLTableElement>) {
  return (
    <div className="w-full overflow-x-auto rounded-lg border">
      <table className={cn("w-full text-sm", className)} {...props} />
    </div>
  );
}
export function Th({ className, ...props }: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return <th className={cn("sticky top-0 bg-bg-muted px-2 py-1.5 text-left text-xs font-semibold text-fg-muted whitespace-nowrap", className)} {...props} />;
}
export function Td({ className, ...props }: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={cn("border-t px-2 py-1.5 align-middle", className)} {...props} />;
}
export function Tr({ className, selected, ...props }: React.HTMLAttributes<HTMLTableRowElement> & { selected?: boolean }) {
  return <tr className={cn("transition-colors", props.onClick && "cursor-pointer hover:bg-bg-muted", selected && "bg-accent-soft", className)} {...props} />;
}
