import { useEffect, useRef, useState, type FormEvent } from "react";
import { HeartHand } from "@untitledui/icons";
import { useNavigate } from "react-router";
import { Button } from "@/components/base/buttons/button";
import { Input } from "@/components/base/input/input";
import { FeaturedIcon } from "@/components/foundations/featured-icon/featured-icon";
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
        script.setAttribute("data-radius", "10");
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
                    <p className="text-center text-sm font-medium text-secondary">Telegram orqali kiring</p>

                    {TELEGRAM_BOT ? (
                        <div ref={widgetRef} className="mt-4 flex min-h-[48px] justify-center" />
                    ) : (
                        <p className="mt-4 rounded-lg bg-secondary px-3 py-2.5 text-center text-xs text-tertiary">
                            Botdagi «🖥 Admin panel» tugmasi orqali kiring.
                        </p>
                    )}

                    {tgError && <p className="mt-3 text-center text-sm text-error-primary">{tgError}</p>}

                    <p className="mt-4 text-center text-xs text-quaternary">
                        Xodimlar botda ro'yxatdan o'tgan Telegram akkaunti bilan kiradilar.
                    </p>

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
                            <Button type="submit" size="lg" isLoading={isSubmitting} isDisabled={!username || !password}>
                                Kirish
                            </Button>
                        </form>
                    ) : (
                        <Button color="secondary" size="lg" className="w-full" onClick={() => setShowDevLogin(true)}>
                            Login va parol bilan kirish
                        </Button>
                    )}
                </div>

                <p className="mt-6 text-center text-xs text-quaternary">Dr. Sardor urologiya klinikasi</p>
            </div>
        </div>
    );
};
