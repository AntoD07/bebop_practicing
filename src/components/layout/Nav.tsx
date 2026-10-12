"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Home, Link2, ListMusic, FileMusic, Hexagon, Triangle } from "lucide-react";
import { cn } from "@/lib/utils";

const ITEMS = [
  { href: "/", label: "Home", icon: Home },
  { href: "/connections", label: "Connections", icon: Link2 },
  { href: "/lines", label: "Lines", icon: ListMusic },
  { href: "/score", label: "Score", icon: FileMusic },
  { href: "/pentatonics", label: "Pentatonics", icon: Hexagon },
  { href: "/triads", label: "Triads", icon: Triangle },
];

export function BottomNav() {
  const path = usePathname();
  return (
    <nav className="fixed inset-x-0 bottom-0 z-30 border-t bg-bg/95 backdrop-blur lg:hidden" style={{ paddingBottom: "env(safe-area-inset-bottom)" }}>
      <ul className="flex h-[var(--bottom-nav-h)] items-stretch">
        {ITEMS.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? path === "/" : path.startsWith(href);
          return (
            <li key={href} className="flex-1">
              <Link href={href} className={cn("flex h-full flex-col items-center justify-center gap-0.5 text-[10px]", active ? "text-accent" : "text-fg-muted")}>
                <Icon size={20} />
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

export function SideNav() {
  const path = usePathname();
  const router = useRouter();
  return (
    <aside className="sticky top-[var(--header-h)] hidden h-[calc(100dvh-var(--header-h))] w-52 shrink-0 border-r lg:block">
      <ul className="space-y-1 p-3">
        {ITEMS.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? path === "/" : path.startsWith(href);
          return (
            <li key={href}>
              <Link href={href} className={cn("flex items-center gap-2 rounded-md px-3 py-2 text-sm", active ? "bg-accent-soft text-accent font-medium" : "text-fg-muted hover:bg-bg-muted")}>
                <Icon size={18} />
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
      <button
        className="absolute bottom-3 left-3 text-xs text-fg-muted hover:underline"
        onClick={async () => {
          await fetch("/api/auth/logout", { method: "POST" });
          router.push("/login");
          router.refresh();
        }}
      >
        Sign out
      </button>
    </aside>
  );
}
