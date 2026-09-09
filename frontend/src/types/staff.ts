import type { StaffRole } from "@/providers/auth-provider";

export interface StaffStatsOut {
    id: string;
    full_name: string;
    role: StaffRole;
    phone: string | null;
    is_active: boolean;
    patients_received: number;
    created_at: string;
}
