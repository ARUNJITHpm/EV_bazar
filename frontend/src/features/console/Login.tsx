import { useState } from "react";

/**
 * PART C.0 — the console sign-in.
 *
 * This form is a convenience, not a security boundary. Every console endpoint
 * refuses on its own via `require_operator`, so hiding this screen would not
 * expose anything and showing it does not grant anything (PLAN C.0).
 */
export function Login({ onSignedIn }: { onSignedIn: () => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/internal/console/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ password }),
      });
      if (res.ok) {
        setPassword("");
        onSignedIn();
        return;
      }
      // 503 means the deployment has no password set. Say so plainly rather
      // than reporting it as a wrong password — they are different problems
      // and only one of them is the operator's fault.
      const body = (await res.json().catch(() => null)) as { detail?: string } | null;
      setError(
        res.status === 503
          ? (body?.detail ?? "Console auth is not configured on this deployment.")
          : "Incorrect password.",
      );
    } catch {
      setError("Could not reach the server.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-ground text-ink">
      <form onSubmit={submit} className="w-full max-w-sm border border-rule p-6">
        <p className="font-ui text-[11px] font-bold tracking-[0.08em] uppercase">
          EV Site Intelligence
        </p>
        <p className="mb-6 font-data text-[11px] text-ink-faint">operations console</p>

        <label htmlFor="console-password" className="block font-ui text-[13px] text-ink-muted">
          Operator password
        </label>
        <input
          id="console-password"
          type="password"
          autoComplete="current-password"
          autoFocus
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mt-1 w-full border border-rule bg-ground-sunk px-2 py-1.5 font-data text-[13px] outline-none focus:border-rule-strong"
        />

        {error && (
          <p className="mt-3 bg-warn-ground px-2 py-1 font-data text-[12px] text-warn">{error}</p>
        )}

        <button
          type="submit"
          disabled={busy || password.length === 0}
          className="mt-4 w-full border border-rule-strong px-2 py-1.5 font-ui text-[13px] hover:bg-ground-sunk disabled:opacity-40"
        >
          {busy ? "…" : "Sign in"}
        </button>

        <p className="mt-4 font-data text-[11px] text-ink-faint">
          This console shows CPO commercial terms and our own spend. Sessions last 12 hours.
        </p>
      </form>
    </div>
  );
}
