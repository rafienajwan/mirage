"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { KeyRound, Loader2, ShieldCheck } from "lucide-react";

function safeNextPath() {
  const target = new URLSearchParams(window.location.search).get("next");
  return target?.startsWith("/") && !target.startsWith("//")
    ? target
    : "/dashboard";
}

export default function LoginPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      if (!response.ok) {
        const body = await response.json() as { detail?: string };
        setError(body.detail ?? "Unable to authenticate");
        return;
      }
      router.replace(safeNextPath());
      router.refresh();
    } catch {
      setError("Authentication service is unavailable");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-bg-dark-navy px-5 py-12">
      <div className="noise-overlay" />
      <section className="relative z-10 w-full max-w-sm rounded-lg border border-white/10 bg-bg-cyber-navy p-7 shadow-2xl">
        <div className="mb-7 flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-lg border border-brand-cyan/25 bg-brand-cyan/5">
            <ShieldCheck className="h-5 w-5 text-brand-cyan" />
          </div>
          <div>
            <h1 className="font-display text-lg font-semibold text-white">
              MIRAGE Operator
            </h1>
            <p className="text-xs text-white/45">Protected dashboard access</p>
          </div>
        </div>

        <form className="space-y-4" onSubmit={submit}>
          <label className="block">
            <span className="mb-2 block text-xs font-medium text-white/65">
              Operator password
            </span>
            <span className="relative block">
              <KeyRound className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/35" />
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
                required
                autoFocus
                className="h-11 w-full rounded border border-white/10 bg-black/20 pl-10 pr-3 text-sm text-white outline-none transition focus:border-brand-cyan/50 focus:ring-2 focus:ring-brand-cyan/10"
              />
            </span>
          </label>

          {error && (
            <p role="alert" className="text-xs text-red-400">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="flex h-11 w-full items-center justify-center gap-2 rounded bg-brand-cyan px-4 text-sm font-semibold text-bg-dark-navy transition hover:bg-white disabled:cursor-wait disabled:opacity-60"
          >
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            <span>{submitting ? "Authenticating" : "Continue"}</span>
          </button>
        </form>
      </section>
    </main>
  );
}
