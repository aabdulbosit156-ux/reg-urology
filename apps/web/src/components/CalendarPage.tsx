import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Badge, Button, Label, Select, TextInput } from "flowbite-react";
import { ChevronLeft, ChevronRight, Clock3 } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";

import { ApiClientError, apiRequest } from "../api/client";
import { EmptyState, QueryError, QueryLoading } from "./QueryState";

interface Doctor { id: string; name: string; clinic_address: string; timezone: string; active: boolean }
interface Slot { start_at: string; end_at: string; available: boolean; state: string }
interface Availability { configured: boolean; slots: Slot[] }
interface Appointment { id: string; inquiry_id: string; start_at: string; end_at: string; status: string; version: number; outcome_pending: boolean }
interface DaySummary { local_date: string; configured: boolean; total_slots: number; available_slots: number; blocked_slots: number; scheduled: number; checked_in: number; completed: number; no_show: number; cancelled: number }
interface CalendarSummary { days: DaySummary[] }
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

function statusLabel(status: string) {
  return { scheduled: "Rejalangan", checked_in: "Keldi", completed: "Yakunlandi", cancelled: "Bekor", no_show: "Kelmadi" }[status] ?? status;
}

export function CalendarPage({ initialInquiryId, canCorrect = false }: { initialInquiryId?: string; canCorrect?: boolean }) {
  const queryClient = useQueryClient();
  const [view, setView] = useState<ViewMode>("day");
  const [date, setDate] = useState(tashkentToday());
  const [selectedSlot, setSelectedSlot] = useState<Slot | null>(null);
  const [inquiryId, setInquiryId] = useState(initialInquiryId ?? "");
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
  const create = useMutation({
    mutationFn: () => apiRequest<Appointment>("/appointments", { method: "POST", body: JSON.stringify({ inquiry_id: inquiryId, doctor_id: doctor?.id, start_at: selectedSlot?.start_at }) }),
    onSuccess: async () => {
      setSelectedSlot(null);
      await queryClient.invalidateQueries({ queryKey: ["availability"] });
      await queryClient.invalidateQueries({ queryKey: ["appointments"] });
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

  function move(direction: number) {
    if (view === "month") {
      const next = new Date(`${date}T12:00:00Z`);
      next.setUTCMonth(next.getUTCMonth() + direction);
      setDate(isoDate(next));
      return;
    }
    setDate(shiftDate(date, direction * (view === "day" ? 1 : 7)));
  }

  if (doctors.isPending) return <QueryLoading label="Kalendar yuklanmoqda" />;
  if (doctors.isError) return <QueryError error={doctors.error} retry={() => void doctors.refetch()} />;

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div><h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Kalendar</h1><p className="mt-1 text-sm text-slate-600">15 daqiqalik qabul jadvali · Toshkent vaqti UTC+5</p></div>
        <div className="flex flex-wrap gap-2" role="group" aria-label="Kalendar ko‘rinishi">{(["day", "week", "month"] as ViewMode[]).map((item) => <Button color={view === item ? "primary" : "secondary"} key={item} onClick={() => setView(item)} size="sm">{{ day: "Kun", week: "Hafta", month: "Oy" }[item]}</Button>)}</div>
      </div>
      {!doctor ? <EmptyState title="Doktor sozlanmagan">Sozlamalar bo‘limida klinika va doktor ma’lumotini kiriting.</EmptyState> : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
            <div className="flex items-center gap-2"><Button aria-label="Oldingi davr" color="secondary" onClick={() => move(-1)} size="sm"><ChevronLeft className="size-4" /></Button><TextInput aria-label="Kalendar sanasi" onChange={(event) => setDate(event.target.value)} type="date" value={date} /><Button aria-label="Keyingi davr" color="secondary" onClick={() => move(1)} size="sm"><ChevronRight className="size-4" /></Button></div>
            <div className="text-right"><p className="text-sm font-medium">{doctor.name}</p><p className="text-xs text-slate-500">{doctor.clinic_address}</p></div>
          </div>
          {availability.isError ? <QueryError error={availability.error} retry={() => void availability.refetch()} /> : null}
          {appointments.isError ? <QueryError error={appointments.error} retry={() => void appointments.refetch()} /> : null}
          {summary.isError ? <QueryError error={summary.error} retry={() => void summary.refetch()} /> : null}
          {rescheduleTarget ? <Alert color="info">#{rescheduleTarget.inquiry_id.slice(0, 8)} qabuli uchun yangi bo‘sh slotni tanlang.</Alert> : null}
          {view === "day" ? (
            <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm" aria-labelledby="day-grid-title">
              <h2 className="font-semibold" id="day-grid-title">Kunlik jadval</h2>
              {availability.isPending ? <div className="mt-4"><QueryLoading /></div> : null}
              {availability.data && !availability.data.configured ? <div className="mt-4"><EmptyState title="Jadval sozlanmagan">Bu sana uchun ish vaqti yo‘q.</EmptyState></div> : null}
              <div className="mt-4 hidden grid-cols-4 gap-2 sm:grid md:grid-cols-6 xl:grid-cols-8">
                {availability.data?.slots.map((slot) => <button className={`min-h-14 rounded-lg border px-2 py-2 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 ${slot.available ? "border-brand-200 bg-brand-50 text-brand-800 hover:bg-brand-100" : "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400"}`} disabled={!slot.available} key={slot.start_at} onClick={() => setSelectedSlot(slot)} type="button"><span className="block tabular-nums">{timeLabel(slot.start_at)}</span><span className="text-[10px] font-normal">{slot.available ? "Bo‘sh" : slot.state === "occupied" ? "Band" : "Yopiq"}</span></button>)}
              </div>
              <div className="mt-4 space-y-2 sm:hidden" aria-label="Mobil agenda">
                {availability.data?.slots.map((slot) => <button className={`flex min-h-14 w-full items-center justify-between rounded-lg border px-4 text-left ${slot.available ? "border-brand-200 bg-brand-50" : "border-slate-200 bg-slate-50 text-slate-500"}`} disabled={!slot.available} key={slot.start_at} onClick={() => setSelectedSlot(slot)} type="button"><span className="flex items-center gap-2 font-medium tabular-nums"><Clock3 className="size-4" />{timeLabel(slot.start_at)}</span><Badge color={slot.available ? "success" : "gray"}>{slot.available ? "Bo‘sh" : slot.state === "occupied" ? "Band" : "Yopiq"}</Badge></button>)}
              </div>
            </section>
          ) : null}
          {view === "week" ? <section className="grid gap-3 md:grid-cols-7">{Array.from({ length: 7 }, (_, index) => shiftDate(date, index)).map((day) => { const items = appointments.data?.filter((item) => new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Tashkent" }).format(new Date(item.start_at)) === day) ?? []; return <article className="min-h-36 rounded-xl border border-slate-200 bg-white p-3" key={day}><h2 className="text-sm font-semibold">{day.slice(5)}</h2><div className="mt-3 space-y-2">{items.map((item) => <div className="rounded bg-brand-50 p-2 text-xs text-brand-800" key={item.id}>{timeLabel(item.start_at)} · {statusLabel(item.status)}</div>)}{items.length === 0 ? <p className="text-xs text-slate-400">Qabul yo‘q</p> : null}</div></article>; })}</section> : null}
          {view === "month" ? <section className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">{Array.from({ length: Number(range.to.slice(-2)) }, (_, index) => `${range.from.slice(0, 8)}${String(index + 1).padStart(2, "0")}`).map((day) => { const item = summary.data?.days.find((entry) => entry.local_date === day); const booked = item ? item.scheduled + item.checked_in + item.completed + item.no_show : 0; return <button className="min-h-28 rounded-xl border border-slate-200 bg-white p-3 text-left hover:border-brand-600 focus-visible:ring-2 focus-visible:ring-brand-600" key={day} onClick={() => { setDate(day); setView("day"); }} type="button"><span className="font-semibold">{Number(day.slice(-2))}</span><span className="mt-3 block text-xs text-slate-600">{booked} yozilgan · {item?.available_slots ?? 0} bo‘sh</span><span className="mt-1 block text-xs text-emerald-700">{item?.completed ?? 0} yakunlangan</span><span className="mt-1 block text-xs text-rose-700">{item?.no_show ?? 0} kelmagan</span></button>; })}</section> : null}
          {dayAppointments.length ? <section className="space-y-2"><h2 className="font-semibold">Shu kundagi qabullar</h2>{dayAppointments.map((item) => <article className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:flex-row sm:items-center sm:justify-between" key={item.id}><div><p className="font-medium tabular-nums">{timeLabel(item.start_at)} · {statusLabel(item.status)}</p><p className="text-xs text-slate-500">Murojaat #{item.inquiry_id.slice(0, 8)}</p></div><div className="flex flex-wrap gap-2">{item.status === "scheduled" ? <><Button color="secondary" onClick={() => setRescheduleTarget(item)} size="xs">Ko‘chirish</Button><Button color="secondary" onClick={() => transition.mutate({ appointment: item, status: "checked_in" })} size="xs">Keldi</Button></> : null}{item.status === "checked_in" ? <Button color="primary" onClick={() => transition.mutate({ appointment: item, status: "completed" })} size="xs">Yakunlash</Button> : null}{item.outcome_pending ? <Button color="secondary" onClick={() => transition.mutate({ appointment: item, status: "no_show" })} size="xs">Kelmadi</Button> : null}{canCorrect ? <Button color="secondary" onClick={() => { setCorrectionTarget(item); setCorrectionStatus(["scheduled", "checked_in", "completed", "cancelled", "no_show"].find((status) => status !== item.status) ?? "cancelled"); }} size="xs">Tuzatish</Button> : null}</div></article>)}</section> : null}
        </>
      )}
      {selectedSlot ? <div aria-modal="true" className="fixed inset-0 z-40 grid place-items-end bg-slate-950/40 p-0 sm:place-items-center sm:p-4" role="dialog"><form className="w-full max-w-md space-y-4 rounded-t-2xl bg-white p-5 shadow-xl sm:rounded-2xl" onSubmit={(event: FormEvent) => { event.preventDefault(); if (rescheduleTarget) reschedule.mutate(); else create.mutate(); }}><div><h2 className="text-lg font-semibold">{rescheduleTarget ? "Qabulni ko‘chirish" : "Qabulga yozish"}</h2><p className="mt-1 text-sm text-slate-600">{date} · {timeLabel(selectedSlot.start_at)} · 15 daqiqa</p></div>{rescheduleTarget ? <div><Label htmlFor="reschedule-reason">Ko‘chirish sababi</Label><TextInput id="reschedule-reason" onChange={(event) => setRescheduleReason(event.target.value)} required value={rescheduleReason} /></div> : <div><Label htmlFor="booking-inquiry">Murojaat ID</Label><TextInput id="booking-inquiry" onChange={(event) => setInquiryId(event.target.value)} required value={inquiryId} /></div>}{bookingError ? <Alert color="failure">{bookingError instanceof ApiClientError && bookingError.code === "SLOT_TAKEN" ? "Bu vaqt hozirgina band qilindi. Slotlar yangilandi." : bookingError.message}</Alert> : null}<div className="flex justify-end gap-2"><Button color="secondary" onClick={() => setSelectedSlot(null)} type="button">Bekor qilish</Button><Button color="primary" disabled={create.isPending || reschedule.isPending} type="submit">Tasdiqlash</Button></div></form></div> : null}
      {correctionTarget ? <div aria-modal="true" className="fixed inset-0 z-40 grid place-items-end bg-slate-950/40 p-0 sm:place-items-center sm:p-4" role="dialog"><form className="w-full max-w-md space-y-4 rounded-t-2xl bg-white p-5 shadow-xl sm:rounded-2xl" onSubmit={(event) => { event.preventDefault(); correct.mutate(); }}><div><h2 className="text-lg font-semibold">Tashrif holatini tuzatish</h2><p className="mt-1 text-sm text-slate-600">Eski tarix o‘chmaydi; correction event va audit yoziladi.</p></div><div><Label htmlFor="correction-status">To‘g‘ri holat</Label><Select id="correction-status" onChange={(event) => setCorrectionStatus(event.target.value)} value={correctionStatus}>{["scheduled", "checked_in", "completed", "cancelled", "no_show"].filter((status) => status !== correctionTarget.status).map((status) => <option key={status} value={status}>{statusLabel(status)}</option>)}</Select></div><div><Label htmlFor="correction-reason">Tuzatish sababi</Label><TextInput id="correction-reason" onChange={(event) => setCorrectionReason(event.target.value)} required value={correctionReason} /></div>{correct.isError ? <QueryError error={correct.error} /> : null}<div className="flex justify-end gap-2"><Button color="secondary" onClick={() => setCorrectionTarget(null)} type="button">Bekor qilish</Button><Button color="primary" disabled={correct.isPending || correctionReason.trim().length < 2} type="submit">Tuzatishni saqlash</Button></div></form></div> : null}
    </div>
  );
}
