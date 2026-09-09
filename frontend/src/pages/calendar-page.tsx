import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, X as CloseIcon } from "@untitledui/icons";
import { useSearchParams } from "react-router";
import { Tabs } from "@/components/application/tabs/tabs";
import { Button } from "@/components/base/buttons/button";
import { DayView } from "@/components/calendar/day-view";
import { MonthView } from "@/components/calendar/month-view";
import { WeekView } from "@/components/calendar/week-view";
import { PatientSlideout } from "@/components/patients/patient-slideout";
import { useLiveUpdates } from "@/hooks/use-live-updates";
import { ApiError, api } from "@/lib/api-client";
import {
    addDays,
    addMonths,
    formatDateLabel,
    formatMonthLabel,
    formatWeekRangeLabel,
    generateTimeSlots,
    monthGridRange,
    slotIndexOf,
    startOfDay,
    startOfWeek,
    withTimeOfSlot,
} from "@/lib/calendar";
import type { CalendarAppointment } from "@/types/appointment";
import type { ScheduleSettings } from "@/types/settings";

type ViewMode = "day" | "week" | "month";

const VIEW_TABS: { id: ViewMode; label: string }[] = [
    { id: "day", label: "Kun" },
    { id: "week", label: "Hafta" },
    { id: "month", label: "Oy" },
];

const MAX_LOOKAHEAD_DAYS = 21;

function hasFreeSlot(schedule: ScheduleSettings, day: Date, dayAppointments: CalendarAppointment[]): boolean {
    const slots = generateTimeSlots(schedule.work_start, schedule.work_end, schedule.slot_minutes);
    const covered = new Set<number>();
    dayAppointments.forEach((a) => {
        const startIdx = slotIndexOf(new Date(a.start_at), schedule.work_start, schedule.slot_minutes);
        const span = Math.max(1, Math.ceil(a.duration_min / schedule.slot_minutes));
        for (let i = startIdx; i < startIdx + span; i++) covered.add(i);
    });
    const now = new Date();
    return slots.some((slot, idx) => !covered.has(idx) && withTimeOfSlot(day, slot) > now);
}

export const CalendarPage = () => {
    const [searchParams, setSearchParams] = useSearchParams();
    const bookPatientId = searchParams.get("book");
    const bookPatientName = searchParams.get("bookName");

    const [view, setView] = useState<ViewMode>("week");
    const [anchor, setAnchor] = useState(() => startOfDay(new Date()));
    const [appointments, setAppointments] = useState<CalendarAppointment[]>([]);
    const [schedule, setSchedule] = useState<ScheduleSettings | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedPatientId, setSelectedPatientId] = useState<string | null>(null);

    const [isFindingSlot, setIsFindingSlot] = useState(false);
    const [isBooking, setIsBooking] = useState(false);
    const [bookingError, setBookingError] = useState<string | null>(null);

    const range = useMemo(() => {
        if (view === "day") return { start: anchor, end: addDays(anchor, 1) };
        if (view === "week") {
            const weekStart = startOfWeek(anchor);
            return { start: weekStart, end: addDays(weekStart, 7) };
        }
        return monthGridRange(anchor);
    }, [view, anchor]);

    const loadAppointments = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const params = new URLSearchParams({
                start: range.start.toISOString(),
                end: range.end.toISOString(),
            });
            const result = await api.get<CalendarAppointment[]>(`/appointments?${params.toString()}`);
            setAppointments(result);
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "Qabullarni yuklashda xatolik");
        } finally {
            setIsLoading(false);
        }
    }, [range]);

    useEffect(() => {
        loadAppointments();
    }, [loadAppointments]);

    useLiveUpdates(loadAppointments);

    useEffect(() => {
        api
            .get<ScheduleSettings>("/settings/schedule")
            .then(setSchedule)
            .catch(() => setError("Ish vaqti sozlamalarini yuklashda xatolik"));
    }, []);

    // Booking mode: jump straight to the earliest day (starting today) that still has an open slot.
    useEffect(() => {
        if (!bookPatientId || !schedule) return;
        let cancelled = false;

        (async () => {
            setIsFindingSlot(true);
            setBookingError(null);
            let day = startOfDay(new Date());
            for (let i = 0; i < MAX_LOOKAHEAD_DAYS; i++) {
                try {
                    const params = new URLSearchParams({ start: day.toISOString(), end: addDays(day, 1).toISOString() });
                    const dayAppointments = await api.get<CalendarAppointment[]>(`/appointments?${params.toString()}`);
                    if (cancelled) return;
                    if (hasFreeSlot(schedule, day, dayAppointments)) {
                        setView("day");
                        setAnchor(day);
                        setIsFindingSlot(false);
                        return;
                    }
                } catch {
                    if (!cancelled) setBookingError("Bo'sh slotlarni qidirishda xatolik");
                    setIsFindingSlot(false);
                    return;
                }
                day = addDays(day, 1);
            }
            if (!cancelled) {
                setBookingError("Yaqin kunlarda bo'sh slot topilmadi");
                setIsFindingSlot(false);
            }
        })();

        return () => {
            cancelled = true;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [bookPatientId, schedule]);

    const exitBookingMode = () => {
        setSearchParams((prev) => {
            const next = new URLSearchParams(prev);
            next.delete("book");
            next.delete("bookName");
            return next;
        });
        setBookingError(null);
    };

    const handlePickSlot = async (start: Date) => {
        if (!bookPatientId || !schedule) return;
        setIsBooking(true);
        setBookingError(null);
        try {
            await api.patch(`/patients/${bookPatientId}/status`, {
                to_status: "scheduled",
                appointment_start_at: start.toISOString(),
                appointment_duration_min: schedule.slot_minutes,
                note: null,
            });
            await loadAppointments();
            exitBookingMode();
        } catch (err) {
            setBookingError(err instanceof ApiError ? err.message : "Band qilishda xatolik");
        } finally {
            setIsBooking(false);
        }
    };

    const handleReschedule = async (appointmentId: string, newStart: Date) => {
        const previous = appointments;
        setAppointments((current) =>
            current.map((a) => (a.id === appointmentId ? { ...a, start_at: newStart.toISOString() } : a)),
        );
        try {
            await api.patch(`/appointments/${appointmentId}`, { start_at: newStart.toISOString() });
            await loadAppointments();
        } catch (err) {
            setAppointments(previous);
            setError(err instanceof ApiError ? err.message : "Ko'chirishda xatolik");
        }
    };

    const goToday = () => setAnchor(startOfDay(new Date()));
    const goPrev = () => {
        if (view === "day") setAnchor((d) => addDays(d, -1));
        else if (view === "week") setAnchor((d) => addDays(d, -7));
        else setAnchor((d) => addMonths(d, -1));
    };
    const goNext = () => {
        if (view === "day") setAnchor((d) => addDays(d, 1));
        else if (view === "week") setAnchor((d) => addDays(d, 7));
        else setAnchor((d) => addMonths(d, 1));
    };

    const headerLabel =
        view === "day"
            ? formatDateLabel(anchor)
            : view === "week"
              ? formatWeekRangeLabel(startOfWeek(anchor))
              : formatMonthLabel(anchor);

    const bookingMode = bookPatientId
        ? { patientName: bookPatientName ?? "Bemor", onPickSlot: handlePickSlot }
        : undefined;

    return (
        <div className="flex flex-col gap-6">
            {bookPatientId && (
                <div className="flex items-center justify-between gap-3 rounded-xl bg-brand-primary_alt px-4 py-3">
                    <p className="text-sm text-brand-secondary">
                        <strong>{bookPatientName ?? "Bemor"}</strong> uchun qabul vaqtini tanlang
                        {isFindingSlot && " — bo'sh slot qidirilmoqda..."}
                        {isBooking && " — band qilinmoqda..."}
                    </p>
                    <Button size="sm" color="secondary" iconLeading={CloseIcon} onClick={exitBookingMode} aria-label="Bekor qilish" />
                </div>
            )}
            {bookingError && <p className="text-sm text-error-primary">{bookingError}</p>}

            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <h1 className="text-xl font-semibold text-primary">Kalendar</h1>
                {!bookPatientId && (
                    <Tabs selectedKey={view} onSelectionChange={(key) => setView(key as ViewMode)}>
                        <Tabs.List type="button-border" items={VIEW_TABS}>
                            {(item) => <Tabs.Item id={item.id} label={item.label} />}
                        </Tabs.List>
                    </Tabs>
                )}
            </div>

            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Button size="sm" color="secondary" iconLeading={ChevronLeft} onClick={goPrev} aria-label="Oldingi" />
                    <Button size="sm" color="secondary" onClick={goToday}>
                        Bugun
                    </Button>
                    <Button size="sm" color="secondary" iconLeading={ChevronRight} onClick={goNext} aria-label="Keyingi" />
                </div>
                <p className="text-sm font-medium text-secondary capitalize">{headerLabel}</p>
            </div>

            {error && <p className="text-sm text-error-primary">{error}</p>}

            {isLoading || !schedule ? (
                <p className="text-sm text-tertiary">Yuklanmoqda...</p>
            ) : (
                <>
                    {view === "day" && (
                        <DayView
                            date={anchor}
                            appointments={appointments}
                            schedule={schedule}
                            onOpenPatient={setSelectedPatientId}
                            booking={bookingMode}
                        />
                    )}
                    {view === "week" && !bookPatientId && (
                        <WeekView
                            weekStart={startOfWeek(anchor)}
                            appointments={appointments}
                            onOpenPatient={setSelectedPatientId}
                            onReschedule={handleReschedule}
                        />
                    )}
                    {view === "month" && !bookPatientId && (
                        <MonthView
                            monthAnchor={anchor}
                            gridStart={range.start}
                            appointments={appointments}
                            onOpenPatient={setSelectedPatientId}
                            onReschedule={handleReschedule}
                            onSelectDay={(day) => {
                                setAnchor(day);
                                setView("day");
                            }}
                        />
                    )}
                </>
            )}

            <PatientSlideout
                patientId={selectedPatientId}
                onOpenChange={(open) => !open && setSelectedPatientId(null)}
                onChanged={loadAppointments}
            />
        </div>
    );
};
