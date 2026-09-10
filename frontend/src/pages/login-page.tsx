import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { HeartHand, Send01 } from "@untitledui/icons";
import { useNavigate } from "react-router";
import { Button } from "@/components/base/buttons/button";
import { Input } from "@/components/base/input/input";
import { FeaturedIcon } from "@/components/foundations/featured-icon/featured-icon";
import { ApiError, api } from "@/lib/api-client";
import { useAuth } from "@/providers/auth-provider";
import type { LoginTokenStart, LoginTokenStatus } from "@/types/settings";

const API_BASE = import.meta.env.VITE_API_URL ?? "/api";
const POLL_MS = 2500;

export const LoginPage = () => {
    const { loginWithPassword, loginWithTelegram, applyAccessToken } = useAuth();
    const navigate = useNavigate();

    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isTelegramChecking, setIsTelegramChecking] = useState(true);
    const [showDevLogin, setShowDevLogin] = useState(false);

    const [session, setSession] = useState<LoginTokenStart | null>(null);
    const [tgError, setTgError] = useState<string | null>(null);
    const [isStarting, setIsStarting] = useState(false);
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

    // Auto-login when opened inside the Telegram WebApp (from the bot's "Admin panel" button).
    useEffect(() => {
        const initData = window.Telegram?.WebApp?.initData;
        if (!initData) {
            setIsTelegramChecking(false);
            return;
        }
        loginWithTelegram(initData)
            .then(() => navigate("/dashboard", { replace: true }))
            .catch(() => setIsTelegramChecking(false));
    }, [loginWithTelegram, navigate]);

    const stopPolling = useCallback(() => {
        if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
        }
    }, []);

    useEffect(() => stopPolling, [stopPolling]);

    const startTelegramLogin = async () => {
        setTgError(null);
        setIsStarting(true);
        try {
            const result = await api.post<LoginTokenStart>("/auth/staff/login/start");
            setSession(result);
            stopPolling();
            pollRef.current = setInterval(async () => {
                try {
                    const status = await api.get<LoginTokenStatus>(`/auth/staff/login/${result.token}`);
                    if (status.status === "confirmed" && status.access_token) {
                        stopPolling();
                        await applyAccessToken(status.access_token);
                        navigate("/dashboard", { replace: true });
                    } else if (status.status === "expired") {
                        stopPolling();
                        setSession(null);
                        setTgError("Havola muddati tugadi. Qaytadan urinib ko'ring.");
                    }
                } catch {
                    // transient poll error — keep trying
                }
            }, POLL_MS);
        } catch (err) {
            setTgError(err instanceof ApiError ? err.message : "Telegram orqali kirishda xatolik");
        } finally {
            setIsStarting(false);
        }
    };

    const handleSubmit = async (event: FormEvent) => {
        event.preventDefault();
        setError(null);
        setIsSubmitting(true);
        try {
            await loginWithPassword(username, password);
            navigate("/dashboard", { replace: true });
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "Kirishda xatolik yuz berdi");
        } finally {
            setIsSubmitting(false);
        }
    };

    if (isTelegramChecking) {
        return (
            <div className="flex min-h-dvh items-center justify-center bg-primary text-sm text-tertiary">
                Yuklanmoqda...
            </div>
        );
    }

    return (
        <div className="flex min-h-dvh flex-col items-center justify-center bg-secondary px-4 py-10">
            <div className="w-full max-w-sm">
                <div className="flex flex-col items-center text-center">
                    <FeaturedIcon icon={HeartHand} color="brand" theme="light" size="xl" />
                    <h1 className="mt-5 text-2xl font-semibold text-primary">
                        Reg<span className="text-brand-secondary">Urolog</span>
                    </h1>
                    <p className="mt-1 text-sm text-tertiary">Boshqaruv paneliga xush kelibsiz</p>
                </div>

                <div className="mt-8 rounded-2xl bg-primary p-6 shadow-sm ring-1 ring-secondary sm:p-8">
                    {session ? (
                        <div className="flex flex-col items-center gap-4">
                            <p className="text-center text-sm font-medium text-secondary">
                                Telegram orqali tasdiqlang
                            </p>
                            <img
                                src={`${API_BASE}/auth/staff/login/${session.token}/qr`}
                                alt="QR kod"
                                className="size-44 rounded-lg bg-white p-2 ring-1 ring-secondary"
                            />
                            <p className="text-center text-xs text-tertiary">
                                QR kodни skaner qiling yoki quyidagi tugmani bosing. Botда tasdiqlagach, panel
                                avtomatik ochiladi.
                            </p>
                            <Button href={session.deep_link} target="_blank" rel="noreferrer" size="lg" iconLeading={Send01} className="w-full">
                                Telegramda ochish
                            </Button>
                            <div className="flex items-center gap-2 text-xs text-quaternary">
                                <span className="size-1.5 animate-pulse rounded-full bg-brand-solid" />
                                Tasdiqlash kutilmoqda...
                            </div>
                            {tgError && <p className="text-center text-sm text-error-primary">{tgError}</p>}
                            <button
                                type="button"
                                onClick={() => {
                                    stopPolling();
                                    setSession(null);
                                }}
                                className="cursor-pointer text-xs text-tertiary underline outline-focus-ring hover:text-secondary"
                            >
                                Bekor qilish
                            </button>
                        </div>
                    ) : (
                        <>
                            <Button
                                size="lg"
                                iconLeading={Send01}
                                className="w-full"
                                isLoading={isStarting}
                                onClick={startTelegramLogin}
                            >
                                Telegram orqali kirish
                            </Button>
                            <p className="mt-3 text-center text-xs text-quaternary">
                                Xodimlar botда ro'yxatdan o'tgan Telegram akkaunti bilan kiradilar.
                            </p>
                            {tgError && <p className="mt-3 text-center text-sm text-error-primary">{tgError}</p>}

                            <div className="my-6 flex items-center gap-3">
                                <span className="h-px flex-1 bg-border-secondary" />
                                <span className="text-xs font-medium text-quaternary">yoki</span>
                                <span className="h-px flex-1 bg-border-secondary" />
                            </div>

                            {showDevLogin ? (
                                <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
                                    <Input label="Login" value={username} onChange={setUsername} isRequired autoFocus />
                                    <Input label="Parol" type="password" value={password} onChange={setPassword} isRequired />
                                    {error && <p className="text-sm text-error-primary">{error}</p>}
                                    <Button type="submit" size="lg" color="secondary" isLoading={isSubmitting} isDisabled={!username || !password}>
                                        Kirish
                                    </Button>
                                </form>
                            ) : (
                                <button
                                    type="button"
                                    onClick={() => setShowDevLogin(true)}
                                    className="mx-auto block cursor-pointer text-sm text-tertiary underline outline-focus-ring hover:text-secondary"
                                >
                                    Dev sifatida login/parol bilan kirish
                                </button>
                            )}
                        </>
                    )}
                </div>

                <p className="mt-6 text-center text-xs text-quaternary">Dr. Sardor urologiya klinikasi</p>
            </div>
        </div>
    );
};
