import createClient from "openapi-fetch";

import type { paths } from "./schema";

/**
 * Typed client for app/api/internal.
 *
 * `paths` is generated from FastAPI's OpenAPI output (npm run api:generate)
 * and CI fails if the committed copy is stale. A renamed backend field
 * becomes a TypeScript error here rather than an `undefined` where a rupee
 * figure should be (AGENTS.md).
 */

/**
 * Only the internal surface is reachable from this client.
 *
 * `/api/v1` is a contract with CPO partners. Our SPA calling it would mean a
 * console tweak could pressure a partner-facing payload into changing shape.
 * Narrowing the type here makes that a compile error rather than a rule
 * somebody has to remember (STACK.md §2).
 */
type InternalPaths = Pick<paths, Extract<keyof paths, `/api/internal/${string}`>>;

export const api = createClient<InternalPaths>({
  credentials: "include", // console session cookie
});
