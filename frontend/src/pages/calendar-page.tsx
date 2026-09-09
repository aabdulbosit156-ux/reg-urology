import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight } from "@untitledui/icons";
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
    monthGridRange,
    startOfDay,
    startOfWeek,
} from "@/lib/calendar";
import type { CalendarAppointment } from "@/types/appointment";
import type { ScheduleSettings } from "@/types/settings";

type ViewMode = "day" | "week" | "month";

const VIEW_TABS: { id: ViewMode; label: string }[] = [
    { id: "day", label: "Kun" },
    { id: "week", label: "Hafta" },
    { id: "month", label: "Oy" },
];

export const CalendarPage = () => {
    const [view, setView] = useState<ViewMode>("week");
    const [anchor, setAnchor] = useState(() => startOfDay(new Date()));
    const [appointments, setAppointments] = useState<CalendarAppointment[]>([]);
    const [schedule, setSchedule] = useState<ScheduleSettings | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedPatientId, setSelectedPatientId] = useState<string | null>(null);

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

    return (
        <div className="flex flex-col gap-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <h1 className="text-xl font-semibold text-primary">Kalendar</h1>
                <Tabs selectedKey={view} onSelectionChange={(key) => setView(key as ViewMode)}>
                    <Tabs.List type="button-border" items={VIEW_TABS}>
                        {(item) => <Tabs.Item id={item.id} label={item.label} />}
                    </Tabs.List>
                </Tabs>
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
                        <DayView appointments={appointments} schedule={schedule} onOpenPatient={setSelectedPatientId} />
                    )}
                    {view === "week" && (
                        <WeekView
                            weekStart={startOfWeek(anchor)}
                            appointments={appointments}
                            onOpenPatient={setSelectedPatientId}
                            onReschedule={handleReschedule}
                        />
                    )}
                    {view === "month" && (
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
