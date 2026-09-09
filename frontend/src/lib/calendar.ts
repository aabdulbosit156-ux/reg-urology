export function startOfDay(date: Date): Date {
    const d = new Date(date);
    d.setHours(0, 0, 0, 0);
    return d;
}

export function addDays(date: Date, days: number): Date {
    const d = new Date(date);
    d.setDate(d.getDate() + days);
    return d;
}

/** Monday-start week. */
export function startOfWeek(date: Date): Date {
    const d = startOfDay(date);
    const day = d.getDay();
    const diff = (day === 0 ? -6 : 1) - day;
    return addDays(d, diff);
}

export function startOfMonth(date: Date): Date {
    return new Date(date.getFullYear(), date.getMonth(), 1);
}

export function addMonths(date: Date, months: number): Date {
    return new Date(date.getFullYear(), date.getMonth() + months, 1);
}

/** Grid start/end (end exclusive) covering full weeks so the month view has complete rows. */
export function monthGridRange(date: Date): { start: Date; end: Date } {
    const gridStart = startOfWeek(startOfMonth(date));
    const gridEnd = addDays(startOfWeek(addMonths(date, 1)), 7);
    return { start: gridStart, end: gridEnd };
}

export function isSameDay(a: Date, b: Date): boolean {
    return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

/** "HH:MM" labels from work_start to work_end, stepping by slot_minutes. */
export function generateTimeSlots(workStart: string, workEnd: string, slotMinutes: number): string[] {
    const [startH, startM] = workStart.split(":").map(Number);
    const [endH, endM] = workEnd.split(":").map(Number);
    const slots: string[] = [];
    let minutes = startH * 60 + startM;
    const endMinutes = endH * 60 + endM;
    while (minutes < endMinutes) {
        const h = Math.floor(minutes / 60);
        const m = minutes % 60;
        slots.push(`${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`);
        minutes += slotMinutes;
    }
    return slots;
}

/** 0-based slot index of a datetime within the work day, given work_start and slot length. */
export function slotIndexOf(date: Date, workStart: string, slotMinutes: number): number {
    const [startH, startM] = workStart.split(":").map(Number);
    const minutesFromStart = date.getHours() * 60 + date.getMinutes() - (startH * 60 + startM);
    return Math.floor(minutesFromStart / slotMinutes);
}

export function formatTime(iso: string): string {
    return new Date(iso).toLocaleTimeString("uz-UZ", { hour: "2-digit", minute: "2-digit" });
}

export function formatDayLabel(date: Date): string {
    return date.toLocaleDateString("uz-UZ", { weekday: "short", day: "2-digit", month: "2-digit" });
}

export function formatMonthLabel(date: Date): string {
    return date.toLocaleDateString("uz-UZ", { month: "long", year: "numeric" });
}

export function formatWeekRangeLabel(weekStart: Date): string {
    const weekEnd = addDays(weekStart, 6);
    const startLabel = weekStart.toLocaleDateString("uz-UZ", { day: "2-digit", month: "short" });
    const endLabel = weekEnd.toLocaleDateString("uz-UZ", { day: "2-digit", month: "short", year: "numeric" });
    return `${startLabel} — ${endLabel}`;
}

export function formatDateLabel(date: Date): string {
    return date.toLocaleDateString("uz-UZ", { weekday: "long", day: "2-digit", month: "long", year: "numeric" });
}

/** Combine a slot's "HH:MM" with another date's Y-M-D, producing a new local Date. */
export function withTimeOfSlot(date: Date, slot: string): Date {
    const [h, m] = slot.split(":").map(Number);
    const result = new Date(date);
    result.setHours(h, m, 0, 0);
    return result;
}
