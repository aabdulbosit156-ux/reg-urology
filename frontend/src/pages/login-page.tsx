import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { Button } from "@/components/base/buttons/button";
import { Input } from "@/components/base/input/input";
import { ApiError } from "@/lib/api-client";
import { useAuth } from "@/providers/auth-provider";

export const LoginPage = () => {
    const { loginWithPassword, loginWithTelegram } = useAuth();
    const navigate = useNavigate();

    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isTelegramChecking, setIsTelegramChecking] = useState(true);

    useEffect(() => {
        const initData = window.Telegram?.WebApp?.initData;
        if (!initData) {
            setIsTelegramChecking(false);
            return;
        }
        loginWithTelegram(initData)
            .then(() => navigate("/patients", { replace: true }))
            .catch(() => setIsTelegramChecking(false));
    }, [loginWithTelegram, navigate]);

    const handleSubmit = async (event: FormEvent) => {
        event.preventDefault();
        setError(null);
        setIsSubmitting(true);
        try {
            await loginWithPassword(username, password);
            navigate("/patients", { replace: true });
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

                <form className="mt-6 flex flex-col gap-4" onSubmit={handleSubmit}>
                    <Input label="Login" value={username} onChange={setUsername} isRequired autoFocus />
                    <Input label="Parol" type="password" value={password} onChange={setPassword} isRequired />
                    {error && <p className="text-sm text-error-primary">{error}</p>}
                    <Button type="submit" size="lg" isLoading={isSubmitting} isDisabled={!username || !password}>
                        Kirish
                    </Button>
                </form>
            </div>
        </div>
    );
};
