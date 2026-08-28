import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import "./styles.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Near-real-time: refresh on tab focus / reconnect and poll periodically so
      // changes made elsewhere (other staff, the bot) show up without a manual reload.
      refetchOnWindowFocus: true,
      refetchOnReconnect: true,
      refetchInterval: 20_000,
      retry: 1,
      staleTime: 10_000,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);
