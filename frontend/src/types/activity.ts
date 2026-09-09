export interface ActivityLogOut {
    id: string;
    staff_id: string | null;
    staff_name: string | null;
    action: string;
    entity: string | null;
    entity_id: string | null;
    meta: Record<string, unknown>;
    at: string;
}

export interface ActivityLogListResponse {
    items: ActivityLogOut[];
    total: number;
}
