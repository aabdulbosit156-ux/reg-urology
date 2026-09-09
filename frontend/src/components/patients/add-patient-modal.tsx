import { useState, type FormEvent } from "react";
import { Check, Copy01 } from "@untitledui/icons";
import { Dialog, Modal, ModalOverlay } from "@/components/application/modals/modal";
import { Button } from "@/components/base/buttons/button";
import { Input } from "@/components/base/input/input";
import { TextArea } from "@/components/base/textarea/textarea";
import { useClipboard } from "@/hooks/use-clipboard";
import { ApiError, api } from "@/lib/api-client";
import type { Patient } from "@/types/patient";

interface AddPatientModalProps {
    isOpen: boolean;
    onOpenChange: (open: boolean) => void;
    onCreated: () => void;
}

export const AddPatientModal = ({ isOpen, onOpenChange, onCreated }: AddPatientModalProps) => {
    const [fullName, setFullName] = useState("");
    const [phone, setPhone] = useState("");
    const [goal, setGoal] = useState("");
    const [error, setError] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [createdPatient, setCreatedPatient] = useState<Patient | null>(null);
    const { copied, copy } = useClipboard();

    const reset = () => {
        setFullName("");
        setPhone("");
        setGoal("");
        setError(null);
        setCreatedPatient(null);
    };

    const handleClose = () => {
        onOpenChange(false);
        reset();
    };

    const handleSubmit = async (event: FormEvent) => {
        event.preventDefault();
        setError(null);
        setIsSubmitting(true);
        try {
            const patient = await api.post<Patient>("/patients", {
                full_name: fullName,
                phone,
                consultation_goal: goal || null,
            });
            setCreatedPatient(patient);
            onCreated();
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "Xatolik yuz berdi");
        } finally {
            setIsSubmitting(false);
        }
    };

    const inviteDeepLink = createdPatient?.invite_deep_link ?? null;

    return (
        <ModalOverlay isOpen={isOpen} onOpenChange={(open) => !open && handleClose()}>
            <Modal>
                <Dialog>
                    <div className="w-full max-w-md rounded-xl bg-primary p-6 shadow-xl">
                        <h2 className="text-lg font-semibold text-primary">Yangi bemor</h2>

                        {createdPatient ? (
                            <div className="mt-4 flex flex-col gap-4">
                                <p className="text-sm text-tertiary">
                                    <strong className="text-primary">{createdPatient.full_name}</strong> ro'yxatga olindi.
                                </p>
                                {inviteDeepLink ? (
                                    <div className="flex flex-col gap-2">
                                        <p className="text-sm text-secondary">Botga ulanish uchun havolani bemorga yuboring:</p>
                                        <div className="flex gap-2">
                                            <Input isReadOnly value={inviteDeepLink} className="flex-1" aria-label="Taklif havolasi" />
                                            <Button color="secondary" iconLeading={copied ? Check : Copy01} onClick={() => copy(inviteDeepLink)} />
                                        </div>
                                        <Button
                                            href={`sms:${createdPatient.phone}?body=${encodeURIComponent(inviteDeepLink)}`}
                                            color="secondary"
                                        >
                                            SMS orqali yuborish
                                        </Button>
                                    </div>
                                ) : (
                                    <p className="text-sm text-warning-primary">Bot username sozlanmagani uchun havola yaratilmadi.</p>
                                )}
                                <Button onClick={handleClose}>Yopish</Button>
                            </div>
                        ) : (
                            <form className="mt-4 flex flex-col gap-4" onSubmit={handleSubmit}>
                                <Input label="Ism-familiya" value={fullName} onChange={setFullName} isRequired autoFocus />
                                <Input label="Telefon raqam" value={phone} onChange={setPhone} isRequired />
                                <TextArea label="Konsultatsiya maqsadi" value={goal} onChange={setGoal} rows={3} />
                                {error && <p className="text-sm text-error-primary">{error}</p>}
                                <div className="flex justify-end gap-3">
                                    <Button color="secondary" type="button" onClick={handleClose}>
                                        Bekor qilish
                                    </Button>
                                    <Button type="submit" isLoading={isSubmitting} isDisabled={!fullName || !phone}>
                                        Qo'shish
                                    </Button>
                                </div>
                            </form>
                        )}
                    </div>
                </Dialog>
            </Modal>
        </ModalOverlay>
    );
};
