import type { DragEvent } from "react";
import { formatTimeUz } from "@/lib/uz-date";
import type { CalendarAppointment } from "@/types/appointment";

interface AppointmentCardProps {
    appointment: CalendarAppointment;
    onClick: () => void;
    onDragStart?: (event: DragEvent<HTMLButtonElement>) => void;
    draggable?: boolean;
}

export const AppointmentCard = ({ appointment, onClick, onDragStart, draggable = true }: AppointmentCardProps) => (
    <button
        type="button"
        draggable={draggable}
        onDragStart={onDragStart}
        onClick={(event) => {
            event.stopPropagation();
            onClick();
        }}
        className="flex w-full cursor-grab items-center gap-1.5 rounded-md bg-secondary px-2 py-1 text-left outline-focus-ring transition duration-100 ease-linear hover:bg-secondary_hover active:cursor-grabbing"
    >
        <span className="shrink-0 text-xs font-semibold text-brand-secondary">{formatTimeUz(appointment.start_at)}</span>
        <span className="min-w-0 flex-1 truncate text-xs text-secondary">{appointment.patient.full_name}</span>
    </button>
);
