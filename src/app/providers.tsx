"use client";

import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/misc";
import { useAudioUnlock } from "@/lib/audio/useAudio";
import { useRehydrateStores } from "@/lib/store/hydrate";

function AudioUnlock() {
  useAudioUnlock();
  return null;
}

function Rehydrate() {
  useRehydrateStores();
  return null;
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [qc] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false } },
      }),
  );
  return (
    <QueryClientProvider client={qc}>
      <AudioUnlock />
      {children}
      {/* after the children's effects, so store subscriptions (drill sync…) see the rehydration */}
      <Rehydrate />
      <Toaster />
    </QueryClientProvider>
  );
}
