"use client";

import * as React from "react";

type Ctx = { content: React.ReactNode; setContent: (n: React.ReactNode) => void; open: boolean; setOpen: (b: boolean) => void };
const PageSettingsContext = React.createContext<Ctx | null>(null);

export function PageSettingsProvider({ children }: { children: React.ReactNode }) {
  const [content, setContent] = React.useState<React.ReactNode>(null);
  const [open, setOpen] = React.useState(false);
  const value = React.useMemo(() => ({ content, setContent, open, setOpen }), [content, open]);
  return <PageSettingsContext.Provider value={value}>{children}</PageSettingsContext.Provider>;
}

export function usePageSettingsContext() {
  const ctx = React.useContext(PageSettingsContext);
  if (!ctx) throw new Error("PageSettingsProvider missing");
  return ctx;
}

/** A page registers the options UI the header's gear button opens. */
export function usePageSettings(node: React.ReactNode, deps: React.DependencyList) {
  const { setContent } = usePageSettingsContext();
  React.useEffect(() => {
    setContent(node);
    return () => setContent(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
