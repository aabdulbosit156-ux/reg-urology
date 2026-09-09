import { Badge } from "@/components/base/badges/badges";
import { STATUS_BADGE_COLOR, STATUS_LABELS } from "@/lib/patient-status";
import type { PatientStatus } from "@/types/patient";

export const StatusBadge = ({ status }: { status: PatientStatus }) => (
    <Badge size="sm" type="pill-color" color={STATUS_BADGE_COLOR[status]}>
        {STATUS_LABELS[status]}
    </Badge>
);
