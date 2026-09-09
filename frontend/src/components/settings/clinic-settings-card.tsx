import { useEffect, useState } from "react";
import { Plus, Trash01 } from "@untitledui/icons";
import { Button } from "@/components/base/buttons/button";
import { Input } from "@/components/base/input/input";
import { ApiError, api } from "@/lib/api-client";
import type { ClinicProfile } from "@/types/settings";

interface ContactRow {
    label: string;
    value: string;
}

function contactsToRows(contacts: Record<string, string>): ContactRow[] {
    return Object.entries(contacts).map(([label, value]) => ({ label, value }));
}

function rowsToContacts(rows: ContactRow[]): Record<string, string> {
    const result: Record<string, string> = {};
    for (const row of rows) {
        if (row.label.trim()) result[row.label.trim()] = row.value;
    }
    return result;
}

export const ClinicSettingsCard = () => {
    const [name, setName] = useState("");
    const [lat, setLat] = useState("");
    const [lng, setLng] = useState("");
    const [contacts, setContacts] = useState<ContactRow[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState(false);

    useEffect(() => {
        api.get<ClinicProfile>("/settings/clinic")
            .then((result) => {
                setName(result.clinic_name ?? "");
                setLat(result.clinic_lat !== null ? String(result.clinic_lat) : "");
                setLng(result.clinic_lng !== null ? String(result.clinic_lng) : "");
                setContacts(contactsToRows(result.clinic_contacts));
            })
            .catch((err) => setError(err instanceof ApiError ? err.message : "Yuklashda xatolik"))
            .finally(() => setIsLoading(false));
    }, []);

    const handleSave = async () => {
        setIsSaving(true);
        setError(null);
        setSuccess(false);
        try {
            const result = await api.patch<ClinicProfile>("/settings/clinic", {
                clinic_name: name.trim() || null,
                clinic_lat: lat.trim() ? Number(lat) : null,
                clinic_lng: lng.trim() ? Number(lng) : null,
                clinic_contacts: rowsToContacts(contacts),
            });
            setName(result.clinic_name ?? "");
            setLat(result.clinic_lat !== null ? String(result.clinic_lat) : "");
            setLng(result.clinic_lng !== null ? String(result.clinic_lng) : "");
            setContacts(contactsToRows(result.clinic_contacts));
            setSuccess(true);
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "Saqlashda xatolik");
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <section className="rounded-xl border border-secondary bg-primary p-5">
            <h2 className="text-sm font-semibold text-primary">Klinika profili</h2>
            <p className="mt-1 text-sm text-tertiary">Botdagi "Klinika haqida" bo'limida bemorlarga ko'rsatiladi.</p>

            {isLoading ? (
                <p className="mt-4 text-sm text-tertiary">Yuklanmoqda...</p>
            ) : (
                <div className="mt-4 flex flex-col gap-4">
                    <Input label="Klinika nomi" value={name} onChange={setName} className="max-w-md" />

                    <div className="flex flex-col gap-4 sm:flex-row">
                        <Input label="Kenglik (lat)" type="number" value={lat} onChange={setLat} />
                        <Input label="Uzunlik (lng)" type="number" value={lng} onChange={setLng} />
                    </div>

                    <div>
                        <p className="mb-2 text-sm font-medium text-secondary">Kontaktlar</p>
                        <div className="flex flex-col gap-2">
                            {contacts.map((row, index) => (
                                <div key={index} className="flex items-center gap-2">
                                    <Input
                                        aria-label="Kontakt nomi"
                                        placeholder="Telefon"
                                        value={row.label}
                                        onChange={(value) =>
                                            setContacts((prev) => prev.map((r, i) => (i === index ? { ...r, label: value } : r)))
                                        }
                                        className="w-40"
                                    />
                                    <Input
                                        aria-label="Kontakt qiymati"
                                        placeholder="+998901234567"
                                        value={row.value}
                                        onChange={(value) =>
                                            setContacts((prev) => prev.map((r, i) => (i === index ? { ...r, value } : r)))
                                        }
                                        className="flex-1"
                                    />
                                    <Button
                                        size="sm"
                                        color="tertiary-destructive"
                                        iconLeading={Trash01}
                                        aria-label="O'chirish"
                                        onClick={() => setContacts((prev) => prev.filter((_, i) => i !== index))}
                                    />
                                </div>
                            ))}
                            <Button
                                size="sm"
                                color="secondary"
                                iconLeading={Plus}
                                onClick={() => setContacts((prev) => [...prev, { label: "", value: "" }])}
                                className="self-start"
                            >
                                Kontakt qo'shish
                            </Button>
                        </div>
                    </div>
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
