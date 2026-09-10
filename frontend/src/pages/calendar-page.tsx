import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, SearchLg, X as CloseIcon } from "@untitledui/icons";
import { useSearchParams } from "react-router";
import { Dialog, Modal, ModalOverlay } from "@/components/application/modals/modal";
import { Tabs } from "@/components/application/tabs/tabs";
import { Button } from "@/components/base/buttons/button";
import { Input } from "@/components/base/input/input";
import { DayView } from "@/components/calendar/day-view";
import { MonthView } from "@/components/calendar/month-view";
import { WeekView } from "@/components/calendar/week-view";
import { PageHeader } from "@/components/layout/page-header";
import { PatientSlideout } from "@/components/patients/patient-slideout";
import { useLiveUpdates } from "@/hooks/use-live-updates";
import { ApiError, api } from "@/lib/api-client";
import {
    addDays,
    addMonths,
    generateTimeSlots,
    monthGridRange,
    slotIndexOf,
    startOfDay,
    startOfWeek,
    withTimeOfSlot,
} from "@/lib/calendar";
import { formatFullDateUz, formatMonthYearUz, formatTimeUz, formatWeekRangeUz } from "@/lib/uz-date";
import type { CalendarAppointment } from "@/types/appointment";
import type { Patient, PatientListResponse } from "@/types/patient";
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
    const rescheduleAppointmentId = searchParams.get("appointmentId");

    const [view, setView] = useState<ViewMode>("month");
    const [anchor, setAnchor] = useState(() => startOfDay(new Date()));
    const [appointments, setAppointments] = useState<CalendarAppointment[]>([]);
    const [schedule, setSchedule] = useState<ScheduleSettings | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedPatientId, setSelectedPatientId] = useState<string | null>(null);

    const [isFindingSlot, setIsFindingSlot] = useState(false);
    const [isBooking, setIsBooking] = useState(false);
    const [bookingError, setBookingError] = useState<string | null>(null);

    // Empty-slot patient picker (day view, non-booking mode).
    const [pickSlotStart, setPickSlotStart] = useState<Date | null>(null);
    const [pickerPatients, setPickerPatients] = useState<Patient[]>([]);
    const [pickerSearch, setPickerSearch] = useState("");
    const [pickerLoading, setPickerLoading] = useState(false);
    const [pickerError, setPickerError] = useState<string | null>(null);
    const [assigningId, setAssigningId] = useState<string | null>(null);

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
            next.delete("appointmentId");
            return next;
        });
        setBookingError(null);
    };

    const handlePickSlot = async (start: Date) => {
        if (!bookPatientId || !schedule) return;
        setIsBooking(true);
        setBookingError(null);
        try {
            if (rescheduleAppointmentId) {
                await api.patch(`/appointments/${rescheduleAppointmentId}`, { start_at: start.toISOString() });
            } else {
                await api.patch(`/patients/${bookPatientId}/status`, {
                    to_status: "scheduled",
                    appointment_start_at: start.toISOString(),
                    appointment_duration_min: schedule.slot_minutes,
                    note: null,
                });
            }
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

    const openSlotPicker = useCallback(async (start: Date) => {
        setPickSlotStart(start);
        setPickerSearch("");
        setPickerError(null);
        setPickerLoading(true);
        try {
            const result = await api.get<PatientListResponse>("/patients?segment=new&limit=200");
            setPickerPatients(result.items);
        } catch (err) {
            setPickerError(err instanceof ApiError ? err.message : "Bemorlarni yuklashda xatolik");
        } finally {
            setPickerLoading(false);
        }
    }, []);

    const handleAssignPatient = async (patient: Patient) => {
        if (!pickSlotStart || !schedule) return;
        setAssigningId(patient.id);
        setPickerError(null);
        try {
            await api.patch(`/patients/${patient.id}/status`, {
                to_status: "scheduled",
                appointment_start_at: pickSlotStart.toISOString(),
                appointment_duration_min: schedule.slot_minutes,
                note: null,
            });
            setPickSlotStart(null);
            await loadAppointments();
        } catch (err) {
            setPickerError(err instanceof ApiError ? err.message : "Band qilishda xatolik");
        } finally {
            setAssigningId(null);
        }
    };

    const filteredPickerPatients = pickerPatients.filter((p) => {
        const q = pickerSearch.trim().toLowerCase();
        if (!q) return true;
        return p.full_name.toLowerCase().includes(q) || p.phone.toLowerCase().includes(q);
    });

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
            ? formatFullDateUz(anchor)
            : view === "week"
              ? formatWeekRangeUz(startOfWeek(anchor))
              : formatMonthYearUz(anchor);

    const bookingMode = bookPatientId
        ? { patientName: bookPatientName ?? "Bemor", onPickSlot: handlePickSlot }
        : undefined;

    return (
        <div className="flex flex-col gap-6 px-4 py-6 pb-24 lg:px-0 lg:py-0">
            <PageHeader>
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
            </PageHeader>

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
                            onPickEmptySlot={bookingMode ? undefined : openSlotPicker}
                        />
                    )}
                    {view === "week" && !bookPatientId && (
                        <WeekView
                            weekStart={startOfWeek(anchor)}
                            appointments={appointments}
                            onOpenPatient={setSelectedPatientId}
                            onReschedule={handleReschedule}
                            onSelectDay={(day) => {
                                setAnchor(day);
                                setView("day");
                            }}
                        />
                    )}
                    {view === "month" && !bookPatientId && (
                        <MonthView
                            monthAnchor={anchor}
                            gridStart={range.start}
                            appointments={appointments}
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

            <ModalOverlay isOpen={!!pickSlotStart} onOpenChange={(open) => !open && setPickSlotStart(null)}>
                <Modal>
                    <Dialog>
                        <div className="flex max-h-[80vh] w-full max-w-md flex-col rounded-xl bg-primary p-6 shadow-xl">
                            <h2 className="text-lg font-semibold text-primary">
                                Bemorni qabulga qo'shish
                                {pickSlotStart && <span className="text-brand-secondary"> · {formatTimeUz(pickSlotStart)}</span>}
                            </h2>
                            <p className="mt-1 text-sm text-tertiary">Yangi bemorlardan birini tanlang.</p>

                            <Input
                                icon={SearchLg}
                                aria-label="Qidirish"
                                placeholder="Ism yoki telefon"
                                value={pickerSearch}
                                onChange={setPickerSearch}
                                className="mt-4"
                            />

                            {pickerError && <p className="mt-3 text-sm text-error-primary">{pickerError}</p>}

                            <div className="mt-3 flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto">
                                {pickerLoading ? (
                                    <p className="py-8 text-center text-sm text-tertiary">Yuklanmoqda...</p>
                                ) : filteredPickerPatients.length === 0 ? (
                                    <p className="py-8 text-center text-sm text-tertiary">Yangi bemorlar topilmadi</p>
                                ) : (
                                    filteredPickerPatients.map((p) => (
                                        <button
                                            key={p.id}
                                            type="button"
                                            disabled={assigningId !== null}
                                            onClick={() => handleAssignPatient(p)}
                                            className="flex items-center justify-between gap-3 rounded-lg px-3 py-2.5 text-left outline-focus-ring transition duration-100 ease-linear hover:bg-secondary disabled:opacity-50"
                                        >
                                            <span className="min-w-0">
                                                <span className="block truncate text-sm font-medium text-primary">{p.full_name}</span>
                                                <span className="block truncate text-xs text-tertiary">{p.phone}</span>
                                            </span>
                                            {assigningId === p.id && <span className="text-xs text-tertiary">...</span>}
                                        </button>
                                    ))
                                )}
                            </div>

                            <div className="mt-4 flex justify-end">
                                <Button color="secondary" onClick={() => setPickSlotStart(null)}>
                                    Yopish
                                </Button>
                            </div>
                        </div>
                    </Dialog>
                </Modal>
            </ModalOverlay>
        </div>
    );
};
