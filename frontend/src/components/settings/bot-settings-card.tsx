import { useEffect, useState } from "react";
import { Button } from "@/components/base/buttons/button";
import { Input } from "@/components/base/input/input";
import { ApiError, api } from "@/lib/api-client";
import type { BotSettings } from "@/types/settings";

export const BotSettingsCard = () => {
    const [settings, setSettings] = useState<BotSettings | null>(null);
    const [token, setToken] = useState("");
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState(false);

    useEffect(() => {
        api.get<BotSettings>("/settings/bot")
            .then(setSettings)
            .catch((err) => setError(err instanceof ApiError ? err.message : "Yuklashda xatolik"))
            .finally(() => setIsLoading(false));
    }, []);

    const handleSave = async () => {
        if (!token.trim()) return;
        setIsSaving(true);
        setError(null);
        setSuccess(false);
        try {
            const result = await api.patch<BotSettings>("/settings/bot", { bot_token: token.trim() });
            setSettings(result);
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
            <h2 className="text-sm font-semibold text-primary">Telegram bot</h2>
            <p className="mt-1 text-sm text-tertiary">
                {isLoading
                    ? "Tekshirilmoqda..."
                    : settings?.bot_username
                      ? `Bot: @${settings.bot_username} · Holat: ${settings.bot_token_configured ? "sozlangan" : "sozlanmagan"}`
                      : `Holat: ${settings?.bot_token_configured ? "sozlangan" : "sozlanmagan"}`}
            </p>

            <div className="mt-4 max-w-md">
                <Input label="Yangi bot tokeni" type="password" placeholder="123456:ABC-DEF..." value={token} onChange={setToken} />
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
