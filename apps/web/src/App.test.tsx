import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

const sessionPayload = {
  principal: { kind: "root", role: "DEV" },
  expires_at: "2026-08-26T12:00:00+00:00",
  csrf_token: null,
};

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderApp() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  );
}

function mockAuthenticatedFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/auth/me")) return jsonResponse(sessionPayload);
      if (url.endsWith("/health/live")) {
        return jsonResponse({ status: "ok", service: "regurolog-api", timezone: "Asia/Tashkent" });
      }
      if (url.includes("/analytics/cohort")) {
        return jsonResponse({
          mode: "registration_cohort",
          date_from: "2026-08-20",
          date_to: "2026-08-26",
          metrics: { inquiries: 2, contact_started: 1, answered: 1, booked: 1 },
          daily: [{ date: "2026-08-26", inquiries: 2 }],
        });
      }
      if (url.includes("/reports/no-shows")) return jsonResponse([]);
      throw new Error(`Unexpected request: ${url}`);
    }),
  );
}

describe("authenticated application shell", () => {
  beforeEach(() => localStorage.clear());

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("renders the real session and health state", async () => {
    mockAuthenticatedFetch();
    renderApp();

    expect(await screen.findByRole("heading", { name: "Boshqaruv" })).toBeInTheDocument();
    expect(await screen.findByText("API ishlayapti")).toBeInTheDocument();
    expect(screen.getByText("DEV · Root sessiya")).toBeInTheDocument();
  });

  it("opens and closes mobile navigation", async () => {
    const user = userEvent.setup();
    mockAuthenticatedFetch();
    renderApp();

    const openButton = await screen.findByRole("button", { name: "Navigatsiyani ochish" });
    const drawer = screen.getByTestId("flowbite-drawer");
    expect(drawer).toHaveClass("-translate-x-full");

    await user.click(openButton);
    await waitFor(() => expect(drawer).not.toHaveClass("-translate-x-full"));
    await user.click(screen.getByRole("button", { name: "Menyuni yopish" }));
    await waitFor(() => expect(drawer).toHaveClass("-translate-x-full"));
  });

  it("logs in without persisting the admin token in browser storage", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/auth/me")) {
        return jsonResponse(
          { code: "AUTH_REQUIRED", message: "Kirish talab qilinadi", field_errors: [], request_id: "r1" },
          401,
        );
      }
      if (url.endsWith("/auth/root")) return jsonResponse({ ...sessionPayload, csrf_token: "csrf" });
      if (url.endsWith("/health/live")) {
        return jsonResponse({ status: "ok", service: "regurolog-api", timezone: "Asia/Tashkent" });
      }
      if (url.includes("/analytics/cohort")) {
        return jsonResponse({
          mode: "registration_cohort",
          date_from: "2026-08-20",
          date_to: "2026-08-26",
          metrics: { inquiries: 0, contact_started: 0, answered: 0, booked: 0 },
          daily: [],
        });
      }
      if (url.includes("/reports/no-shows")) return jsonResponse([]);
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    renderApp();

    await user.click(await screen.findByRole("tab", { name: "Root" }));
    const tokenInput = await screen.findByLabelText("Admin token");
    await user.type(tokenInput, "test-admin-token-never-store");
    await user.click(screen.getByRole("button", { name: "Xavfsiz kirish" }));

    expect(await screen.findByRole("heading", { name: "Boshqaruv" })).toBeInTheDocument();
    expect(localStorage.length).toBe(0);
    const loginCall = fetchMock.mock.calls.find(([input]) => String(input).endsWith("/auth/root"));
    const loginOptions = loginCall?.[1];
    expect(loginOptions).toMatchObject({ method: "POST" });
    expect(JSON.parse(String(loginOptions?.body))).toEqual({
      token: "test-admin-token-never-store",
    });
  });

  it("shows the standardized API error on invalid root token", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input).endsWith("/auth/me")) {
          return jsonResponse(
            { code: "AUTH_REQUIRED", message: "Kirish talab qilinadi", field_errors: [], request_id: "r1" },
            401,
          );
        }
        return jsonResponse(
          { code: "ROOT_TOKEN_INVALID", message: "Root token noto‘g‘ri", field_errors: [], request_id: "req-42" },
          401,
        );
      }),
    );
    renderApp();

    await user.click(await screen.findByRole("tab", { name: "Root" }));
    await user.type(await screen.findByLabelText("Admin token"), "wrong");
    await user.click(screen.getByRole("button", { name: "Xavfsiz kirish" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Root token noto‘g‘ri");
    expect(screen.getByRole("alert")).toHaveTextContent("req-42");
  });
});
