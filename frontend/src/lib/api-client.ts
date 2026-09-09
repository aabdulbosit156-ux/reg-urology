import { clearToken, getToken } from "@/lib/auth-storage";

// In dev, Vite proxies "/api" to the local backend (see vite.config.ts). In production the
// frontend and backend are separate Railway services, so VITE_API_URL points at the backend's
// public URL (e.g. https://regurolog-api.up.railway.app) and gets baked in at build time.
const API_BASE = import.meta.env.VITE_API_URL ?? "/api";

export class ApiError extends Error {
    status: number;

    constructor(status: number, message: string) {
        super(message);
        this.status = status;
    }
}

type UnauthorizedHandler = () => void;
let onUnauthorized: UnauthorizedHandler | null = null;

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
    onUnauthorized = handler;
}

interface RequestOptions extends Omit<RequestInit, "body"> {
    body?: unknown;
    isFormData?: boolean;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const { body, isFormData, headers, ...rest } = options;
    const token = getToken();

    const finalHeaders = new Headers(headers);
    if (token) finalHeaders.set("Authorization", `Bearer ${token}`);
    if (body !== undefined && !isFormData) finalHeaders.set("Content-Type", "application/json");

    const response = await fetch(`${API_BASE}${path}`, {
        ...rest,
        headers: finalHeaders,
        body: body === undefined ? undefined : isFormData ? (body as FormData) : JSON.stringify(body),
    });

    if (response.status === 401) {
        clearToken();
        onUnauthorized?.();
        throw new ApiError(401, "Not authenticated");
    }

    if (!response.ok) {
        const raw = await response.text().catch(() => response.statusText);
        let detail = raw;
        try {
            detail = JSON.parse(raw)?.detail ?? raw;
        } catch {
            // response wasn't JSON — keep the raw text
        }
        throw new ApiError(response.status, detail || response.statusText);
    }

    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
}

export const api = {
    get: <T>(path: string) => request<T>(path),
    post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
    patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body }),
    delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
    postForm: <T>(path: string, formData: FormData) =>
        request<T>(path, { method: "POST", body: formData, isFormData: true }),
};

export async function fetchBlob(path: string): Promise<Blob> {
    const token = getToken();
    const headers = new Headers();
    if (token) headers.set("Authorization", `Bearer ${token}`);

    const response = await fetch(`${API_BASE}${path}`, { headers });
    if (response.status === 401) {
        clearToken();
        onUnauthorized?.();
        throw new ApiError(401, "Not authenticated");
    }
    if (!response.ok) throw new ApiError(response.status, response.statusText);
    return response.blob();
}
