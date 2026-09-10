import { useCallback, useEffect, useState } from "react";
import { Plus } from "@untitledui/icons";
import { Table } from "@/components/application/table/table";
import { Badge, BadgeWithDot } from "@/components/base/badges/badges";
import { Button } from "@/components/base/buttons/button";
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

const COLUMNS: Column[] = [
    { id: "name", label: "Xodim" },
    { id: "role", label: "Rol" },
    { id: "phone", label: "Telefon" },
    { id: "status", label: "Holat" },
    { id: "received", label: "Qabul qilingan bemorlar" },
];

export const StaffPage = () => {
    const { me } = useAuth();
    const canInvite = me?.role === "dev" || me?.role === "director";

    const [staff, setStaff] = useState<StaffStatsOut[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isInviteOpen, setIsInviteOpen] = useState(false);

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

    return (
        <div className="flex flex-col gap-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <h1 className="text-xl font-semibold text-primary">
                    Xodimlar <span className="text-tertiary">{staff.length}</span>
                </h1>
                {canInvite && (
                    <Button iconLeading={Plus} onClick={() => setIsInviteOpen(true)}>
                        Xodim qo'shish
                    </Button>
                )}
            </div>

            {error && <p className="text-sm text-error-primary">{error}</p>}

            {isLoading ? (
                <p className="text-sm text-tertiary">Yuklanmoqda...</p>
            ) : (
                <Table aria-label="Xodimlar ro'yxati">
                    <Table.Header columns={COLUMNS}>{(column) => <Table.Head id={column.id}>{column.label}</Table.Head>}</Table.Header>
                    <Table.Body
                        items={staff}
                        renderEmptyState={() => (
                            <div className="flex w-full justify-center py-12 text-sm text-tertiary">Xodimlar topilmadi</div>
                        )}
                    >
                        {(person) => (
                            <Table.Row id={person.id} columns={COLUMNS}>
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
                                        default:
                                            return <Table.Cell>—</Table.Cell>;
                                    }
                                }}
                            </Table.Row>
                        )}
                    </Table.Body>
                </Table>
            )}

            {canInvite && <InviteStaffModal isOpen={isInviteOpen} onOpenChange={setIsInviteOpen} />}
        </div>
    );
};
