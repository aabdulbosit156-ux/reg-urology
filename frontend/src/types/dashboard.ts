import type { PatientStatus } from "@/types/patient";

export type StatusCounts = Record<PatientStatus, number>;

export interface DailyLeads {
    date: string;
    count: number;
}

export interface DashboardOut {
    segment_new: number;
    segment_in_progress: number;
    segment_unresponsive: number;
    appointments_today: number;
    analyses_pending: number;
    status_counts: StatusCounts;
    daily_leads: DailyLeads[];
    my_analyses_uploaded: number | null;
}
