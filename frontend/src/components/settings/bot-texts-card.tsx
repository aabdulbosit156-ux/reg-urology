import { useEffect, useState } from "react";
import { Button } from "@/components/base/buttons/button";
import { TextArea } from "@/components/base/textarea/textarea";
import { ApiError, api } from "@/lib/api-client";
import type { BotTexts } from "@/types/settings";

const TEXT_LABELS: Record<string, { label: string; hint?: string }> = {
    welcome_new: { label: "Yangi bemor uchun salomlashuv" },
    welcome_returning: { label: "Qayta kelgan bemor uchun salomlashuv", hint: "{full_name} — bemor ismi bilan almashtiriladi" },
    status_new: { label: "Holat: Yangi" },
    status_scheduled: { label: "Holat: Qabulga joylangan", hint: "{when} — qabul sanasi/vaqti bilan almashtiriladi" },
    status_unreachable: { label: "Holat: Bog'lanib bo'lmadi" },
    status_advised: { label: "Holat: Maslahat berilgan" },
    status_no_show: { label: "Holat: Kelmagan" },
    status_arrived: { label: "Holat: Keldi" },
    status_analysis_ordered: { label: "Holat: Analiz buyurildi" },
    status_analysis_ready: { label: "Holat: Analiz tayyor" },
};

export const BotTextsCard = () => {
    const [texts, setTexts] = useState<Record<string, string>>({});
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState(false);

    useEffect(() => {
        api.get<BotTexts>("/settings/bot-texts")
            .then((result) => setTexts(result.texts))
            .catch((err) => setError(err instanceof ApiError ? err.message : "Yuklashda xatolik"))
            .finally(() => setIsLoading(false));
    }, []);

    const handleSave = async () => {
        setIsSaving(true);
        setError(null);
        setSuccess(false);
        try {
            const result = await api.patch<BotTexts>("/settings/bot-texts", { texts });
            setTexts(result.texts);
            setSuccess(true);
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "Saqlashda xatolik");
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <section className="rounded-xl border border-secondary bg-primary p-5">
            <h2 className="text-sm font-semibold text-primary">Bot matnlari</h2>
            <p className="mt-1 text-sm text-tertiary">Bemorlarga botda yuboriladigan xabarlar matni.</p>

            {isLoading ? (
                <p className="mt-4 text-sm text-tertiary">Yuklanmoqda...</p>
            ) : (
                <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
                    {Object.entries(TEXT_LABELS).map(([key, meta]) => (
                        <TextArea
                            key={key}
                            label={meta.label}
                            hint={meta.hint}
                            rows={2}
                            value={texts[key] ?? ""}
                            onChange={(value) => setTexts((prev) => ({ ...prev, [key]: value }))}
                        />
                    ))}
                </div>
            )}

            {error && <p className="mt-3 text-sm text-error-primary">{error}</p>}
            {success && <p className="mt-3 text-sm text-success-primary">Saqlandi</p>}

            <div className="mt-4 flex justify-end">
                <Button onClick={handleSave} isLoading={isSaving} isDisabled={isLoading}>
                    Saqlash
                </Button>
            </div>
        </section>
    );
};
