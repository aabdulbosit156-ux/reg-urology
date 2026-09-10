import { useCallback, useEffect, useState } from "react";
import { Plus, Trash01, UserCheck01 } from "@untitledui/icons";
import { Dialog, Modal, ModalOverlay } from "@/components/application/modals/modal";
import { Table } from "@/components/application/table/table";
import { Badge, BadgeWithDot } from "@/components/base/badges/badges";
import { Button } from "@/components/base/buttons/button";
import { PageHeader } from "@/components/layout/page-header";
import { InviteStaffModal } from "@/components/staff/invite-staff-modal";
import { useLiveUpdates } from "@/hooks/use-live-updates";
import { ApiError, api } from "@/lib/api-client";
import { ROLE_BADGE_COLOR, ROLE_LABELS } from "@/lib/staff-role";
import { useAuth } from "@/providers/auth-provider";
import type { StaffStatsOut } from "@/types/staff";

interface Column {
    id: string;
    label: string;
}

const BASE_COLUMNS: Column[] = [
    { id: "name", label: "Xodim" },
    { id: "role", label: "Rol" },
    { id: "phone", label: "Telefon" },
    { id: "status", label: "Holat" },
    { id: "received", label: "Qabul qilingan bemorlar" },
];

export const StaffPage = () => {
    const { me } = useAuth();
    const canManageAccess = me?.role === "dev" || me?.role === "director";

    const [staff, setStaff] = useState<StaffStatsOut[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isInviteOpen, setIsInviteOpen] = useState(false);

    const [deactivateTarget, setDeactivateTarget] = useState<StaffStatsOut | null>(null);
    const [isUpdating, setIsUpdating] = useState(false);

    const columns = canManageAccess ? [...BASE_COLUMNS, { id: "actions", label: "" }] : BASE_COLUMNS;

    const loadStaff = useCallback(async () => {
        try {
            const result = await api.get<StaffStatsOut[]>("/staff");
            setStaff(result);
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "Xodimlarni yuklashda xatolik");
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        loadStaff();
    }, [loadStaff]);

    useLiveUpdates(loadStaff);

    const setActive = async (person: StaffStatsOut, isActive: boolean) => {
        setIsUpdating(true);
        setError(null);
        try {
            await api.patch(`/staff/${person.id}`, { is_active: isActive });
            setDeactivateTarget(null);
            await loadStaff();
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "O'zgartirishda xatolik");
        } finally {
            setIsUpdating(false);
        }
    };

    return (
        <div className="flex flex-col gap-6 px-4 py-6 pb-24 lg:px-0 lg:py-0">
            <PageHeader>
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                    <h1 className="text-xl font-semibold text-primary">
                        Xodimlar <span className="text-tertiary">{staff.length}</span>
                    </h1>
                    {canManageAccess && (
                        <Button iconLeading={Plus} onClick={() => setIsInviteOpen(true)}>
                            Xodim qo'shish
                        </Button>
                    )}
                </div>
            </PageHeader>

            {error && <p className="text-sm text-error-primary">{error}</p>}

            {isLoading ? (
                <p className="text-sm text-tertiary">Yuklanmoqda...</p>
            ) : (
                <Table aria-label="Xodimlar ro'yxati">
                    <Table.Header columns={columns}>{(column) => <Table.Head id={column.id}>{column.label}</Table.Head>}</Table.Header>
                    <Table.Body
                        items={staff}
                        renderEmptyState={() => (
                            <div className="flex w-full justify-center py-12 text-sm text-tertiary">Xodimlar topilmadi</div>
                        )}
                    >
                        {(person) => (
                            <Table.Row id={person.id} columns={columns}>
                                {(column) => {
                                    switch (column.id) {
                                        case "name":
                                            return (
                                                <Table.Cell>
                                                    <p className="text-sm font-medium text-primary">{person.full_name}</p>
                                                </Table.Cell>
                                            );
                                        case "role":
                                            return (
                                                <Table.Cell>
                                                    <Badge color={ROLE_BADGE_COLOR[person.role]} size="sm">
                                                        {ROLE_LABELS[person.role]}
                                                    </Badge>
                                                </Table.Cell>
                                            );
                                        case "phone":
                                            return <Table.Cell>{person.phone ?? "—"}</Table.Cell>;
                                        case "status":
                                            return (
                                                <Table.Cell>
                                                    <BadgeWithDot color={person.is_active ? "success" : "gray"} size="sm" type="pill-color">
                                                        {person.is_active ? "Faol" : "Nofaol"}
                                                    </BadgeWithDot>
                                                </Table.Cell>
                                            );
                                        case "received":
                                            return <Table.Cell>{person.patients_received}</Table.Cell>;
                                        case "actions":
                                            return (
                                                <Table.Cell>
                                                    <div className="flex justify-end">
                                                        {person.is_active ? (
                                                            <Button
                                                                size="sm"
                                                                color="tertiary-destructive"
                                                                iconLeading={Trash01}
                                                                aria-label="Xodimlikdan chiqarish"
                                                                onClick={() => setDeactivateTarget(person)}
                                                            />
                                                        ) : (
                                                            <Button
                                                                size="sm"
                                                                color="tertiary"
                                                                iconLeading={UserCheck01}
                                                                aria-label="Faollashtirish"
                                                                isLoading={isUpdating}
                                                                onClick={() => setActive(person, true)}
                                                            />
                                                        )}
                                                    </div>
                                                </Table.Cell>
                                            );
                                        default:
                                            return <Table.Cell>—</Table.Cell>;
                                    }
                                }}
                            </Table.Row>
                        )}
                    </Table.Body>
                </Table>
            )}

            {canManageAccess && <InviteStaffModal isOpen={isInviteOpen} onOpenChange={setIsInviteOpen} />}

            <ModalOverlay isOpen={!!deactivateTarget} onOpenChange={(open) => !open && setDeactivateTarget(null)}>
                <Modal>
                    <Dialog>
                        <div className="w-full max-w-sm rounded-xl bg-primary p-6 shadow-xl">
                            <h2 className="text-lg font-semibold text-primary">Xodimlikdan chiqarish</h2>
                            <p className="mt-2 text-sm text-tertiary">
                                <strong className="text-primary">{deactivateTarget?.full_name}</strong> endi tizimga kira olmaydi va
                                xabarnomalar olmaydi. Uning o'tmishdagi ma'lumotlari (bemorlar, analizlar, tarix) saqlanib qoladi.
                                Keyinchalik qayta faollashtirish mumkin.
                            </p>
                            <div className="mt-6 flex justify-end gap-3">
                                <Button color="secondary" onClick={() => setDeactivateTarget(null)}>
                                    Bekor qilish
                                </Button>
                                <Button
                                    color="primary-destructive"
                                    isLoading={isUpdating}
                                    onClick={() => deactivateTarget && setActive(deactivateTarget, false)}
                                >
                                    Chiqarish
                                </Button>
                            </div>
                        </div>
                    </Dialog>
                </Modal>
            </ModalOverlay>
        </div>
    );
};
