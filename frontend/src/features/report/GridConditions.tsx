import type { ReportPayload } from "./payload";

/** Stored checkable conditions only; no capacity inference from a map. */
export function GridConditions({ payload }: { payload: Pick<ReportPayload, "public_context"> }) {
  const conditions = payload.public_context?.grid_conditions ?? [];
  if (conditions.length === 0) return null;
  return (
    <div data-grid-conditions className="mt-6">
      <h3 className="font-semibold">Confirm the electricity connection</h3>
      {conditions.map((condition) => (
        <p key={condition}>
          {condition.split(/(\d+(?:\.\d+)?\s*kVA)/).map((part, index) =>
            /\d/.test(part) ? (
              <span key={index} className="font-cw-mono tabular-nums">
                {part}
              </span>
            ) : (
              part
            ),
          )}
        </p>
      ))}
      <p>
        Mapped proximity does not confirm spare capacity. Obtain written DISCOM confirmation before
        committing to the connection.
      </p>
    </div>
  );
}
