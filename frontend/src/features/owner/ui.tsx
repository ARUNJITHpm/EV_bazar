import { useEffect, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../api/client";

import { clearPrivateGridCache } from "./grid-cache";

export const inputCls =
  "min-h-[56px] w-full border border-cw-line bg-cw-surface px-5 text-[18px] text-cw-text placeholder:text-cw-muted focus:border-cw-slate focus:outline-none";

export const primaryCls =
  "inline-flex min-h-[58px] items-center justify-center bg-cw-accent px-7 text-[17px] font-semibold text-cw-ground transition-[filter] duration-200 hover:brightness-107 disabled:cursor-not-allowed disabled:opacity-40";

export const secondaryCls =
  "inline-flex min-h-[56px] items-center justify-center border border-cw-line bg-cw-surface px-6 text-[17px] text-cw-text transition-colors duration-200 hover:border-cw-slate";

export const choiceCls = (on: boolean) =>
  `flex min-h-[56px] flex-col gap-1 border p-5 text-left transition-colors duration-200 ${
    on ? "border-cw-accent bg-cw-surface-2" : "border-cw-line bg-cw-surface hover:border-cw-slate"
  }`;

export const WHOLE = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
export const ONE = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 1 });

/** Who is signed in, or ``undefined`` while loading / when nobody is. */
export function useOwner() {
  return useQuery({
    queryKey: ["owner-me"],
    retry: false,
    staleTime: 60_000,
    queryFn: async () => {
      const { data } = await api.GET("/api/internal/owner/me");
      return data ?? null;
    },
  });
}

/** The page frame: header (with the masked number and sign-out), progress, body. */
export function Shell({
  children,
  progress,
  back,
}: {
  children: ReactNode;
  progress?: { at: number; of: number };
  back?: () => void;
}) {
  const me = useOwner();
  const navigate = useNavigate();
  const client = useQueryClient();
  const signOut = async () => {
    await api.POST("/api/internal/owner/logout");
    await clearPrivateGridCache(client);
    client.setQueryData(["owner-me"], null);
    navigate("/owner", { replace: true });
  };
  return (
    <div className="cw-surface-root relative flex min-h-dvh flex-col bg-cw-ground font-cw-sans text-[17px] leading-[1.6] text-cw-text antialiased">
      <header className="flex items-center justify-between gap-6 px-[clamp(24px,7vw,112px)] py-5">
        <Link
          to="/"
          className="inline-flex min-h-[44px] items-center font-cw-mono text-[clamp(18px,1.6vw,21px)] font-medium tracking-[0.08em] text-cw-text uppercase"
        >
          Chargeworthy
        </Link>
        <span className="flex items-center gap-5 font-cw-mono text-[14px] tracking-[0.04em] text-cw-muted">
          {progress && (
            <span className="tracking-[0.08em]">
              {String(progress.at).padStart(2, "0")} / {String(progress.of).padStart(2, "0")}
            </span>
          )}
          {me.data && (
            <>
              <span className="tabular-nums">{me.data.phone_masked}</span>
              <button
                type="button"
                onClick={() => void signOut()}
                className="inline-flex min-h-[44px] items-center text-cw-slate"
              >
                Sign out
              </button>
            </>
          )}
        </span>
      </header>
      {progress && (
        <div className="h-0.5 bg-cw-line">
          <div
            className="h-0.5 bg-cw-slate transition-[width] duration-[420ms] ease-(--cw-ease)"
            style={{ width: `${Math.min((progress.at / progress.of) * 100, 100)}%` }}
          />
        </div>
      )}
      {back && (
        <div className="px-[clamp(24px,7vw,112px)] pt-3.5">
          <button
            type="button"
            onClick={back}
            className="inline-flex min-h-[56px] items-center px-1 text-[17px] text-cw-muted transition-colors duration-200 hover:text-cw-text"
          >
            ← Back
          </button>
        </div>
      )}
      <main className="flex flex-grow flex-col px-[clamp(24px,7vw,112px)] pt-[clamp(24px,5vw,56px)] pb-[clamp(96px,10vw,120px)]">
        {children}
      </main>
    </div>
  );
}

/** Redirects to sign-in when nobody is signed in. */
export function useRequireOwner() {
  const me = useOwner();
  const navigate = useNavigate();
  useEffect(() => {
    if (!me.isPending && me.data === null) navigate("/owner", { replace: true });
  }, [me.isPending, me.data, navigate]);
  return me;
}

export function Card({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-4 border border-cw-line bg-cw-surface p-6 sm:p-8">
      {title && (
        <h2 className="font-cw-mono text-[14px] tracking-[0.12em] text-cw-muted uppercase">
          {title}
        </h2>
      )}
      {children}
    </section>
  );
}

export function Field({
  id,
  label,
  hint,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="text-[17px] font-medium">
        {label}
      </label>
      {hint && <span className="text-[15px] text-cw-muted">{hint}</span>}
      {children}
    </div>
  );
}
