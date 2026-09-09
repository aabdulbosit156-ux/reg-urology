import { useEffect, useState } from "react";
import { Button } from "@/components/base/buttons/button";
import { Input } from "@/components/base/input/input";
import { ApiError, api } from "@/lib/api-client";
import type { AISettings } from "@/types/settings";

export const AiSettingsCard = () => {
    const [configured, setConfigured] = useState(false);
    const [token, setToken] = useState("");
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState(false);

    useEffect(() => {
        api.get<AISettings>("/settings/ai")
            .then((result) => setConfigured(result.ai_token_configured))
            .catch((err) => setError(err instanceof ApiError ? err.message : "Yuklashda xatolik"))
            .finally(() => setIsLoading(false));
    }, []);

    const handleSave = async () => {
        if (!token.trim()) return;
        setIsSaving(true);
        setError(null);
        setSuccess(false);
        try {
            const result = await api.patch<AISettings>("/settings/ai", { ai_token: token.trim() });
            setConfigured(result.ai_token_configured);
            setToken("");
            setSuccess(true);
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "Saqlashda xatolik");
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <section className="rounded-xl border border-secondary bg-primary p-5">
            <h2 className="text-sm font-semibold text-primary">AI (OpenAI) tokeni</h2>
            <p className="mt-1 text-sm text-tertiary">
                Analiz natijalarini AI orqali tahlil qilish uchun ishlatiladi. Holat:{" "}
                {isLoading ? "tekshirilmoqda..." : configured ? "sozlangan" : "sozlanmagan"}.
            </p>

            <div className="mt-4 max-w-md">
                <Input
                    label="Yangi API kalit"
                    type="password"
                    placeholder="sk-..."
                    value={token}
                    onChange={setToken}
                />
            </div>

            {error && <p className="mt-3 text-sm text-error-primary">{error}</p>}
            {success && <p className="mt-3 text-sm text-success-primary">Saqlandi</p>}

            <div className="mt-4 flex justify-end">
                <Button onClick={handleSave} isLoading={isSaving} isDisabled={!token.trim()}>
                    Saqlash
                </Button>
            </div>
        </section>
    );
};
