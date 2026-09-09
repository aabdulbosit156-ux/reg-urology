import { useEffect, useState } from "react";
import { Table } from "@/components/application/table/table";
import { Badge, BadgeWithDot } from "@/components/base/badges/badges";
import { ApiError, api } from "@/lib/api-client";
import { ROLE_BADGE_COLOR, ROLE_LABELS } from "@/lib/staff-role";
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
    const [staff, setStaff] = useState<StaffStatsOut[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setIsLoading(true);
        api.get<StaffStatsOut[]>("/staff")
            .then((result) => {
                if (!cancelled) setStaff(result);
            })
            .catch((err) => {
                if (!cancelled) setError(err instanceof ApiError ? err.message : "Xodimlarni yuklashda xatolik");
            })
            .finally(() => {
                if (!cancelled) setIsLoading(false);
            });
        return () => {
            cancelled = true;
        };
    }, []);

    return (
        <div className="flex flex-col gap-6">
            <div>
                <h1 className="text-xl font-semibold text-primary">Xodimlar</h1>
                <p className="text-sm text-tertiary">{staff.length} ta xodim</p>
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
        </div>
    );
};
