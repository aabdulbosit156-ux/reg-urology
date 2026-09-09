import type { Analysis } from "@/types/analysis";

export type PatientStatus =
    | "new"
    | "scheduled"
    | "unreachable"
    | "advised"
    | "no_show"
    | "arrived"
    | "analysis_ordered"
    | "analysis_ready";

export type PatientSegment = "new" | "in_progress" | "unresponsive";

export type PatientSource = "bot" | "manual";

export interface Patient {
    id: string;
    full_name: string;
    phone: string;
    telegram_user_id: number | null;
    telegram_username: string | null;
    consultation_goal: string | null;
    source: PatientSource;
    status: PatientStatus;
    assigned_staff_id: string | null;
    invite_deep_link: string | null;
    created_at: string;
}

export interface StatusHistoryEntry {
    id: string;
    from_status: PatientStatus | null;
    to_status: PatientStatus;
    staff_id: string | null;
    staff_name: string | null;
    note: string | null;
    at: string;
}

export type AppointmentStatus = "scheduled" | "completed" | "cancelled";

export interface Appointment {
    id: string;
    patient_id: string;
    staff_id: string | null;
    start_at: string;
    duration_min: number;
    status: AppointmentStatus;
    room: string | null;
}

export interface PatientDetail extends Patient {
    history: StatusHistoryEntry[];
    appointments: Appointment[];
    analyses: Analysis[];
}

export interface PatientListResponse {
    items: Patient[];
    total: number;
}
