import { addDays, isSameDay } from "@/lib/calendar";
import type { CalendarAppointment } from "@/types/appointment";
import { cx } from "@/utils/cx";

interface MonthViewProps {
    monthAnchor: Date;
    gridStart: Date;
    appointments: CalendarAppointment[];
    onSelectDay: (day: Date) => void;
}

const WEEKDAY_LABELS = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"];

export const MonthView = ({ monthAnchor, gridStart, appointments, onSelectDay }: MonthViewProps) => {
    const days = Array.from({ length: 42 }, (_, i) => addDays(gridStart, i));
    const today = new Date();
    const currentMonth = monthAnchor.getMonth();

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
                    const dayCount = appointments.filter((a) => isSameDay(new Date(a.start_at), day)).length;
                    const isCurrentMonth = day.getMonth() === currentMonth;
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
                            className={cx(
                                "flex aspect-square cursor-pointer flex-col items-center justify-center gap-1 rounded-lg ring-1 ring-secondary outline-focus-ring transition duration-100 ease-linear hover:ring-brand",
                                isCurrentMonth ? "bg-primary" : "bg-secondary",
                                isSameDay(day, today) && "ring-2 ring-brand",
                            )}
                        >
                            <p className={cx("text-xs font-semibold sm:text-sm", isCurrentMonth ? "text-primary" : "text-quaternary")}>
                                {day.getDate()}
                            </p>
                            {dayCount > 0 && (
                                <span className="flex size-5 items-center justify-center rounded-full bg-brand-solid text-[10px] font-semibold text-fg-white">
                                    {dayCount}
                                </span>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
};
