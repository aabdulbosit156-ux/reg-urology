import { useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { Button } from "@/components/base/buttons/button";
import { Input } from "@/components/base/input/input";
import { ApiError } from "@/lib/api-client";
import { useAuth } from "@/providers/auth-provider";

const TELEGRAM_BOT = import.meta.env.VITE_TELEGRAM_BOT;

export const LoginPage = () => {
    const { loginWithPassword, loginWithTelegram, loginWithTelegramWidget } = useAuth();
    const navigate = useNavigate();

    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState<string | null>(null);
    const [tgError, setTgError] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isTelegramChecking, setIsTelegramChecking] = useState(true);
    const [showDevLogin, setShowDevLogin] = useState(false);

    const widgetRef = useRef<HTMLDivElement>(null);

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

    // Website login via the Telegram Login Widget (normal browser).
    useEffect(() => {
        if (isTelegramChecking || !TELEGRAM_BOT || !widgetRef.current) return;

        window.onTelegramAuth = (user) => {
            setTgError(null);
            loginWithTelegramWidget(user)
                .then(() => navigate("/dashboard", { replace: true }))
                .catch((err) =>
                    setTgError(err instanceof ApiError ? err.message : "Telegram orqali kirishda xatolik"),
                );
        };

        const script = document.createElement("script");
        script.src = "https://telegram.org/js/telegram-widget.js?22";
        script.async = true;
        script.setAttribute("data-telegram-login", TELEGRAM_BOT);
        script.setAttribute("data-size", "large");
        script.setAttribute("data-radius", "8");
        script.setAttribute("data-onauth", "onTelegramAuth(user)");
        script.setAttribute("data-request-access", "write");

        const container = widgetRef.current;
        container.appendChild(script);
        return () => {
            container.innerHTML = "";
        };
    }, [isTelegramChecking, loginWithTelegramWidget, navigate]);

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
            <div className="flex min-h-screen items-center justify-center bg-primary text-sm text-tertiary">
                Yuklanmoqda...
            </div>
        );
    }

    return (
        <div className="flex min-h-screen items-center justify-center bg-secondary px-4">
            <div className="w-full max-w-sm rounded-xl bg-primary p-8 shadow-lg ring-1 ring-secondary">
                <h1 className="text-xl font-semibold text-primary">RegUrology</h1>
                <p className="mt-1 text-sm text-tertiary">Boshqaruv paneliga kirish</p>

                <div className="mt-6 flex flex-col gap-4">
                    <div>
                        <p className="mb-2 text-sm font-medium text-secondary">Telegram orqali kirish</p>
                        {TELEGRAM_BOT ? (
                            <div ref={widgetRef} className="flex justify-center" />
                        ) : (
                            <p className="text-xs text-tertiary">
                                Telegram bot sozlanmagan. Botdagi «🖥 Admin panel» tugmasi orqali kiring.
                            </p>
                        )}
                        {tgError && <p className="mt-2 text-sm text-error-primary">{tgError}</p>}
                    </div>

                    <div className="border-t border-secondary pt-4">
                        {showDevLogin ? (
                            <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
                                <Input label="Login" value={username} onChange={setUsername} isRequired autoFocus />
                                <Input label="Parol" type="password" value={password} onChange={setPassword} isRequired />
                                {error && <p className="text-sm text-error-primary">{error}</p>}
                                <Button type="submit" size="lg" isLoading={isSubmitting} isDisabled={!username || !password}>
                                    Kirish
                                </Button>
                            </form>
                        ) : (
                            <button
                                type="button"
                                onClick={() => setShowDevLogin(true)}
                                className="cursor-pointer text-sm text-tertiary underline outline-focus-ring hover:text-secondary"
                            >
                                Dev sifatida login/parol bilan kirish
                            </button>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};
