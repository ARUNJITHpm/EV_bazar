import type { QueryClient } from "@tanstack/react-query";

const pending = new Set<AbortController>();

export function startPrivateGridRequest() {
  const controller = new AbortController();
  pending.add(controller);
  return controller;
}

export function finishPrivateGridRequest(controller: AbortController) {
  pending.delete(controller);
}

export async function clearPrivateGridCache(client: QueryClient) {
  for (const controller of pending) controller.abort();
  pending.clear();
  const filters = {
    predicate: (query: { queryKey: readonly unknown[] }) =>
      query.queryKey[0] === "owner-grid" || query.queryKey[0] === "owner-area",
  };
  await client.cancelQueries(filters);
  client.removeQueries(filters);
}
