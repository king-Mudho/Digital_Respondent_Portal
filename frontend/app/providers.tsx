"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError } from "@/lib/api/client";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // The library defaults treat data as stale at once, so every
            // return to the tab refetched every query on the page. Thirty
            // seconds keeps screens current without the churn on a shared,
            // single-CPU server and on respondents' mobile data.
            staleTime: 30_000,
            // A 4xx is a definite answer (not permitted, not found, not set
            // up) -- retrying it three times only delayed the message.
            retry: (failureCount, error) =>
              !(error instanceof ApiError && error.status >= 400 && error.status < 500) && failureCount < 2,
          },
        },
      }),
  );
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
