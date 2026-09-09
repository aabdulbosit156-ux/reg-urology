import { useEffect, useState } from "react";
import { Button } from "@/components/base/buttons/button";
import { Input } from "@/components/base/input/input";
import { ApiError, api } from "@/lib/api-client";
import type { ScheduleSettings } from "@/types/settings";

export const ScheduleSettingsCard = () => {
    const [form, setForm] = useState<ScheduleSettings | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState(false);

    useEffect(() => {
        api.get<ScheduleSettings>("/settings/schedule")
            .then(setForm)
            .catch((err) => setError(err instanceof ApiError ? err.message : "Yuklashda xatolik"))
            .finally(() => setIsLoading(false));
    }, []);

    const handleSave = async () => {
        if (!form) return;
        setIsSaving(true);
        setError(null);
        setSuccess(false);
        try {
            const result = await api.patch<ScheduleSettings>("/settings/schedule", form);
            setForm(result);
            setSuccess(true);
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "Saqlashda xatolik");
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <section className="rounded-xl border border-secondary bg-primary p-5">
            <h2 className="text-sm font-semibold text-primary">Ish vaqti</h2>
            <p className="mt-1 text-sm text-tertiary">Kalendardagi qabul slotlari shu oraliqqa qarab hisoblanadi.</p>

            {isLoading ? (
                <p className="mt-4 text-sm text-tertiary">Yuklanmoqda...</p>
            ) : form ? (
                <div className="mt-4 flex flex-col gap-4 sm:flex-row">
                    <Input
                        label="Boshlanish vaqti"
                        type="time"
                        value={form.work_start.slice(0, 5)}
                        onChange={(value) => setForm({ ...form, work_start: value })}
                    />
                    <Input
                        label="Tugash vaqti"
                        type="time"
                        value={form.work_end.slice(0, 5)}
                        onChange={(value) => setForm({ ...form, work_end: value })}
                    />
                    <Input
                        label="Slot davomiyligi (daqiqa)"
                        type="number"
                        value={String(form.slot_minutes)}
                        onChange={(value) => setForm({ ...form, slot_minutes: Number(value) || 0 })}
                    />
                </div>
            ) : null}

            {error && <p className="mt-3 text-sm text-error-primary">{error}</p>}
            {success && <p className="mt-3 text-sm text-success-primary">Saqlandi</p>}

            <div className="mt-4 flex justify-end">
                <Button onClick={handleSave} isLoading={isSaving} isDisabled={!form}>
                    Saqlash
                </Button>
            </div>
        </section>
    );
};
