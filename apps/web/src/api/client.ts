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

export async function apiError(response: Response): Promise<ApiClientError> {
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

export function cookieValue(name: string): string | null {
  const prefix = `${encodeURIComponent(name)}=`;
  const cookie = document.cookie.split("; ").find((item) => item.startsWith(prefix));
  return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : null;
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (init.method && !["GET", "HEAD"].includes(init.method.toUpperCase())) {
    const csrfToken = cookieValue("regurolog_csrf");
    if (!csrfToken) throw new ApiClientError("Xavfsizlik tokeni topilmadi", 403, "CSRF_MISSING");
    headers.set("X-CSRF-Token", csrfToken);
  }
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    credentials: "same-origin",
    headers,
  });
  if (!response.ok) throw await apiError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
