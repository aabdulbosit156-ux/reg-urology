import { ApiClientError, apiError, cookieValue } from "./client";

export { ApiClientError } from "./client";

export interface AuthSession {
  principal: {
    kind: "root" | "staff";
    role: "DEV" | "DIRECTOR" | "ADMIN";
    staff_id?: string | null;
    full_name?: string | null;
  };
  expires_at: string;
  csrf_token: string | null;
}

export interface LoginChallenge {
  state: string;
  matching_code: string;
  expires_at: string;
  deep_link?: string | null;
  qr_data_url?: string | null;
}

export async function getCurrentSession(): Promise<AuthSession | null> {
  const response = await fetch("/api/v1/auth/me", {
    credentials: "same-origin",
    headers: { Accept: "application/json" },
  });
  if (response.status === 401) return null;
  if (!response.ok) throw await apiError(response);
  return (await response.json()) as AuthSession;
}

export async function rootLogin(token: string): Promise<AuthSession> {
  const response = await fetch("/api/v1/auth/root", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ token }),
  });
  if (!response.ok) throw await apiError(response);
  return (await response.json()) as AuthSession;
}

export async function rootLogout(): Promise<void> {
  const csrfToken = cookieValue("regurolog_csrf");
  if (!csrfToken) {
    throw new ApiClientError(
      "Sessiya xavfsizlik tokeni topilmadi. Sahifani yangilang",
      403,
      "CSRF_MISSING",
    );
  }
  const response = await fetch("/api/v1/auth/logout", {
    method: "POST",
    credentials: "same-origin",
    headers: { Accept: "application/json", "X-CSRF-Token": csrfToken },
  });
  if (!response.ok) throw await apiError(response);
}

export async function createStaffChallenge(): Promise<LoginChallenge> {
  const response = await fetch("/api/v1/auth/challenges", {
    method: "POST",
    credentials: "same-origin",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw await apiError(response);
  return (await response.json()) as LoginChallenge;
}

export async function getStaffChallenge(): Promise<LoginChallenge> {
  const response = await fetch("/api/v1/auth/challenges/current", {
    credentials: "same-origin",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw await apiError(response);
  return (await response.json()) as LoginChallenge;
}

export async function exchangeStaffChallenge(): Promise<AuthSession> {
  const response = await fetch("/api/v1/auth/exchange", {
    method: "POST",
    credentials: "same-origin",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw await apiError(response);
  return (await response.json()) as AuthSession;
}
