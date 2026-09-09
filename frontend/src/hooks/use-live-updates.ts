import { useEffect, useRef } from "react";
import { getToken } from "@/lib/auth-storage";

const API_BASE = import.meta.env.VITE_API_URL ?? "/api";

/** Opens an SSE connection and calls onUpdate whenever the backend broadcasts a change. */
export function useLiveUpdates(onUpdate: () => void): void {
    const callbackRef = useRef(onUpdate);
    callbackRef.current = onUpdate;

    useEffect(() => {
        const token = getToken();
        if (!token) return;

        const source = new EventSource(`${API_BASE}/events?token=${encodeURIComponent(token)}`);
        const handleUpdate = () => callbackRef.current();
        source.addEventListener("update", handleUpdate);

        return () => source.close();
    }, []);
}
