import type { DragEvent } from "react";
import { AppointmentCard } from "@/components/calendar/appointment-card";
import { addDays, isSameDay } from "@/lib/calendar";
import type { CalendarAppointment } from "@/types/appointment";
import { cx } from "@/utils/cx";

interface MonthViewProps {
    monthAnchor: Date;
    gridStart: Date;
    appointments: CalendarAppointment[];
    onOpenPatient: (patientId: string) => void;
    onReschedule: (appointmentId: string, newStart: Date) => void;
    onSelectDay: (day: Date) => void;
}

const WEEKDAY_LABELS = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"];
const MAX_VISIBLE = 3;

export const MonthView = ({
    monthAnchor,
    gridStart,
    appointments,
    onOpenPatient,
    onReschedule,
    onSelectDay,
}: MonthViewProps) => {
    const days = Array.from({ length: 42 }, (_, i) => addDays(gridStart, i));
    const today = new Date();
    const currentMonth = monthAnchor.getMonth();

    const handleDrop = (event: DragEvent<HTMLDivElement>, day: Date) => {
        event.preventDefault();
        const appointmentId = event.dataTransfer.getData("text/plain");
        const appointment = appointments.find((a) => a.id === appointmentId);
        if (!appointment) return;
        const originalStart = new Date(appointment.start_at);
        const newStart = new Date(day);
        newStart.setHours(originalStart.getHours(), originalStart.getMinutes(), 0, 0);
        onReschedule(appointmentId, newStart);
    };

    return (
        <div className="flex flex-col gap-1.5">
            <div className="grid grid-cols-7 gap-1.5">
                {WEEKDAY_LABELS.map((label) => (
                    <p key={label} className="text-center text-xs font-semibold text-quaternary">
                        {label}
                    </p>
                ))}
            </div>
            <div className="grid grid-cols-7 gap-1.5">
                {days.map((day) => {
                    const dayAppointments = appointments
                        .filter((a) => isSameDay(new Date(a.start_at), day))
                        .sort((a, b) => a.start_at.localeCompare(b.start_at));
                    const isCurrentMonth = day.getMonth() === currentMonth;
                    return (
                        <div
                            key={day.toISOString()}
                            onDragOver={(event) => event.preventDefault()}
                            onDrop={(event) => handleDrop(event, day)}
                            className={cx(
                                "flex min-h-24 flex-col gap-1 rounded-lg p-1.5 ring-1 ring-secondary",
                                isCurrentMonth ? "bg-primary" : "bg-secondary",
                                isSameDay(day, today) && "ring-2 ring-brand",
                            )}
                        >
                            <button
                                type="button"
                                onClick={() => onSelectDay(day)}
                                className={cx(
                                    "self-start rounded px-1 text-xs font-semibold outline-focus-ring",
                                    isCurrentMonth ? "text-primary" : "text-quaternary",
                                )}
                            >
                                {day.getDate()}
                            </button>
                            {dayAppointments.slice(0, MAX_VISIBLE).map((a) => (
                                <AppointmentCard
                                    key={a.id}
                                    appointment={a}
                                    onClick={() => onOpenPatient(a.patient_id)}
                                    onDragStart={(event) => event.dataTransfer.setData("text/plain", a.id)}
                                />
                            ))}
                            {dayAppointments.length > MAX_VISIBLE && (
                                <button
                                    type="button"
                                    onClick={() => onSelectDay(day)}
                                    className="text-left text-xs text-tertiary hover:underline"
                                >
                                    +{dayAppointments.length - MAX_VISIBLE} ko'proq
                                </button>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
};
