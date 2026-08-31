import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api } from "../../../api/client";
import { BackgroundMap } from "./BackgroundMap";
import { Locate } from "./Locate";
import { Answer, Answers, Aside, Screen, Slider, StepFooter } from "./Question";
import { Result } from "./Result";
import {
  clearState,
  loadState,
  saveState,
  toBody,
  type Answers as AnswerSet,
  type AssessOut,
  type FlowState,
} from "./state";
import { Working } from "./Working";

/**
 * The seven-step public assessment flow (design/, per design/DECISIONS.md).
 *
 * locate · connection (+ load) · transformer · land · intent · working ·
 * result. Every step is a real URL under /assess, so the browser back
 * button works for free and a link into the middle of the flow resolves;
 * the answers live in sessionStorage, so a refresh loses nothing.
 *
 * The question set is the ENGINE'S, not the reference build's: the flow
 * asks what compute_teaser actually reads. The reference's transformer
 * distance and capacity sliders are gone — collecting inputs the arithmetic
 * cannot use, on a product whose thesis is honesty, is theatre, and
 * "how big is the transformer" invites exactly the kVA/kW conflation
 * AGENTS.md forbids. Intent survives because it feeds the operator match
 * and its echo says so. The reasoning is in design/DECISIONS.md.
 */

type StepId =
  "locate" | "connection" | "load" | "transformer" | "land" | "intent" | "working" | "result";

/** Total over StepId, so the chrome can never index its way to undefined. */
const STEP_META: Record<StepId, { label: string; progress: number }> = {
  locate: { label: "01 / 05", progress: 20 },
  connection: { label: "02 / 05", progress: 40 },
  load: { label: "02 / 05", progress: 50 },
  transformer: { label: "03 / 05", progress: 60 },
  land: { label: "04 / 05", progress: 80 },
  intent: { label: "05 / 05", progress: 100 },
  working: { label: "WORKING", progress: 100 },
  result: { label: "RESULT", progress: 100 },
};

const isStep = (v: string): v is StepId => v in STEP_META;

const BACK_LABEL: Partial<Record<StepId, string>> = {
  load: "Back to the connection question",
  transformer: "Back to the connection question",
  land: "Back to the transformer question",
  intent: "Back to the land question",
  working: "Change an answer",
  result: "Back to my answers",
};

function Chevron() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12.5 4.5 L6.5 10 L12.5 15.5" />
    </svg>
  );
}

export function Flow() {
  const navigate = useNavigate();
  const params = useParams();
  const raw = params.step ?? "locate";
  const step: StepId = isStep(raw) ? raw : "locate";

  const [state, setState] = useState<FlowState>(loadState);
  useEffect(() => saveState(state), [state]);

  const go = useCallback((id: StepId) => navigate(`/assess/${id}`), [navigate]);
  const set = useCallback(
    (patch: Partial<AnswerSet>) => setState((s) => ({ ...s, answers: { ...s.answers, ...patch } })),
    [],
  );

  // The finishing call: the same pin, now carrying the taps. The normalised
  // key is unchanged, so this upserts the lead logged at 'Check this spot'
  // and bumps its request counter rather than creating a second row.
  const run = useCallback(async () => {
    if (!state.pin) return false;
    const { data } = await api.POST("/api/internal/assess", {
      body: toBody(state.pin, state.answers),
    });
    if (!data) return false;
    setState((s) => ({ ...s, result: data }));
    return true;
  }, [state.pin, state.answers]);

  const meta = STEP_META[step];
  const bare = step === "locate";

  // A refresh straight into a later step with nothing stored: send them back
  // to the pin rather than assessing an empty site.
  useEffect(() => {
    if (step !== "locate" && !state.pin) navigate("/assess", { replace: true });
  }, [step, state.pin, navigate]);

  const body = (() => {
    switch (step) {
      case "locate":
        return (
          <Locate
            pin={state.pin ?? null}
            onPin={(pin) => setState((s) => ({ ...s, pin, confirmed: undefined }))}
            confirmed={state.confirmed ?? null}
            onChecked={(out) => setState((s) => ({ ...s, confirmed: out }))}
            onContinue={(out) => {
              // A pin we cannot price is still a lead, and the waitlist is
              // the answer — do not march them through five questions we
              // are only going to decline to answer.
              if (out.waitlisted) {
                setState((s) => ({ ...s, result: out }));
                go("result");
              } else {
                go("connection");
              }
            }}
          />
        );

      case "connection":
        return (
          <Screen question="Does the site already have an electricity connection?">
            <Answers>
              <Answer
                title="Yes, there is one"
                sub="One more question about how much load it is sanctioned for."
                onClick={() => {
                  set({ connection: "yes" });
                  go("load");
                }}
              />
              <Answer
                title="No, it would be new"
                sub="We price a new connection into the capital cost."
                onClick={() => {
                  set({ connection: "no", kva: "skip" });
                  go("transformer");
                }}
              />
            </Answers>
            <Aside>
              <button
                type="button"
                onClick={() => {
                  set({ connection: "skip", kva: "skip" });
                  go("transformer");
                }}
                className="inline-flex min-h-[56px] items-center text-[17px] text-cw-muted underline underline-offset-4 transition-colors duration-200 hover:text-cw-text"
              >
                I don’t know this one — skip it
              </button>
            </Aside>
          </Screen>
        );

      case "load":
        return (
          <Screen question="How much load is it sanctioned for?">
            <Slider
              id="sanctioned-kva"
              label="Sanctioned load"
              unit="kVA"
              min={25}
              max={1000}
              step={25}
              value={typeof state.answers.kva === "number" ? state.answers.kva : 150}
              onChange={(v) => set({ kva: v })}
            />
            <Aside>
              This is the load your connection is sanctioned for — the figure on the bill, in kVA.
              It sets the demand charges, which is why it moves the answer.
            </Aside>
            <StepFooter
              onSkip={() => {
                set({ kva: "skip" });
                go("transformer");
              }}
              onNext={() => {
                if (typeof state.answers.kva !== "number") set({ kva: 150 });
                go("transformer");
              }}
            />
          </Screen>
        );

      case "transformer":
        return (
          <Screen question="Is there a transformer on the site itself?">
            <Answers cols={3}>
              <Answer
                title="Yes, on the site"
                sub="One less thing to build, so the capital cost drops."
                onClick={() => {
                  set({ transformer: "yes" });
                  go("land");
                }}
              />
              <Answer
                title="No, there isn’t"
                sub="A new transformer is priced into the capital cost."
                onClick={() => {
                  set({ transformer: "no" });
                  go("land");
                }}
              />
              <Answer
                title="I don’t know"
                sub="Most owners don’t. We assume one has to be built."
                onClick={() => {
                  set({ transformer: "skip" });
                  go("land");
                }}
              />
            </Answers>
            <Aside>
              Skipping does not stop the assessment. The report marks the figure unverified, and the
              answer below shows you exactly what we assumed instead.
            </Aside>
          </Screen>
        );

      case "land":
        return (
          <Screen question="Do you own the land, or lease it?">
            <Answers cols={3}>
              <Answer
                title="I own it"
                sub="No rent to cover, which lowers the bar directly."
                onClick={() => {
                  set({ land: "own" });
                  go("intent");
                }}
              />
              <Answer
                title="I lease it"
                sub="Rent stays in the running costs."
                onClick={() => {
                  set({ land: "lease" });
                  go("intent");
                }}
              />
              <Answer
                title="Not settled yet"
                sub="We assume a lease — the more cautious of the two."
                onClick={() => {
                  set({ land: "skip" });
                  go("intent");
                }}
              />
            </Answers>
          </Screen>
        );

      case "intent":
        return (
          <Screen question="What do you want this site to do?">
            <Answers cols={3}>
              <Answer
                title="Earn from land I already own"
                sub="You have the space and want it to produce an income."
                onClick={() => {
                  set({ intent: "income" });
                  go("working");
                }}
              />
              <Answer
                title="Serve my own fleet"
                sub="Vehicles you operate, charging on a predictable schedule."
                onClick={() => {
                  set({ intent: "fleet" });
                  go("working");
                }}
              />
              <Answer
                title="Serve visitors to my property"
                sub="A mall, hotel, office or apartment block where people already stop."
                onClick={() => {
                  set({ intent: "visitors" });
                  go("working");
                }}
              />
            </Answers>
            <Aside>
              This changes which operators suit you. It does not change the number on the next
              screen — that is arithmetic, and the answer will say so.
            </Aside>
          </Screen>
        );

      case "working":
        return <Working run={run} onDone={() => navigate("/assess/result", { replace: true })} />;

      case "result":
        return state.result ? (
          <Result
            out={state.result}
            onRestart={() => {
              clearState();
              setState({ answers: {} });
              navigate("/assess", { replace: true });
            }}
          />
        ) : null;
    }
  })();

  return (
    <div className="cw-surface-root relative flex min-h-dvh flex-col bg-cw-ground font-cw-sans text-[17px] leading-[1.6] text-cw-text antialiased">
      <header className="relative z-10 flex items-center justify-between gap-6 bg-cw-ground px-[clamp(24px,7vw,112px)] py-5">
        <Link
          to="/"
          className="inline-flex min-h-[44px] items-center font-cw-mono text-[16px] font-medium tracking-[0.09em] text-cw-text uppercase"
        >
          Chargeworthy
        </Link>
        <span className="font-cw-mono text-[14px] tracking-[0.08em] text-cw-muted">
          {meta.label}
        </span>
      </header>

      {/* A quiet hairline. Never a percentage in text. */}
      <div className="relative z-10 h-0.5 bg-cw-line">
        <div
          className="h-0.5 bg-cw-slate transition-[width] duration-[420ms] ease-(--cw-ease)"
          style={{ width: `${meta.progress}%` }}
        />
      </div>

      {step !== "locate" && step !== "result" && (
        <div className="relative z-10 px-[clamp(24px,7vw,112px)] pt-3.5">
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="inline-flex min-h-[56px] items-center gap-2.5 px-1 text-[17px] text-cw-muted transition-colors duration-200 hover:text-cw-text"
          >
            <Chevron />
            {BACK_LABEL[step] ?? "Back"}
          </button>
        </div>
      )}

      <div
        className={`relative z-10 flex flex-grow flex-col justify-center ${
          bare
            ? ""
            : "px-[clamp(24px,7vw,112px)] pt-[clamp(24px,5vw,56px)] pb-[clamp(48px,7vw,72px)]"
        }`}
      >
        {!bare && state.pin && <BackgroundMap pin={state.pin} />}
        {/* On the locate step the map IS the interface, so the wrapper has
            to pass the flex chain through rather than shrink-wrap it. */}
        <div className={bare ? "relative z-10 flex flex-grow flex-col" : "relative z-10"}>
          {body}
        </div>
      </div>

      {!bare && (
        <div className="relative z-10 flex justify-end px-[clamp(24px,7vw,112px)] pb-[18px] text-[13px] text-cw-muted">
          <a
            href="https://www.openstreetmap.org/copyright"
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex min-h-[44px] items-center text-[13px] transition-colors duration-200 hover:text-cw-text"
          >
            © OpenStreetMap contributors
          </a>
        </div>
      )}
    </div>
  );
}

export type { AssessOut };
