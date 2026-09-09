import { Phone, Send03, Trash01 } from "@untitledui/icons";
import { Button } from "@/components/base/buttons/button";
import { Table } from "@/components/application/table/table";
import { StatusBadge } from "@/components/patients/status-badge";
import type { Patient } from "@/types/patient";

interface Column {
    id: string;
    label: string;
}

const COLUMNS: Column[] = [
    { id: "patient", label: "Bemor" },
    { id: "phone", label: "Telefon" },
    { id: "status", label: "Holat" },
    { id: "created", label: "Sana" },
    { id: "actions", label: "" },
];

function formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString("uz-UZ", { day: "2-digit", month: "2-digit", year: "numeric" });
}

interface PatientTableProps {
    patients: Patient[];
    canManage: boolean;
    onOpen: (id: string) => void;
    onDelete: (patient: Patient) => void;
}

export const PatientTable = ({ patients, canManage, onOpen, onDelete }: PatientTableProps) => {
    return (
        <Table aria-label="Bemorlar ro'yxati">
            <Table.Header columns={COLUMNS}>{(column) => <Table.Head id={column.id}>{column.label}</Table.Head>}</Table.Header>
            <Table.Body
                items={patients}
                renderEmptyState={() => (
                    <div className="flex w-full justify-center py-12 text-sm text-tertiary">Bemorlar topilmadi</div>
                )}
            >
                {(patient) => (
                    <Table.Row id={patient.id} columns={COLUMNS}>
                        {(column) => {
                            switch (column.id) {
                                case "patient":
                                    return (
                                        <Table.Cell>
                                            <button
                                                type="button"
                                                onClick={() => onOpen(patient.id)}
                                                className="cursor-pointer text-left outline-focus-ring focus-visible:outline-2"
                                            >
                                                <p className="text-sm font-medium text-primary hover:underline">{patient.full_name}</p>
                                                {patient.telegram_username && (
                                                    <p className="text-xs text-tertiary">@{patient.telegram_username}</p>
                                                )}
                                            </button>
                                        </Table.Cell>
                                    );
                                case "phone":
                                    return <Table.Cell>{patient.phone}</Table.Cell>;
                                case "status":
                                    return (
                                        <Table.Cell>
                                            <StatusBadge status={patient.status} />
                                        </Table.Cell>
                                    );
                                case "created":
                                    return <Table.Cell>{formatDate(patient.created_at)}</Table.Cell>;
                                case "actions":
                                    return (
                                        <Table.Cell>
                                            <div className="flex justify-end gap-1">
                                                {patient.telegram_username && (
                                                    <Button
                                                        href={`https://t.me/${patient.telegram_username}`}
                                                        target="_blank"
                                                        rel="noreferrer"
                                                        size="sm"
                                                        color="tertiary"
                                                        iconLeading={Send03}
                                                        aria-label="Telegram orqali aloqa"
                                                    />
                                                )}
                                                <Button
                                                    href={`tel:${patient.phone}`}
                                                    size="sm"
                                                    color="tertiary"
                                                    iconLeading={Phone}
                                                    aria-label="Qo'ng'iroq qilish"
                                                />
                                                {canManage && (
                                                    <Button
                                                        size="sm"
                                                        color="tertiary-destructive"
                                                        iconLeading={Trash01}
                                                        aria-label="O'chirish"
                                                        onClick={() => onDelete(patient)}
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
    );
};
