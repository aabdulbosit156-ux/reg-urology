import type { PatientSegment, PatientStatus } from "@/types/patient";

type StatusBadgeColor = "gray" | "brand" | "error" | "warning" | "success" | "blue" | "purple" | "orange";

export const STATUS_LABELS: Record<PatientStatus, string> = {
    new: "Yangi",
    scheduled: "Qabulga joylangan",
    unreachable: "Bog'lanib bo'lmadi",
    advised: "Maslahat berilgan",
    no_show: "Kelmagan",
    arrived: "Keldi",
    analysis_ordered: "Analiz buyurildi",
    analysis_ready: "Analiz tayyor",
};

export const STATUS_BADGE_COLOR: Record<PatientStatus, StatusBadgeColor> = {
    new: "brand",
    scheduled: "blue",
    unreachable: "warning",
    advised: "success",
    no_show: "error",
    arrived: "purple",
    analysis_ordered: "orange",
    analysis_ready: "success",
};

export const SEGMENT_LABELS: Record<PatientSegment, string> = {
    new: "Yangi",
    in_progress: "Jarayonda",
    unresponsive: "Javobsiz",
};

// Mirrors backend VALID_TRANSITIONS in app/api/routes/patients.py — keep in sync.
export const VALID_TRANSITIONS: Record<PatientStatus, PatientStatus[]> = {
    new: ["scheduled", "unreachable", "advised"],
    unreachable: ["scheduled", "unreachable", "advised"],
    scheduled: ["arrived", "no_show"],
    no_show: ["scheduled", "unreachable"],
    arrived: ["analysis_ordered", "advised"],
    analysis_ordered: ["analysis_ready"],
    analysis_ready: ["advised"],
    advised: ["scheduled"],
};

export const STATUS_ORDER: PatientStatus[] = [
    "new",
    "scheduled",
    "arrived",
    "analysis_ordered",
    "analysis_ready",
    "advised",
];
