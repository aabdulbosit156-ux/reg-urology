import { generateTimeSlots, slotIndexOf, withTimeOfSlot } from "@/lib/calendar";
import { formatTimeUz } from "@/lib/uz-date";
import type { CalendarAppointment } from "@/types/appointment";
import type { ScheduleSettings } from "@/types/settings";

const ROW_HEIGHT_REM = 3;

interface BookingMode {
    patientName: string;
    onPickSlot: (start: Date) => void;
}

interface DayViewProps {
    date: Date;
    appointments: CalendarAppointment[];
    schedule: ScheduleSettings;
    onOpenPatient: (patientId: string) => void;
    booking?: BookingMode;
}

export const DayView = ({ date, appointments, schedule, onOpenPatient, booking }: DayViewProps) => {
    const slots = generateTimeSlots(schedule.work_start, schedule.work_end, schedule.slot_minutes);
    const totalHeight = slots.length * ROW_HEIGHT_REM;
    const now = new Date();

    const coveredIndices = new Set<number>();
    appointments.forEach((a) => {
        const startIdx = slotIndexOf(new Date(a.start_at), schedule.work_start, schedule.slot_minutes);
        const span = Math.max(1, Math.ceil(a.duration_min / schedule.slot_minutes));
        for (let i = startIdx; i < startIdx + span; i++) coveredIndices.add(i);
    });

    return (
        <div className="flex">
            <div className="flex shrink-0 flex-col" style={{ width: "4rem" }}>
                {slots.map((slot) => (
                    <div
                        key={slot}
                        style={{ height: `${ROW_HEIGHT_REM}rem` }}
                        className="border-t border-secondary pr-2 text-right text-xs text-quaternary"
                    >
                        {slot}
                    </div>
                ))}
            </div>
            <div className="relative flex-1 border-l border-secondary" style={{ height: `${totalHeight}rem` }}>
                {slots.map((slot, idx) => {
                    const slotStart = withTimeOfSlot(date, slot);
                    const isPast = slotStart <= now;
                    const isFree = !coveredIndices.has(idx);
                    return (
                        <div key={slot} className="absolute inset-x-0 border-t border-secondary" style={{ top: `${idx * ROW_HEIGHT_REM}rem` }}>
                            {booking && isFree && !isPast && (
                                <button
                                    type="button"
                                    onClick={() => booking.onPickSlot(slotStart)}
                                    style={{ height: `${ROW_HEIGHT_REM}rem` }}
                                    className="absolute inset-x-1 top-0 flex items-center justify-center rounded-md text-xs font-medium text-tertiary opacity-0 outline-focus-ring transition duration-100 ease-linear hover:bg-brand-primary_alt hover:text-brand-secondary hover:opacity-100"
                                >
                                    {slot} — band qilish
                                </button>
                            )}
                        </div>
                    );
                })}
                {appointments.length === 0 && !booking && (
                    <p className="absolute inset-0 flex items-center justify-center text-sm text-quaternary">
                        Bu kunda qabullar yo'q
                    </p>
                )}
                {appointments.map((a) => {
                    const startIdx = slotIndexOf(new Date(a.start_at), schedule.work_start, schedule.slot_minutes);
                    if (startIdx < 0 || startIdx >= slots.length) return null;
                    const span = Math.max(1, Math.ceil(a.duration_min / schedule.slot_minutes));
                    return (
                        <button
                            key={a.id}
                            type="button"
                            onClick={() => onOpenPatient(a.patient_id)}
                            className="absolute right-1 left-1 overflow-hidden rounded-md bg-brand-primary_alt px-2 py-1 text-left outline-focus-ring transition duration-100 ease-linear hover:opacity-90"
                            style={{ top: `${startIdx * ROW_HEIGHT_REM}rem`, height: `${span * ROW_HEIGHT_REM - 0.25}rem` }}
                        >
                            <p className="truncate text-xs font-semibold text-brand-secondary">
                                {formatTimeUz(a.start_at)} · {a.patient.full_name}
                            </p>
                        </button>
                    );
                })}
            </div>
        </div>
    );
};
