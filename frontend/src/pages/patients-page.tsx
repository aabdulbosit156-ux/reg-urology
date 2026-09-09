import { useCallback, useEffect, useState } from "react";
import { Plus, SearchLg } from "@untitledui/icons";
import { Dialog, Modal, ModalOverlay } from "@/components/application/modals/modal";
import { Tabs } from "@/components/application/tabs/tabs";
import { Button } from "@/components/base/buttons/button";
import { Input } from "@/components/base/input/input";
import { AddPatientModal } from "@/components/patients/add-patient-modal";
import { PatientSlideout } from "@/components/patients/patient-slideout";
import { PatientTable } from "@/components/patients/patient-table";
import { useLiveUpdates } from "@/hooks/use-live-updates";
import { ApiError, api } from "@/lib/api-client";
import { SEGMENT_LABELS } from "@/lib/patient-status";
import { useAuth } from "@/providers/auth-provider";
import type { Patient, PatientListResponse, PatientSegment } from "@/types/patient";

const SEGMENT_TABS: { id: PatientSegment; label: string }[] = [
    { id: "new", label: SEGMENT_LABELS.new },
    { id: "in_progress", label: SEGMENT_LABELS.in_progress },
    { id: "unresponsive", label: SEGMENT_LABELS.unresponsive },
];

export const PatientsPage = () => {
    const { me } = useAuth();
    const canManage = me?.role !== "analyst";

    const [segment, setSegment] = useState<PatientSegment>("new");
    const [searchInput, setSearchInput] = useState("");
    const [search, setSearch] = useState("");
    const [patients, setPatients] = useState<Patient[]>([]);
    const [total, setTotal] = useState(0);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [selectedPatientId, setSelectedPatientId] = useState<string | null>(null);
    const [isAddModalOpen, setIsAddModalOpen] = useState(false);
    const [deleteTarget, setDeleteTarget] = useState<Patient | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);

    useEffect(() => {
        const timeout = setTimeout(() => setSearch(searchInput), 300);
        return () => clearTimeout(timeout);
    }, [searchInput]);

    const loadPatients = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const params = new URLSearchParams({ segment });
            if (search) params.set("search", search);
            const result = await api.get<PatientListResponse>(`/patients?${params.toString()}`);
            setPatients(result.items);
            setTotal(result.total);
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "Bemorlarni yuklashda xatolik");
        } finally {
            setIsLoading(false);
        }
    }, [segment, search]);

    useEffect(() => {
        loadPatients();
    }, [loadPatients]);

    useLiveUpdates(loadPatients);

    const handleDelete = async () => {
        if (!deleteTarget) return;
        setIsDeleting(true);
        try {
            await api.delete(`/patients/${deleteTarget.id}`);
            setDeleteTarget(null);
            await loadPatients();
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "O'chirishda xatolik");
        } finally {
            setIsDeleting(false);
        }
    };

    return (
        <div className="flex flex-col gap-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                    <h1 className="text-xl font-semibold text-primary">Bemorlar</h1>
                    <p className="text-sm text-tertiary">{total} ta bemor</p>
                </div>
                {canManage && (
                    <Button iconLeading={Plus} onClick={() => setIsAddModalOpen(true)}>
                        Yangi bemor
                    </Button>
                )}
            </div>

            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <Tabs selectedKey={segment} onSelectionChange={(key) => setSegment(key as PatientSegment)}>
                    <Tabs.List type="button-border" items={SEGMENT_TABS}>
                        {(item) => <Tabs.Item id={item.id} label={item.label} />}
                    </Tabs.List>
                </Tabs>
                <Input
                    icon={SearchLg}
                    aria-label="Qidirish"
                    placeholder="Ism yoki telefon bo'yicha qidirish"
                    value={searchInput}
                    onChange={setSearchInput}
                    className="md:w-80"
                />
            </div>

            {error && <p className="text-sm text-error-primary">{error}</p>}

            {isLoading ? (
                <p className="text-sm text-tertiary">Yuklanmoqda...</p>
            ) : (
                <PatientTable patients={patients} canManage={canManage} onOpen={setSelectedPatientId} onDelete={setDeleteTarget} />
            )}

            <AddPatientModal isOpen={isAddModalOpen} onOpenChange={setIsAddModalOpen} onCreated={loadPatients} />

            <PatientSlideout
                patientId={selectedPatientId}
                onOpenChange={(open) => !open && setSelectedPatientId(null)}
                onChanged={loadPatients}
            />

            <ModalOverlay isOpen={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
                <Modal>
                    <Dialog>
                        <div className="w-full max-w-sm rounded-xl bg-primary p-6 shadow-xl">
                            <h2 className="text-lg font-semibold text-primary">Bemorni o'chirish</h2>
                            <p className="mt-2 text-sm text-tertiary">
                                <strong className="text-primary">{deleteTarget?.full_name}</strong> ni o'chirishni tasdiqlaysizmi? Bu amalni
                                qaytarib bo'lmaydi.
                            </p>
                            <div className="mt-6 flex justify-end gap-3">
                                <Button color="secondary" onClick={() => setDeleteTarget(null)}>
                                    Bekor qilish
                                </Button>
                                <Button color="primary-destructive" isLoading={isDeleting} onClick={handleDelete}>
                                    O'chirish
                                </Button>
                            </div>
                        </div>
                    </Dialog>
                </Modal>
            </ModalOverlay>
        </div>
    );
};
