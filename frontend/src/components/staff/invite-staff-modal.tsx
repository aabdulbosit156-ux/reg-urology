import { useEffect, useState } from "react";
import { Check, Copy01 } from "@untitledui/icons";
import { Dialog, Modal, ModalOverlay } from "@/components/application/modals/modal";
import { Button } from "@/components/base/buttons/button";
import { Input } from "@/components/base/input/input";
import { Select } from "@/components/base/select/select";
import { useClipboard } from "@/hooks/use-clipboard";
import { ApiError, api, fetchBlob } from "@/lib/api-client";
import { ROLE_LABELS } from "@/lib/staff-role";
import { formatTimeUz } from "@/lib/uz-date";
import type { InvitableRole, StaffSessionCreateResponse } from "@/types/auth";

const INVITABLE_ROLES: { id: InvitableRole; label: string }[] = [
    { id: "director", label: ROLE_LABELS.director },
    { id: "admin", label: ROLE_LABELS.admin },
    { id: "analyst", label: ROLE_LABELS.analyst },
];

interface InviteStaffModalProps {
    isOpen: boolean;
    onOpenChange: (open: boolean) => void;
}

export const InviteStaffModal = ({ isOpen, onOpenChange }: InviteStaffModalProps) => {
    const [role, setRole] = useState<InvitableRole>("admin");
    const [error, setError] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [session, setSession] = useState<StaffSessionCreateResponse | null>(null);
    const [qrUrl, setQrUrl] = useState<string | null>(null);
    const { copied, copy } = useClipboard();

    const reset = () => {
        setRole("admin");
        setError(null);
        setSession(null);
        if (qrUrl) URL.revokeObjectURL(qrUrl);
        setQrUrl(null);
    };

    const handleClose = () => {
        onOpenChange(false);
        reset();
    };

    const handleSubmit = async () => {
        setError(null);
        setIsSubmitting(true);
        try {
            const result = await api.post<StaffSessionCreateResponse>("/auth/staff/token", { role });
            setSession(result);
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "Xatolik yuz berdi");
        } finally {
            setIsSubmitting(false);
        }
    };

    useEffect(() => {
        if (!session) return;
        let cancelled = false;
        let objectUrl: string | null = null;
        fetchBlob(`/auth/staff/token/${session.token}/qr`)
            .then((blob) => {
                if (cancelled) return;
                objectUrl = URL.createObjectURL(blob);
                setQrUrl(objectUrl);
            })
            .catch(() => {
                if (!cancelled) setError("QR kod yuklanmadi");
            });
        return () => {
            cancelled = true;
            if (objectUrl) URL.revokeObjectURL(objectUrl);
        };
    }, [session]);

    const expiresLabel = session ? formatTimeUz(session.expires_at) : null;

    return (
        <ModalOverlay isOpen={isOpen} onOpenChange={(open) => !open && handleClose()}>
            <Modal>
                <Dialog>
                    <div className="w-full max-w-md rounded-xl bg-primary p-6 shadow-xl">
                        <h2 className="text-lg font-semibold text-primary">Yangi xodim taklif qilish</h2>

                        {session ? (
                            <div className="mt-4 flex flex-col gap-4">
                                <p className="text-sm text-tertiary">
                                    <strong className="text-primary">{ROLE_LABELS[session.role]}</strong> sifatida taklif yaratildi. Havola{" "}
                                    <strong className="text-primary">{expiresLabel}</strong>gacha amal qiladi.
                                </p>

                                {qrUrl ? (
                                    <img src={qrUrl} alt="QR kod" className="mx-auto size-48 rounded-lg ring-1 ring-secondary" />
                                ) : (
                                    <div className="mx-auto flex size-48 items-center justify-center text-sm text-tertiary">Yuklanmoqda...</div>
                                )}

                                <div className="flex flex-col gap-2">
                                    <p className="text-sm text-secondary">Yoki havolani xodimga yuboring:</p>
                                    <div className="flex gap-2">
                                        <Input isReadOnly value={session.deep_link} className="flex-1" aria-label="Taklif havolasi" />
                                        <Button color="secondary" iconLeading={copied ? Check : Copy01} onClick={() => copy(session.deep_link)} />
                                    </div>
                                </div>

                                <Button onClick={handleClose}>Yopish</Button>
                            </div>
                        ) : (
                            <div className="mt-4 flex flex-col gap-4">
                                <Select label="Rol" selectedKey={role} onSelectionChange={(key) => setRole(key as InvitableRole)} items={INVITABLE_ROLES}>
                                    {(item) => <Select.Item id={item.id}>{item.label}</Select.Item>}
                                </Select>
                                {error && <p className="text-sm text-error-primary">{error}</p>}
                                <div className="flex justify-end gap-3">
                                    <Button color="secondary" onClick={handleClose}>
                                        Bekor qilish
                                    </Button>
                                    <Button onClick={handleSubmit} isLoading={isSubmitting}>
                                        Taklif yaratish
                                    </Button>
                                </div>
                            </div>
                        )}
                    </div>
                </Dialog>
            </Modal>
        </ModalOverlay>
    );
};
