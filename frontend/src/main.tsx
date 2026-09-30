import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot, hydrateRoot } from "react-dom/client";
import { RouterProvider } from "react-router-dom";

import { router } from "./routes";
import "./styles/index.css";

// TanStack Query owns all server state. There is no global store, because
// there is very little client state that is not server state (STACK.md §5).
const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, refetchOnWindowFocus: false } },
});

const app = (
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>
);

const root = document.getElementById("root")!;
const currentPath = window.location.pathname.replace(/\/+$/, "") || "/";
if (root.dataset.analyticsPath === currentPath) {
  hydrateRoot(root, app);
} else {
  // Unpublished paths use an honest static fallback. Mount rather than
  // hydrating a different document; registered pages hydrate their own HTML.
  createRoot(root).render(app);
}
