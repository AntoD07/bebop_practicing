"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const r = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ password }),
    });
    setBusy(false);
    if (r.ok) {
      const next = params.get("next") || "/connections";
      router.replace(next.startsWith("/") ? next : "/connections");
      router.refresh();
    } else {
      setError(r.status === 401 ? "Wrong password." : `Login failed (${r.status}).`);
    }
  }

  return (
    <form onSubmit={submit} className="w-full max-w-sm space-y-4 rounded-xl border bg-bg-elev p-6 shadow-sm">
      <div>
        <h1 className="text-xl font-semibold">Bebop practice</h1>
        <p className="text-sm text-fg-muted">Enter the shared password. You stay signed in on this device.</p>
      </div>
      <input
        type="password"
        autoFocus
        autoComplete="current-password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className="h-11 w-full rounded-md border bg-bg px-3 text-base outline-none focus:ring-2 focus:ring-ring"
        placeholder="Password"
      />
      {error && <p className="text-sm text-danger">{error}</p>}
      <button
        type="submit"
        disabled={busy || !password}
        className="h-11 w-full rounded-md bg-accent text-accent-fg font-medium disabled:opacity-50"
      >
        {busy ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}

export default function LoginPage() {
  return (
    <main className="flex min-h-dvh items-center justify-center p-4">
      <Suspense fallback={null}>
        <LoginForm />
      </Suspense>
    </main>
  );
}
