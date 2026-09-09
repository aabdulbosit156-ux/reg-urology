import { useEffect, useState } from "react";
import { Table } from "@/components/application/table/table";
import { ApiError, api } from "@/lib/api-client";
import type { ActivityLogListResponse, ActivityLogOut } from "@/types/activity";

interface Column {
    id: string;
    label: string;
}

const COLUMNS: Column[] = [
    { id: "at", label: "Vaqt" },
    { id: "staff", label: "Xodim" },
    { id: "action", label: "Amal" },
    { id: "entity", label: "Ob'ekt" },
];

function formatDateTime(iso: string): string {
    return new Date(iso).toLocaleString("uz-UZ", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

const PAGE_SIZE = 50;

export const ActivityPage = () => {
    const [items, setItems] = useState<ActivityLogOut[]>([]);
    const [total, setTotal] = useState(0);
    const [offset, setOffset] = useState(0);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setIsLoading(true);
        api.get<ActivityLogListResponse>(`/activity?limit=${PAGE_SIZE}&offset=${offset}`)
            .then((result) => {
                if (cancelled) return;
                setItems(result.items);
                setTotal(result.total);
            })
            .catch((err) => {
                if (!cancelled) setError(err instanceof ApiError ? err.message : "Faoliyat logini yuklashda xatolik");
            })
            .finally(() => {
                if (!cancelled) setIsLoading(false);
            });
        return () => {
            cancelled = true;
        };
    }, [offset]);

    return (
        <div className="flex flex-col gap-6">
            <div>
                <h1 className="text-xl font-semibold text-primary">Faoliyat</h1>
                <p className="text-sm text-tertiary">{total} ta yozuv</p>
            </div>

            {error && <p className="text-sm text-error-primary">{error}</p>}

            {isLoading ? (
                <p className="text-sm text-tertiary">Yuklanmoqda...</p>
            ) : (
                <>
                    <Table aria-label="Faoliyat logi">
                        <Table.Header columns={COLUMNS}>{(column) => <Table.Head id={column.id}>{column.label}</Table.Head>}</Table.Header>
                        <Table.Body
                            items={items}
                            renderEmptyState={() => (
                                <div className="flex w-full justify-center py-12 text-sm text-tertiary">Yozuvlar topilmadi</div>
                            )}
                        >
                            {(entry) => (
                                <Table.Row id={entry.id} columns={COLUMNS}>
                                    {(column) => {
                                        switch (column.id) {
                                            case "at":
                                                return <Table.Cell>{formatDateTime(entry.at)}</Table.Cell>;
                                            case "staff":
                                                return <Table.Cell>{entry.staff_name ?? "—"}</Table.Cell>;
                                            case "action":
                                                return (
                                                    <Table.Cell>
                                                        <span className="font-mono text-xs text-primary">{entry.action}</span>
                                                    </Table.Cell>
                                                );
                                            case "entity":
                                                return (
                                                    <Table.Cell>
                                                        {entry.entity ? (
                                                            <span className="text-xs text-tertiary">
                                                                {entry.entity}
                                                                {entry.entity_id ? ` · ${entry.entity_id.slice(0, 8)}` : ""}
                                                            </span>
                                                        ) : (
                                                            "—"
                                                        )}
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

                    {total > PAGE_SIZE && (
                        <div className="flex items-center justify-between text-sm text-tertiary">
                            <button
                                type="button"
                                disabled={offset === 0}
                                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                                className="cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                Oldingi
                            </button>
                            <span>
                                {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} / {total}
                            </span>
                            <button
                                type="button"
                                disabled={offset + PAGE_SIZE >= total}
                                onClick={() => setOffset(offset + PAGE_SIZE)}
                                className="cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                Keyingi
                            </button>
                        </div>
                    )}
                </>
            )}
        </div>
    );
};
