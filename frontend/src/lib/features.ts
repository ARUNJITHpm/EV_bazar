import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";

/**
 * Deferred features the backend has switched on.
 *
 * Status scraping (charger status polled from CPO apps) is a later stage, so
 * ``scraperEnabled`` is false unless the server was started with SCRAPER_ENABLED.
 * While the answer is loading, or if it cannot be fetched, it is false: a
 * deferred feature never appears by accident.
 */
export function useFeatures(): { scraperEnabled: boolean } {
  const q = useQuery({
    queryKey: ["features"],
    staleTime: 5 * 60_000,
    queryFn: async () => (await api.GET("/api/internal/features")).data ?? null,
  });
  return { scraperEnabled: q.data?.scraper_enabled === true };
}
