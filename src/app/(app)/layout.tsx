import { PracticeHeader } from "@/components/layout/PracticeHeader";
import { BottomNav, SideNav } from "@/components/layout/Nav";
import { MetronomePanel } from "@/components/layout/MetronomePanel";
import { PageSettingsProvider } from "@/components/layout/PageSettings";

// Mounted ONCE for every page: the header (key/position/tempo/metronome) and
// the navigation never remount on route changes, so the click keeps running.
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <PageSettingsProvider>
      <PracticeHeader />
      <MetronomePanel />
      <div className="mx-auto flex w-full max-w-6xl">
        <SideNav />
        <main className="min-w-0 flex-1 px-4 pb-[calc(var(--bottom-nav-h)+16px)] pt-4 lg:pb-8">{children}</main>
      </div>
      <BottomNav />
    </PageSettingsProvider>
  );
}
