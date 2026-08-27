import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Badge, Button, Label, Select, TextInput } from "flowbite-react";
import { CalendarOff, ChevronLeft, ChevronRight, Clock3, GripVertical, Phone, Send, UserCheck } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";

import { ApiClientError, apiRequest } from "../api/client";
import { appointmentStatusLabel as statusLabel } from "../labels";
import { EmptyState, QueryError, QueryLoading } from "./QueryState";

interface Doctor { id: string; name: string; clinic_address: string; timezone: string; active: boolean }
interface Slot { start_at: string; end_at: string; available: boolean; state: string }
interface Availability { configured: boolean; slots: Slot[] }
interface Appointment { id: string; inquiry_id: string; start_at: string; end_at: string; status: string; version: number; outcome_pending: boolean; patient_name: string | null; patient_phone: string | null; telegram_user_id: number | null }
interface DaySummary { local_date: string; configured: boolean; total_slots: number; available_slots: number; blocked_slots: number; scheduled: number; checked_in: number; completed: number; no_show: number; cancelled: number }
interface CalendarSummary { days: DaySummary[] }
interface BookableInquiry { inquiry_id: string; patient_name: string; patient_phone: string; registered_at: string; reason: string | null }
export type BookingTarget = { inquiryId: string; name: string; phone: string };
type ViewMode = "day" | "week" | "month";

function isoDate(date: Date) {
  return date.toISOString().slice(0, 10);
}

function tashkentToday() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Tashkent" }).format(new Date());
}

function shiftDate(value: string, days: number) {
  const date = new Date(`${value}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return isoDate(date);
}

function timeLabel(value: string) {
  return new Intl.DateTimeFormat("uz-UZ", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Tashkent", hour12: false }).format(new Date(value));
}

// Monday-first weekday labels; Sunday is the default clinic rest day.
const WEEKDAYS = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"];
const WEEKDAYS_FULL = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"];
const MONTHS = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentyabr", "oktyabr", "noyabr", "dekabr"];

function weekdayIndex(value: string) {
  return (new Date(`${value}T12:00:00Z`).getUTCDay() + 6) % 7; // 0=Mon … 6=Sun
}

function longDate(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return `${WEEKDAYS_FULL[weekdayIndex(value)]}, ${day}-${MONTHS[month - 1]} ${year}`;
}

function isRestDay(value: string) {
  return weekdayIndex(value) === 6;
}

type BadgeColor = "info" | "warning" | "success" | "failure" | "gray";

function statusColor(status: string): BadgeColor {
  return (
    { scheduled: "info", checked_in: "warning", completed: "success", cancelled: "gray", no_show: "failure" } as Record<
      string,
      BadgeColor
    >
  )[status] ?? "gray";
}

// Colour tokens for a booked-appointment chip, keyed by status.
const STATUS_CHIP: Record<string, string> = {
  scheduled: "border-sky-200 bg-sky-50 text-sky-800",
  checked_in: "border-amber-200 bg-amber-50 text-amber-800",
  completed: "border-emerald-200 bg-emerald-50 text-emerald-800",
  cancelled: "border-slate-200 bg-slate-50 text-slate-500",
  no_show: "border-rose-200 bg-rose-50 text-rose-800",
};

function statusChip(status: string) {
  return STATUS_CHIP[status] ?? STATUS_CHIP.cancelled;
}

export function CalendarPage({ initialBooking, canCorrect = false }: { initialBooking?: BookingTarget; canCorrect?: boolean }) {
  const queryClient = useQueryClient();
  const [view, setView] = useState<ViewMode>("day");
  const [date, setDate] = useState(tashkentToday());
  const [selectedSlot, setSelectedSlot] = useState<Slot | null>(null);
  const [bookingTarget, setBookingTarget] = useState<BookingTarget | null>(initialBooking ?? null);
  const [needsPatient, setNeedsPatient] = useState(false);
  const [dragInquiry, setDragInquiry] = useState<BookableInquiry | null>(null);
  const [dragOverStart, setDragOverStart] = useState<string | null>(null);
  const [rescheduleTarget, setRescheduleTarget] = useState<Appointment | null>(null);
  const [rescheduleReason, setRescheduleReason] = useState("Bemor bilan kelishildi");
  const [correctionTarget, setCorrectionTarget] = useState<Appointment | null>(null);
  const [correctionStatus, setCorrectionStatus] = useState("scheduled");
  const [correctionReason, setCorrectionReason] = useState("");
  const doctors = useQuery({ queryKey: ["doctors"], queryFn: () => apiRequest<Doctor[]>("/doctors") });
  const doctor = doctors.data?.find((item) => item.active);
  const range = useMemo(() => {
    if (view === "day") return { from: date, to: date };
    if (view === "week") return { from: date, to: shiftDate(date, 6) };
    const first = `${date.slice(0, 7)}-01`;
    const month = new Date(`${first}T12:00:00Z`);
    month.setUTCMonth(month.getUTCMonth() + 1, 0);
    return { from: first, to: isoDate(month) };
  }, [date, view]);
  const availability = useQuery({
    queryKey: ["availability", doctor?.id, date],
    queryFn: () => apiRequest<Availability>(`/calendar/availability?doctor_id=${doctor?.id}&local_date=${date}`),
    enabled: Boolean(doctor),
  });
  const appointments = useQuery({
    queryKey: ["appointments", doctor?.id, range.from, range.to],
    queryFn: () => apiRequest<Appointment[]>(`/appointments?doctor_id=${doctor?.id}&date_from=${range.from}&date_to=${range.to}`),
    enabled: Boolean(doctor),
  });
  const summary = useQuery({
    queryKey: ["calendar-summary", doctor?.id, range.from, range.to],
    queryFn: () => apiRequest<CalendarSummary>(`/calendar/summary?doctor_id=${doctor?.id}&date_from=${range.from}&date_to=${range.to}`),
    enabled: Boolean(doctor) && view === "month",
  });
  const bookable = useQuery({
    queryKey: ["bookable-inquiries"],
    queryFn: () => apiRequest<BookableInquiry[]>("/bookable-inquiries"),
    enabled: Boolean(doctor),
  });
  const create = useMutation({
    mutationFn: () => {
      if (!bookingTarget || !selectedSlot) throw new Error("Bemor yoki slot tanlanmagan");
      return apiRequest<Appointment>("/appointments", { method: "POST", body: JSON.stringify({ inquiry_id: bookingTarget.inquiryId, doctor_id: doctor?.id, start_at: selectedSlot.start_at }) });
    },
    onSuccess: async () => {
      setSelectedSlot(null);
      setBookingTarget(null);
      await queryClient.invalidateQueries({ queryKey: ["availability"] });
      await queryClient.invalidateQueries({ queryKey: ["appointments"] });
      await queryClient.invalidateQueries({ queryKey: ["bookable-inquiries"] });
      await queryClient.invalidateQueries({ queryKey: ["calendar-summary"] });
    },
  });
  const transition = useMutation({
    mutationFn: ({ appointment, status }: { appointment: Appointment; status: string }) => apiRequest<Appointment>(`/appointments/${appointment.id}/transition`, { method: "POST", body: JSON.stringify({ status, version: appointment.version, reason: null }) }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["appointments"] });
      await queryClient.invalidateQueries({ queryKey: ["availability"] });
    },
  });
  const reschedule = useMutation({
    mutationFn: () => {
      if (!rescheduleTarget || !selectedSlot) throw new Error("Yangi slot tanlanmagan");
      return apiRequest<Appointment>(`/appointments/${rescheduleTarget.id}/reschedule`, {
        method: "POST",
        body: JSON.stringify({
          start_at: selectedSlot.start_at,
          version: rescheduleTarget.version,
          reason: rescheduleReason,
        }),
      });
    },
    onSuccess: async () => {
      setSelectedSlot(null);
      setRescheduleTarget(null);
      await queryClient.invalidateQueries({ queryKey: ["availability"] });
      await queryClient.invalidateQueries({ queryKey: ["appointments"] });
    },
  });
  const correct = useMutation({
    mutationFn: () => {
      if (!correctionTarget) throw new Error("Qabul tanlanmagan");
      return apiRequest<Appointment>(`/appointments/${correctionTarget.id}/correct`, { method: "POST", body: JSON.stringify({ status: correctionStatus, version: correctionTarget.version, reason: correctionReason }) });
    },
    onSuccess: async () => {
      setCorrectionTarget(null);
      setCorrectionReason("");
      await queryClient.invalidateQueries({ queryKey: ["appointments"] });
      await queryClient.invalidateQueries({ queryKey: ["availability"] });
      await queryClient.invalidateQueries({ queryKey: ["calendar-summary"] });
    },
  });
  const dayAppointments = appointments.data?.filter((item) => new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Tashkent" }).format(new Date(item.start_at)) === date) ?? [];
  const bookingError = reschedule.error ?? create.error;
  const todayIso = tashkentToday();
  const openSlots = availability.data?.slots.filter((slot) => slot.available).length ?? 0;

  function move(direction: number) {
    if (view === "month") {
      const next = new Date(`${date}T12:00:00Z`);
      next.setUTCMonth(next.getUTCMonth() + direction);
      setDate(isoDate(next));
      return;
    }
    setDate(shiftDate(date, direction * (view === "day" ? 1 : 7)));
  }

  function chooseSlot(slot: Slot) {
    // A booking needs a patient first; reschedule already carries its target.
    if (rescheduleTarget || bookingTarget) {
      setSelectedSlot(slot);
      setNeedsPatient(false);
    } else {
      setNeedsPatient(true);
    }
  }

  if (doctors.isPending) return <QueryLoading label="Kalendar yuklanmoqda" />;
  if (doctors.isError) return <QueryError error={doctors.error} retry={() => void doctors.refetch()} />;

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div><h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Kalendar</h1><p className="mt-1 text-sm text-slate-600">15 daqiqalik qabul jadvali · Toshkent vaqti UTC+5</p></div>
        <div className="inline-flex gap-1 rounded-xl border border-slate-200 bg-white p-1 shadow-sm" role="group" aria-label="Kalendar ko‘rinishi">{(["day", "week", "month"] as ViewMode[]).map((item) => <button aria-pressed={view === item} className={`min-h-9 rounded-lg px-4 text-sm font-medium transition ${view === item ? "bg-brand-700 text-white shadow-sm" : "text-slate-600 hover:bg-slate-100"}`} key={item} onClick={() => setView(item)} type="button">{{ day: "Kun", week: "Hafta", month: "Oy" }[item]}</button>)}</div>
      </div>
      {!doctor ? <EmptyState title="Doktor sozlanmagan">Sozlamalar bo‘limida klinika va doktor ma’lumotini kiriting.</EmptyState> : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
            <div className="flex items-center gap-2"><Button aria-label="Oldingi davr" color="secondary" onClick={() => move(-1)} size="sm"><ChevronLeft className="size-4" /></Button><TextInput aria-label="Kalendar sanasi" onChange={(event) => setDate(event.target.value)} type="date" value={date} /><Button aria-label="Keyingi davr" color="secondary" onClick={() => move(1)} size="sm"><ChevronRight className="size-4" /></Button><Button className="hidden sm:inline-flex" color={date === todayIso ? "primary" : "secondary"} onClick={() => setDate(todayIso)} size="sm">Bugun</Button></div>
            <div className="flex items-center gap-4">{view === "day" && availability.data?.configured ? <div className="hidden text-right sm:block"><p className="text-lg font-semibold tabular-nums text-brand-700">{openSlots}</p><p className="text-xs text-slate-500">bo‘sh slot</p></div> : null}<div className="text-right"><p className="text-sm font-medium">{doctor.name}</p><p className="text-xs text-slate-500">{doctor.clinic_address}</p></div></div>
          </div>
          {availability.isError ? <QueryError error={availability.error} retry={() => void availability.refetch()} /> : null}
          {appointments.isError ? <QueryError error={appointments.error} retry={() => void appointments.refetch()} /> : null}
          {summary.isError ? <QueryError error={summary.error} retry={() => void summary.refetch()} /> : null}
          {rescheduleTarget ? <Alert color="info">{rescheduleTarget.patient_name ?? "Bemor"} qabulini ko‘chirish uchun yangi bo‘sh slotni tanlang.</Alert> : null}
          {bookingTarget && !rescheduleTarget ? <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-brand-200 bg-brand-50 p-3"><div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-sm"><UserCheck aria-hidden="true" className="size-5 shrink-0 text-brand-700" /><span className="font-medium text-brand-900">{bookingTarget.name}</span><span className="tabular-nums text-brand-700">{bookingTarget.phone}</span><span className="hidden text-brand-600 sm:inline">— endi bo‘sh slotni tanlang</span></div><Button color="secondary" onClick={() => setBookingTarget(null)} size="xs">Bekor qilish</Button></div> : null}
          {needsPatient && !bookingTarget && !rescheduleTarget ? <Alert color="warning">Avval quyidagi «Joylashtirilmagan murojaatlar» ro‘yxatidan bemorni tanlang.</Alert> : null}
          {view === "day" ? (
            <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5" aria-labelledby="day-grid-title">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold" id="day-grid-title">{longDate(date)}{date === todayIso ? <span className="ml-2 align-middle rounded-full bg-brand-100 px-2 py-0.5 text-xs font-medium text-brand-700">Bugun</span> : null}</h2>
                  <p className="mt-0.5 text-xs text-slate-500">Kunlik jadval · 15 daqiqalik oynalar</p>
                </div>
                <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
                  <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-brand-500" />Bo‘sh</span>
                  <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-amber-400" />Band</span>
                  <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-slate-300" />Yopiq</span>
                </div>
              </div>
              {availability.isPending ? <div className="mt-4"><QueryLoading /></div> : null}
              {availability.data && !availability.data.configured ? (
                <div className="mt-4 flex flex-col items-center gap-2 rounded-xl border border-dashed border-slate-300 bg-slate-50 px-6 py-10 text-center">
                  <CalendarOff aria-hidden="true" className="size-8 text-slate-400" />
                  <p className="font-medium text-slate-700">{isRestDay(date) ? "Dam olish kuni" : "Jadval sozlanmagan"}</p>
                  <p className="text-sm text-slate-500">{isRestDay(date) ? "Bu kuni klinika ishlamaydi." : "Bu sana uchun ish vaqti belgilanmagan."}</p>
                </div>
              ) : null}
              <div className="mt-4 hidden grid-cols-4 gap-2 sm:grid md:grid-cols-6 xl:grid-cols-8">
                {availability.data?.slots.map((slot) => {
                  const isOver = Boolean(dragInquiry) && dragOverStart === slot.start_at;
                  return <button
                    className={`min-h-14 rounded-lg border px-2 py-2 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 ${slot.available ? (isOver ? "border-brand-500 bg-brand-100 text-brand-900 ring-2 ring-brand-400" : dragInquiry ? "border-dashed border-brand-400 bg-brand-50 text-brand-800" : "border-brand-200 bg-brand-50 text-brand-800 hover:border-brand-400 hover:bg-brand-100") : slot.state === "occupied" ? "cursor-not-allowed border-amber-200 bg-amber-50 text-amber-700" : "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400"}`}
                    disabled={!slot.available}
                    key={slot.start_at}
                    onClick={() => chooseSlot(slot)}
                    onDragOver={(event) => { if (dragInquiry && slot.available) { event.preventDefault(); setDragOverStart(slot.start_at); } }}
                    onDragLeave={() => setDragOverStart((current) => (current === slot.start_at ? null : current))}
                    onDrop={(event) => { event.preventDefault(); if (dragInquiry && slot.available) { setBookingTarget({ inquiryId: dragInquiry.inquiry_id, name: dragInquiry.patient_name, phone: dragInquiry.patient_phone }); setSelectedSlot(slot); setNeedsPatient(false); setDragInquiry(null); setDragOverStart(null); } }}
                    type="button"
                  ><span className="block tabular-nums">{timeLabel(slot.start_at)}</span><span className="text-[10px] font-normal">{slot.available ? "Bo‘sh" : slot.state === "occupied" ? "Band" : "Yopiq"}</span></button>;
                })}
              </div>
              <div className="mt-4 space-y-2 sm:hidden" aria-label="Mobil agenda">
                {availability.data?.slots.map((slot) => <button className={`flex min-h-14 w-full items-center justify-between rounded-lg border px-4 text-left transition ${slot.available ? "border-brand-200 bg-brand-50 hover:bg-brand-100" : slot.state === "occupied" ? "border-amber-200 bg-amber-50 text-amber-700" : "border-slate-200 bg-slate-50 text-slate-500"}`} disabled={!slot.available} key={slot.start_at} onClick={() => chooseSlot(slot)} type="button"><span className="flex items-center gap-2 font-medium tabular-nums"><Clock3 className="size-4" />{timeLabel(slot.start_at)}</span><Badge color={slot.available ? "success" : slot.state === "occupied" ? "warning" : "gray"}>{slot.available ? "Bo‘sh" : slot.state === "occupied" ? "Band" : "Yopiq"}</Badge></button>)}
              </div>
            </section>
          ) : null}
          {view === "day" && !rescheduleTarget ? (
            <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5" aria-labelledby="bookable-title">
              <div className="flex items-center justify-between gap-2"><h2 className="font-semibold" id="bookable-title">Joylashtirilmagan murojaatlar</h2>{bookable.data ? <Badge color="gray">{bookable.data.length}</Badge> : null}</div>
              <p className="mt-1 text-sm text-slate-500">Javob bergan, hali qabulga yozilmagan bemorlar. Birini tanlang yoki to‘g‘ridan-to‘g‘ri bo‘sh slotga sudrab tashlang.</p>
              {bookable.isPending ? <div className="mt-3"><QueryLoading /></div> : null}
              {bookable.isError ? <div className="mt-3"><QueryError error={bookable.error} retry={() => void bookable.refetch()} /></div> : null}
              {bookable.data?.length === 0 ? <div className="mt-3"><EmptyState title="Ro‘yxat bo‘sh">Barcha javob bergan bemorlar qabulga yozilgan.</EmptyState></div> : null}
              {bookable.data?.length ? <ul className="mt-3 divide-y divide-slate-100">{bookable.data.map((item) => { const selected = bookingTarget?.inquiryId === item.inquiry_id; return <li className={`flex flex-wrap items-center justify-between gap-3 rounded-lg py-3 pl-1 pr-1 transition sm:cursor-grab sm:active:cursor-grabbing ${dragInquiry?.inquiry_id === item.inquiry_id ? "bg-brand-50 opacity-60" : ""}`} draggable key={item.inquiry_id} onDragEnd={() => { setDragInquiry(null); setDragOverStart(null); }} onDragStart={(event) => { event.dataTransfer.effectAllowed = "move"; event.dataTransfer.setData("text/plain", item.inquiry_id); setDragInquiry(item); setNeedsPatient(false); }}><div className="flex min-w-0 items-center gap-2"><GripVertical aria-hidden="true" className="hidden size-4 shrink-0 text-slate-300 sm:block" /><div className="min-w-0"><p className="font-medium">{item.patient_name}</p><p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-slate-500"><span className="tabular-nums">{item.patient_phone}</span>{item.reason ? <span className="truncate">· {item.reason}</span> : null}</p></div></div><Button color={selected ? "primary" : "secondary"} onClick={() => { setBookingTarget({ inquiryId: item.inquiry_id, name: item.patient_name, phone: item.patient_phone }); setNeedsPatient(false); }} size="xs">{selected ? <><UserCheck aria-hidden="true" className="mr-1 size-4" />Tanlangan</> : "Tanlash"}</Button></li>; })}</ul> : null}
            </section>
          ) : null}
          {view === "week" ? <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">{Array.from({ length: 7 }, (_, index) => shiftDate(date, index)).map((day) => { const items = appointments.data?.filter((item) => new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Tashkent" }).format(new Date(item.start_at)) === day) ?? []; const rest = isRestDay(day); const isToday = day === todayIso; return <article className={`flex min-h-40 flex-col rounded-xl border p-3 shadow-sm transition ${isToday ? "border-brand-500 ring-1 ring-brand-500" : "border-slate-200"} ${rest ? "bg-slate-50" : "bg-white"}`} key={day}><button className="flex items-center justify-between gap-2 text-left" onClick={() => { setDate(day); setView("day"); }} type="button"><span><span className="block text-[11px] font-medium uppercase tracking-wide text-slate-400">{WEEKDAYS[weekdayIndex(day)]}</span><span className={`text-base font-semibold ${isToday ? "text-brand-700" : "text-slate-900"}`}>{Number(day.slice(-2))}</span></span>{rest ? <Badge color="gray">Dam</Badge> : items.length ? <Badge color="info">{items.length}</Badge> : null}</button><div className="mt-3 space-y-1.5">{items.map((item) => <button className={`block w-full rounded-md border px-2 py-1.5 text-left text-xs transition hover:brightness-95 ${statusChip(item.status)}`} key={item.id} onClick={() => { setDate(day); setView("day"); }} type="button"><span className="block truncate font-medium">{item.patient_name ?? "Nomaʼlum bemor"}</span><span className="tabular-nums opacity-80">{timeLabel(item.start_at)}</span></button>)}{items.length === 0 ? <p className="mt-1 text-xs text-slate-400">{rest ? "Dam olish kuni" : "Qabul yo‘q"}</p> : null}</div></article>; })}</section> : null}
          {view === "month" ? (() => {
            const monthDays = Array.from({ length: Number(range.to.slice(-2)) }, (_, index) => `${range.from.slice(0, 8)}${String(index + 1).padStart(2, "0")}`);
            const leading = weekdayIndex(monthDays[0]);
            return <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm sm:p-4">
              <div className="grid grid-cols-7 gap-1 sm:gap-2">
                {WEEKDAYS.map((label, index) => <div className={`pb-1 text-center text-[11px] font-semibold uppercase tracking-wide ${index === 6 ? "text-rose-400" : "text-slate-400"}`} key={label}>{label}</div>)}
                {Array.from({ length: leading }, (_, index) => <div key={`blank-${index}`} />)}
                {monthDays.map((day) => {
                  const item = summary.data?.days.find((entry) => entry.local_date === day);
                  const booked = item ? item.scheduled + item.checked_in + item.completed + item.no_show : 0;
                  const rest = item ? !item.configured : isRestDay(day);
                  const isToday = day === todayIso;
                  return <button className={`flex min-h-16 flex-col rounded-lg border p-1.5 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 sm:min-h-24 sm:p-2 ${isToday ? "border-brand-500 ring-1 ring-brand-500" : "border-slate-200 hover:border-brand-400 hover:shadow-sm"} ${rest ? "bg-slate-50" : "bg-white"}`} key={day} onClick={() => { setDate(day); setView("day"); }} type="button">
                    <span className={`text-sm font-semibold ${isToday ? "text-brand-700" : rest ? "text-slate-400" : "text-slate-900"}`}>{Number(day.slice(-2))}</span>
                    {rest ? <span className="mt-auto hidden text-[10px] text-slate-400 sm:block">Dam olish</span> : <>
                      {booked > 0 ? <span className="mt-1 hidden w-fit items-center rounded bg-brand-50 px-1.5 py-0.5 text-[10px] font-medium text-brand-800 sm:inline-flex">{booked} band</span> : null}
                      <span className="mt-auto hidden text-[10px] text-slate-500 sm:block">{item?.available_slots ?? 0} bo‘sh{(item?.no_show ?? 0) > 0 ? ` · ${item?.no_show} kelmadi` : ""}</span>
                      {booked > 0 ? <span className="mt-1 size-1.5 rounded-full bg-brand-500 sm:hidden" /> : null}
                    </>}
                  </button>;
                })}
              </div>
            </section>;
          })() : null}
          {dayAppointments.length ? <section className="space-y-2"><div className="flex items-center justify-between"><h2 className="font-semibold">Shu kundagi qabullar</h2><Badge color="gray">{dayAppointments.length} ta</Badge></div>{dayAppointments.map((item) => <article className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:shadow-md sm:flex-row sm:items-center sm:justify-between" key={item.id}><div className="flex items-start gap-3"><div className="flex min-w-14 flex-col items-center justify-center rounded-lg bg-slate-50 px-2 py-1.5 text-center"><span className="text-sm font-semibold tabular-nums text-slate-900">{timeLabel(item.start_at)}</span><span className="text-[10px] text-slate-400">15 daq</span></div><div><p className="font-medium">{item.patient_name ?? "Nomaʼlum bemor"}</p><div className="mt-1"><Badge color={statusColor(item.status)}>{statusLabel(item.status)}</Badge></div><p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">{item.patient_phone ? <a className="inline-flex items-center gap-1 text-brand-800 hover:underline" href={`tel:${item.patient_phone}`}><Phone aria-hidden="true" className="size-3.5" />{item.patient_phone}</a> : null}{item.telegram_user_id ? <a className="inline-flex items-center gap-1 text-brand-800 hover:underline" href={`tg://user?id=${item.telegram_user_id}`} rel="noreferrer"><Send aria-hidden="true" className="size-3.5" />Telegram</a> : null}</p></div></div><div className="flex flex-wrap gap-2">{item.status === "scheduled" ? <><Button color="secondary" onClick={() => setRescheduleTarget(item)} size="xs">Ko‘chirish</Button><Button color="secondary" onClick={() => transition.mutate({ appointment: item, status: "checked_in" })} size="xs">Keldi</Button></> : null}{item.status === "checked_in" ? <Button color="primary" onClick={() => transition.mutate({ appointment: item, status: "completed" })} size="xs">Yakunlash</Button> : null}{item.outcome_pending ? <Button color="secondary" onClick={() => transition.mutate({ appointment: item, status: "no_show" })} size="xs">Kelmadi</Button> : null}{canCorrect ? <Button color="secondary" onClick={() => { setCorrectionTarget(item); setCorrectionStatus(["scheduled", "checked_in", "completed", "cancelled", "no_show"].find((status) => status !== item.status) ?? "cancelled"); }} size="xs">Tuzatish</Button> : null}</div></article>)}</section> : null}
        </>
      )}
      {selectedSlot ? <div aria-modal="true" className="fixed inset-0 z-40 grid place-items-end bg-slate-950/40 p-0 sm:place-items-center sm:p-4" role="dialog"><form className="w-full max-w-md space-y-4 rounded-t-2xl bg-white p-5 shadow-xl sm:rounded-2xl" onSubmit={(event: FormEvent) => { event.preventDefault(); if (rescheduleTarget) reschedule.mutate(); else create.mutate(); }}><div><h2 className="text-lg font-semibold">{rescheduleTarget ? "Qabulni ko‘chirish" : "Qabulga yozish"}</h2><p className="mt-1 text-sm text-slate-600">{date} · {timeLabel(selectedSlot.start_at)} · 15 daqiqa</p></div>{rescheduleTarget ? <><div className="rounded-lg border border-slate-200 bg-slate-50 p-3"><p className="text-xs font-medium uppercase tracking-wide text-slate-500">Bemor</p><p className="mt-1 font-medium">{rescheduleTarget.patient_name ?? "Nomaʼlum bemor"}</p>{rescheduleTarget.patient_phone ? <p className="text-sm tabular-nums text-slate-600">{rescheduleTarget.patient_phone}</p> : null}</div><div><Label htmlFor="reschedule-reason">Ko‘chirish sababi</Label><TextInput id="reschedule-reason" onChange={(event) => setRescheduleReason(event.target.value)} required value={rescheduleReason} /></div></> : <div className="rounded-lg border border-brand-200 bg-brand-50 p-3"><p className="text-xs font-medium uppercase tracking-wide text-brand-700">Bu bemorni yozamiz</p><p className="mt-1 font-medium text-brand-900">{bookingTarget?.name}</p><p className="text-sm tabular-nums text-brand-800">{bookingTarget?.phone}</p></div>}{bookingError ? <Alert color="failure">{bookingError instanceof ApiClientError && bookingError.code === "SLOT_TAKEN" ? "Bu vaqt hozirgina band qilindi. Slotlar yangilandi." : bookingError.message}</Alert> : null}<div className="flex justify-end gap-2"><Button color="secondary" onClick={() => setSelectedSlot(null)} type="button">Bekor qilish</Button><Button color="primary" disabled={create.isPending || reschedule.isPending} type="submit">Tasdiqlash</Button></div></form></div> : null}
      {correctionTarget ? <div aria-modal="true" className="fixed inset-0 z-40 grid place-items-end bg-slate-950/40 p-0 sm:place-items-center sm:p-4" role="dialog"><form className="w-full max-w-md space-y-4 rounded-t-2xl bg-white p-5 shadow-xl sm:rounded-2xl" onSubmit={(event) => { event.preventDefault(); correct.mutate(); }}><div><h2 className="text-lg font-semibold">Tashrif holatini tuzatish</h2><p className="mt-1 text-sm text-slate-600">Eski tarix o‘chmaydi; correction event va audit yoziladi.</p></div><div><Label htmlFor="correction-status">To‘g‘ri holat</Label><Select id="correction-status" onChange={(event) => setCorrectionStatus(event.target.value)} value={correctionStatus}>{["scheduled", "checked_in", "completed", "cancelled", "no_show"].filter((status) => status !== correctionTarget.status).map((status) => <option key={status} value={status}>{statusLabel(status)}</option>)}</Select></div><div><Label htmlFor="correction-reason">Tuzatish sababi</Label><TextInput id="correction-reason" onChange={(event) => setCorrectionReason(event.target.value)} required value={correctionReason} /></div>{correct.isError ? <QueryError error={correct.error} /> : null}<div className="flex justify-end gap-2"><Button color="secondary" onClick={() => setCorrectionTarget(null)} type="button">Bekor qilish</Button><Button color="primary" disabled={correct.isPending || correctionReason.trim().length < 2} type="submit">Tuzatishni saqlash</Button></div></form></div> : null}
    </div>
  );
}
