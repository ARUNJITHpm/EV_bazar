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
 * The public assessment flow, built to the design (design/flow-images/).
 *
 * Four counted steps — locate · transformer · space · intent — then working
 * and result. The transformer step nests two sliders (distance, then size)
 * that stay inside 02 / 04, exactly as the artboards number them. Every step
 * is a real URL under /assess, so the browser back button works for free and
 * a link into the middle of the flow resolves; the answers live in
 * sessionStorage, so a refresh loses nothing.
 *
 * The design's inputs are WIRED FOR REAL (owner's call, design/DECISIONS.md
 * Task 3): space drives the connector count and moves breakeven; the
 * transformer's size and distance move capex, so their echoes say "payback,
 * not this breakeven" — the honesty firewall, unbroken. Intent feeds the
 * operator match, never the arithmetic, and its echo owns that.
 */

type StepId =
  "locate" | "transformer" | "distance" | "size" | "land" | "intent" | "working" | "result";

/** Total over StepId, so the chrome can never index its way to undefined.
 *  distance and size are sub-steps of the transformer question, so they hold
 *  02 / 04 — the customer is still answering "the transformer question". */
const STEP_META: Record<StepId, { label: string; progress: number }> = {
  locate: { label: "01 / 04", progress: 25 },
  transformer: { label: "02 / 04", progress: 50 },
  distance: { label: "02 / 04", progress: 50 },
  size: { label: "02 / 04", progress: 50 },
  land: { label: "03 / 04", progress: 75 },
  intent: { label: "04 / 04", progress: 100 },
  working: { label: "WORKING", progress: 100 },
  result: { label: "RESULT", progress: 100 },
};

const isStep = (v: string): v is StepId => v in STEP_META;

const BACK_LABEL: Partial<Record<StepId, string>> = {
  distance: "Back to the transformer question",
  size: "Back to the distance",
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
              // the answer — do not march them through four questions we
              // are only going to decline to answer.
              if (out.waitlisted) {
                setState((s) => ({ ...s, result: out }));
                go("result");
              } else {
                go("transformer");
              }
            }}
          />
        );

      case "transformer":
        return (
          <Screen question="Is there a transformer near this site?">
            <Answers>
              <Answer
                title="Yes, I know the details"
                sub="You will enter the distance and the capacity next. Two questions, no forms."
                onClick={() => {
                  set({ transformerNear: "yes" });
                  go("distance");
                }}
              />
              <Answer
                title="Not sure — skip this"
                sub="Most owners do not know. We will estimate it from the grid records instead."
                onClick={() => {
                  set({ transformerNear: "skip", transformerDistanceM: "skip", transformerKva: "skip" });
                  go("land");
                }}
              />
            </Answers>
            <Aside>
              Skipping widens the range on the estimate. It does not stop the assessment, and the
              report will mark the figure unverified.
            </Aside>
          </Screen>
        );

      case "distance":
        return (
          <Screen question="How far is the transformer from the site?">
            <Slider
              id="transformer-distance"
              label="Distance from the site"
              unit="m"
              min={0}
              max={500}
              step={10}
              value={
                typeof state.answers.transformerDistanceM === "number"
                  ? state.answers.transformerDistanceM
                  : 120
              }
              onChange={(v) => set({ transformerDistanceM: v })}
            />
            <Aside>
              The cabling run from the transformer to the site is priced at ₹2,000 a metre. It moves
              the full report’s payback, not the breakeven figure on the last screen.
            </Aside>
            <StepFooter
              skipLabel="I am not sure — skip this one"
              onSkip={() => {
                set({ transformerDistanceM: "skip" });
                go("size");
              }}
              onNext={() => {
                if (typeof state.answers.transformerDistanceM !== "number")
                  set({ transformerDistanceM: 120 });
                go("size");
              }}
            />
          </Screen>
        );

      case "size":
        return (
          <Screen question="How big is it?">
            <Slider
              id="transformer-capacity"
              label="Transformer capacity"
              unit="kVA"
              min={25}
              max={1000}
              step={25}
              value={
                typeof state.answers.transformerKva === "number" ? state.answers.transformerKva : 250
              }
              onChange={(v) => set({ transformerKva: v })}
            />
            <Aside>
              If the transformer already covers the station’s managed-peak load, a new one does not
              have to be built — that lowers the capital cost, and so the payback, not the breakeven
              figure.
            </Aside>
            <StepFooter
              skipLabel="I am not sure — skip this one"
              onSkip={() => {
                set({ transformerKva: "skip" });
                go("land");
              }}
              onNext={() => {
                if (typeof state.answers.transformerKva !== "number") set({ transformerKva: 250 });
                go("land");
              }}
            />
          </Screen>
        );

      case "land":
        return (
          <Screen question="How much space do you have?">
            <Answers cols={3}>
              <Answer
                title="A couple of car parks"
                sub="Room for two or three vehicles to charge at once."
                onClick={() => {
                  set({ space: "small" });
                  go("intent");
                }}
              />
              <Answer
                title="A corner of a plot or yard"
                sub="Room for four to eight, with space to turn in and out."
                onClick={() => {
                  set({ space: "medium" });
                  go("intent");
                }}
              />
              <Answer
                title="An open site"
                sub="Room for a full station, a canopy and queueing."
                onClick={() => {
                  set({ space: "large" });
                  go("intent");
                }}
              />
            </Answers>
            <Aside>
              A rough answer is enough. We measure the plot properly during the site survey — more
              plugs spread the fixed costs, which is the one answer here that moves the breakeven
              number.
            </Aside>
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
          className="inline-flex min-h-[44px] items-center font-cw-mono text-[clamp(18px,1.6vw,21px)] font-medium tracking-[0.08em] text-cw-text uppercase"
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

      {/* The background map suppresses its own attribution control, so the
          footer carries it: Mapbox renders the style, OSM supplies the data. */}
      {!bare && (
        <div className="relative z-10 flex justify-end gap-4 px-[clamp(24px,7vw,112px)] pb-[18px] text-[13px] text-cw-muted">
          <a
            href="https://www.mapbox.com/about/maps/"
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex min-h-[44px] items-center text-[13px] transition-colors duration-200 hover:text-cw-text"
          >
            © Mapbox
          </a>
          <a
            href="https://www.openstreetmap.org/copyright"
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex min-h-[44px] items-center text-[13px] transition-colors duration-200 hover:text-cw-text"
          >
            © OpenStreetMap
          </a>
        </div>
      )}
    </div>
  );
}

export type { AssessOut };
