export interface ApiFieldError {
  field: string;
  message: string;
}

export interface ApiErrorResponse {
  code: string;
  message: string;
  field_errors: ApiFieldError[];
  request_id: string;
}

export interface AuthSession {
  principal: {
    kind: "root";
    role: "DEV";
  };
  expires_at: string;
  csrf_token: string | null;
}

export class ApiClientError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly requestId?: string,
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

async function apiError(response: Response): Promise<ApiClientError> {
  try {
    const payload = (await response.json()) as ApiErrorResponse;
    return new ApiClientError(payload.message, response.status, payload.code, payload.request_id);
  } catch {
    return new ApiClientError(
      "Server bilan bog‘lanishda xato yuz berdi",
      response.status,
      "UNEXPECTED_RESPONSE",
    );
  }
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

function cookieValue(name: string): string | null {
  const prefix = `${encodeURIComponent(name)}=`;
  const cookie = document.cookie.split("; ").find((item) => item.startsWith(prefix));
  return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : null;
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
