import type { DragEvent } from "react";
import { AppointmentCard } from "@/components/calendar/appointment-card";
import { addDays, isSameDay } from "@/lib/calendar";
import { formatDayShortUz } from "@/lib/uz-date";
import type { CalendarAppointment } from "@/types/appointment";
import { cx } from "@/utils/cx";

interface WeekViewProps {
    weekStart: Date;
    appointments: CalendarAppointment[];
    onOpenPatient: (patientId: string) => void;
    onReschedule: (appointmentId: string, newStart: Date) => void;
    onSelectDay: (day: Date) => void;
}

export const WeekView = ({ weekStart, appointments, onOpenPatient, onReschedule, onSelectDay }: WeekViewProps) => {
    const days = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));
    const today = new Date();

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
        <div className="grid grid-cols-1 gap-3 md:grid-cols-7">
            {days.map((day) => {
                const dayAppointments = appointments
                    .filter((a) => isSameDay(new Date(a.start_at), day))
                    .sort((a, b) => a.start_at.localeCompare(b.start_at));
                return (
                    <div
                        key={day.toISOString()}
                        role="button"
                        tabIndex={0}
                        onClick={() => onSelectDay(day)}
                        onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                                event.preventDefault();
                                onSelectDay(day);
                            }
                        }}
                        onDragOver={(event) => event.preventDefault()}
                        onDrop={(event) => handleDrop(event, day)}
                        className={cx(
                            "flex min-h-32 cursor-pointer flex-col gap-1.5 rounded-lg p-2 ring-1 ring-secondary outline-focus-ring transition duration-100 ease-linear hover:ring-brand",
                            isSameDay(day, today) ? "bg-brand-primary_alt" : "bg-primary",
                        )}
                    >
                        <p className="self-start px-1 text-xs font-semibold text-tertiary capitalize">{formatDayShortUz(day)}</p>
                        {dayAppointments.length === 0 && <p className="text-xs text-quaternary">—</p>}
                        {dayAppointments.map((a) => (
                            <AppointmentCard
                                key={a.id}
                                appointment={a}
                                onClick={() => onOpenPatient(a.patient_id)}
                                onDragStart={(event) => event.dataTransfer.setData("text/plain", a.id)}
                            />
                        ))}
                    </div>
                );
            })}
        </div>
    );
};
