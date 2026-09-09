import type { StaffRole } from "@/providers/auth-provider";

export const ROLE_LABELS: Record<StaffRole, string> = {
    dev: "Dev",
    director: "Direktor",
    admin: "Administrator",
    analyst: "Analitik",
};

export const ROLE_BADGE_COLOR: Record<StaffRole, "gray" | "brand" | "success" | "blue"> = {
    dev: "gray",
    director: "brand",
    admin: "blue",
    analyst: "success",
};
