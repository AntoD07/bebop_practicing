"use client";

import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/misc";
import { useAudioUnlock } from "@/lib/audio/useAudio";

function AudioUnlock() {
  useAudioUnlock();
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
      <Toaster />
    </QueryClientProvider>
  );
}
