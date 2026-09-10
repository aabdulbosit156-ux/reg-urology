import { createContext, useContext, useEffect, useMemo, useState, type PropsWithChildren } from "react";
import { api, setUnauthorizedHandler } from "@/lib/api-client";
import { clearToken, getToken, setToken } from "@/lib/auth-storage";

export type StaffRole = "dev" | "director" | "admin" | "analyst";

export interface Me {
    sub: string;
    role: StaffRole;
    full_name: string | null;
}

interface TokenResponse {
    access_token: string;
    role: StaffRole;
    expires_in: number;
}

export interface TelegramLoginData {
    id: number;
    auth_date: number;
    hash: string;
    first_name?: string;
    last_name?: string;
    username?: string;
    photo_url?: string;
}

interface AuthContextValue {
    isLoading: boolean;
    me: Me | null;
    loginWithPassword: (username: string, password: string) => Promise<void>;
    loginWithTelegram: (initData: string) => Promise<void>;
    loginWithTelegramWidget: (data: TelegramLoginData) => Promise<void>;
    logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export const AuthProvider = ({ children }: PropsWithChildren) => {
    const [me, setMe] = useState<Me | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const logout = () => setMe(null);
        setUnauthorizedHandler(logout);
        return () => setUnauthorizedHandler(null);
    }, []);

    useEffect(() => {
        const token = getToken();
        if (!token) {
            setIsLoading(false);
            return;
        }
        api.get<Me>("/auth/me")
            .then(setMe)
            .catch(() => clearToken())
            .finally(() => setIsLoading(false));
    }, []);

    const applyToken = async (result: TokenResponse) => {
        setToken(result.access_token);
        const meResult = await api.get<Me>("/auth/me");
        setMe(meResult);
    };

    const loginWithPassword = async (username: string, password: string) => {
        const result = await api.post<TokenResponse>("/auth/dev-login", { username, password });
        await applyToken(result);
    };

    const loginWithTelegram = async (initData: string) => {
        const result = await api.post<TokenResponse>("/auth/staff/webapp-login", { init_data: initData });
        await applyToken(result);
    };

    const loginWithTelegramWidget = async (data: TelegramLoginData) => {
        const result = await api.post<TokenResponse>("/auth/staff/telegram-login", data);
        await applyToken(result);
    };

    const logout = () => {
        clearToken();
        setMe(null);
    };

    const value = useMemo(
        () => ({ isLoading, me, loginWithPassword, loginWithTelegram, loginWithTelegramWidget, logout }),
        [isLoading, me],
    );

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export function useAuth(): AuthContextValue {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error("useAuth must be used within AuthProvider");
    return ctx;
}
