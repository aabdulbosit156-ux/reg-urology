import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Badge, Button, Drawer, DrawerItems, Label, Select, TextInput, Textarea } from "flowbite-react";
import { CalendarCheck, CalendarPlus, FileText, Phone, PhoneCall, RefreshCcw, Search, Send, UserPlus, X } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { apiRequest } from "../api/client";
import { appointmentStatusLabel, contactOutcomeLabel, PATIENT_STATUS_OPTIONS, patientStatusLabel } from "../labels";
import { EmptyState, QueryError, QueryLoading } from "./QueryState";

function formatDateTime(value: string | null) {
  return value ? new Date(value).toLocaleString("uz-UZ", { timeZone: "Asia/Tashkent" }) : "—";
}

interface PatientItem {
  id: string;
  full_name: string;
  phone_masked: string;
  possible_duplicate: boolean;
  first_registered_at: string;
  inquiry_id: string | null;
  inquiry_status: string | null;
  close_reason: string | null;
  assigned_to_name: string | null;
  ever_answered: boolean;
  appointment_status: string | null;
}

interface PatientPage { items: PatientItem[]; total: number; page: number; page_size: number }
interface Timeline { kind: string; title: string; occurred_at: string; detail?: string | null }
interface PatientDetail extends PatientItem {
  phone_e164: string | null;
  telegram_user_id: number;
  reason: string | null;
  assigned_to: string | null;
  next_followup_at: string | null;
  version: number | null;
  timeline: Timeline[];
}
interface Attempt { id: string; inquiry_id: string; phone_e164: string; sheet_id: string; sheet_number: string }
interface ReceptionSheet { id: string; number: string; local_contact_date: string; patient_name: string; phone_e164: string; timezone: string; attempts: Array<Record<string, string | null>>; appointments: Array<Record<string, string | null>> }

export function PatientsPage({ onBook, canManage = false }: { onBook: (target: { inquiryId: string; name: string; phone: string }) => void; canManage?: boolean }) {
  const queryClient = useQueryClient();
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [outcome, setOutcome] = useState("answered");
  const [note, setNote] = useState("");
  const [sheetId, setSheetId] = useState<string | null>(null);
  const [statusDraft, setStatusDraft] = useState("open");
  const [statusReason, setStatusReason] = useState("");
  const filterParams = statusFilter === ""
    ? ""
    : statusFilter === "open" || statusFilter === "closed"
      ? `&status=${statusFilter}`
      : `&status=closed&close_reason=${statusFilter}`;
  const patients = useQuery({
    queryKey: ["patients", search, statusFilter],
    queryFn: () => apiRequest<PatientPage>(`/patients?search=${encodeURIComponent(search)}${filterParams}`),
    refetchInterval: 15_000,
  });
  const detail = useQuery({
    queryKey: ["patient", selectedId],
    queryFn: () => apiRequest<PatientDetail>(`/patients/${selectedId}`),
    enabled: Boolean(selectedId),
  });
  const sheet = useQuery({
    queryKey: ["reception-sheet", sheetId],
    queryFn: () => apiRequest<ReceptionSheet>(`/reception-sheets/${sheetId}/print-data`),
    enabled: Boolean(sheetId),
  });
  const startContact = useMutation({
    mutationFn: (inquiryId: string) =>
      apiRequest<Attempt>(`/inquiries/${inquiryId}/contact-attempts`, {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
      }),
    onSuccess: setAttempt,
  });
  const finishContact = useMutation({
    mutationFn: () =>
      apiRequest(`/contact-attempts/${attempt?.id}/finish`, {
        method: "POST",
        body: JSON.stringify({ outcome, note: note || null, next_followup_at: null }),
      }),
    onSuccess: async () => {
      setAttempt(null);
      setNote("");
      await queryClient.invalidateQueries({ queryKey: ["patient", selectedId] });
      await queryClient.invalidateQueries({ queryKey: ["patients"] });
    },
  });
  const currentStatus = detail.data
    ? detail.data.inquiry_status === "closed"
      ? detail.data.close_reason ?? "other"
      : "open"
    : "open";
  useEffect(() => {
    setStatusDraft(currentStatus);
    setStatusReason("");
  }, [currentStatus, detail.data?.inquiry_id]);
  const changeStatus = useMutation({
    mutationFn: () => {
      const inquiryId = detail.data?.inquiry_id;
      const version = detail.data?.version;
      if (!inquiryId || version == null) throw new Error("Faol murojaat topilmadi");
      if (statusDraft === "open") {
        return apiRequest(`/inquiries/${inquiryId}/reopen`, { method: "POST", body: JSON.stringify({ reason: statusReason, version }) });
      }
      return apiRequest(`/inquiries/${inquiryId}/close`, { method: "POST", body: JSON.stringify({ close_reason: statusDraft, reason: statusReason, version }) });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["patient", selectedId] });
      await queryClient.invalidateQueries({ queryKey: ["patients"] });
      await queryClient.invalidateQueries({ queryKey: ["bookable-inquiries"] });
    },
  });

  function submitSearch(event: FormEvent) {
    event.preventDefault();
    setSearch(searchInput.trim());
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Bemorlar</h1>
        <p className="mt-1 text-sm text-slate-600">Registratsiya, qayta aloqa va qabul tarixini boshqaring.</p>
      </div>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
        <form className="flex flex-1 gap-2" onSubmit={submitSearch} role="search">
          <div className="flex-1">
            <Label className="sr-only" htmlFor="patient-search">Ism yoki telefon bo‘yicha qidirish</Label>
            <TextInput
              id="patient-search"
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Ism yoki telefon…"
              value={searchInput}
            />
          </div>
          <Button color="primary" type="submit"><Search aria-hidden="true" className="mr-2 size-4" />Qidirish</Button>
        </form>
        <div className="sm:w-56">
          <Label className="sr-only" htmlFor="patient-status-filter">Status bo‘yicha filtr</Label>
          <Select id="patient-status-filter" onChange={(event) => setStatusFilter(event.target.value)} value={statusFilter}>
            <option value="">Barcha statuslar</option>
            <option value="open">Ochiq</option>
            <option value="closed">Yopilgan (barchasi)</option>
            <option value="attended">Keldi</option>
            <option value="declined">Rad etdi</option>
            <option value="unreachable">Aloqasiz</option>
            <option value="duplicate">Dublikat</option>
            <option value="cancelled">Bekor qilingan</option>
            <option value="other">Boshqa</option>
          </Select>
        </div>
      </div>
      {patients.isPending ? <QueryLoading label="Bemorlar yuklanmoqda" /> : null}
      {patients.isError ? <QueryError error={patients.error} retry={() => void patients.refetch()} /> : null}
      {patients.data?.items.length === 0 ? <EmptyState title="Bemor topilmadi">Filter yoki qidiruvni o‘zgartirib ko‘ring.</EmptyState> : null}
      {patients.data?.items.length ? (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-600">
                <tr><th className="px-4 py-3">Bemor</th><th className="px-4 py-3">Telefon</th><th className="px-4 py-3">Murojaat</th><th className="px-4 py-3">Mas’ul</th><th className="px-4 py-3"><span className="sr-only">Amal</span></th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {patients.data.items.map((patient) => (
                  <tr key={patient.id}>
                    <td className="px-4 py-3 font-medium">{patient.full_name}{patient.possible_duplicate ? <Badge className="ml-2 inline-flex" color="warning">Dublikat ehtimoli</Badge> : null}</td>
                    <td className="px-4 py-3 tabular-nums text-slate-600">{patient.phone_masked}</td>
                    <td className="px-4 py-3"><Badge color={patient.inquiry_status === "open" ? "success" : "gray"}>{patientStatusLabel(patient.inquiry_status, patient.close_reason)}</Badge></td>
                    <td className="px-4 py-3 text-slate-600">{patient.assigned_to_name ?? "Navbatda"}</td>
                    <td className="px-4 py-3 text-right"><Button color="secondary" onClick={() => setSelectedId(patient.id)} size="xs">Ko‘rish</Button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="divide-y divide-slate-100 md:hidden">
            {patients.data.items.map((patient) => (
              <button className="block min-h-20 w-full p-4 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600" key={patient.id} onClick={() => setSelectedId(patient.id)} type="button">
                <div className="flex items-start justify-between gap-3"><span className="font-medium">{patient.full_name}</span><Badge color={patient.inquiry_status === "open" ? "success" : "gray"}>{patientStatusLabel(patient.inquiry_status, patient.close_reason)}</Badge></div>
                <p className="mt-1 text-sm tabular-nums text-slate-600">{patient.phone_masked} · {patient.assigned_to_name ?? "Navbatda"}</p>
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <Drawer className="w-full max-w-xl" onClose={() => { setSelectedId(null); setAttempt(null); }} open={Boolean(selectedId)} position="right">
        <div className="mb-5 flex items-center justify-between gap-3"><h2 className="text-xl font-semibold">Bemor kartochkasi</h2><Button aria-label="Kartochkani yopish" color="secondary" onClick={() => setSelectedId(null)} size="sm"><X aria-hidden="true" className="size-5" /></Button></div>
        <DrawerItems>
          {detail.isPending ? <QueryLoading /> : null}
          {detail.isError ? <QueryError error={detail.error} retry={() => void detail.refetch()} /> : null}
          {detail.data ? (
            <div className="space-y-6">
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="text-lg font-semibold">{detail.data.full_name}</h3>
                    <div className="mt-2 space-y-1.5 text-sm">
                      {detail.data.phone_e164 ? <a className="inline-flex items-center gap-2 text-brand-800 hover:underline" href={`tel:${detail.data.phone_e164}`}><Phone aria-hidden="true" className="size-4" /><span className="tabular-nums">{detail.data.phone_e164}</span></a> : <span className="inline-flex items-center gap-2 text-slate-600"><Phone aria-hidden="true" className="size-4" /><span className="tabular-nums">{detail.data.phone_masked}</span></span>}
                      {detail.data.telegram_user_id ? <a className="flex items-center gap-2 text-brand-800 hover:underline" href={`tg://user?id=${detail.data.telegram_user_id}`} rel="noreferrer"><Send aria-hidden="true" className="size-4" />Telegram profili</a> : null}
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-1.5">
                    {detail.data.inquiry_status ? <Badge color={detail.data.inquiry_status === "open" ? "success" : "gray"}>{patientStatusLabel(detail.data.inquiry_status, detail.data.close_reason)}</Badge> : null}
                    {detail.data.possible_duplicate ? <Badge color="warning">Dublikat ehtimoli</Badge> : null}
                  </div>
                </div>
              </div>
              {detail.data.reason ? <div className="flex gap-3 rounded-xl border border-slate-200 bg-white p-4"><FileText aria-hidden="true" className="size-5 shrink-0 text-slate-400" /><div><p className="text-xs font-medium uppercase tracking-wide text-slate-500">Murojaat sababi</p><p className="mt-1 text-sm">{detail.data.reason}</p></div></div> : null}
              <div className="flex flex-wrap gap-2">
                {detail.data.inquiry_id && detail.data.inquiry_status === "open" ? <Button color="primary" disabled={startContact.isPending} onClick={() => startContact.mutate(detail.data.inquiry_id!)}><PhoneCall aria-hidden="true" className="mr-2 size-4" />Qayta aloqa</Button> : null}
                {detail.data.inquiry_id && detail.data.ever_answered ? <Button color="secondary" onClick={() => onBook({ inquiryId: detail.data.inquiry_id!, name: detail.data.full_name, phone: detail.data.phone_e164 ?? detail.data.phone_masked })}><CalendarPlus aria-hidden="true" className="mr-2 size-4" />Qabulga yozish</Button> : null}
              </div>
              {startContact.isError ? <QueryError error={startContact.error} /> : null}
              {detail.data.inquiry_id ? (
                <div className="rounded-xl border border-slate-200 bg-white p-4">
                  <div className="flex items-center justify-between gap-2">
                    <div><p className="text-sm font-semibold">Status</p><p className="mt-0.5 text-xs text-slate-500">Hozirgi: {patientStatusLabel(detail.data.inquiry_status, detail.data.close_reason)}</p></div>
                    <RefreshCcw aria-hidden="true" className="size-5 text-slate-400" />
                  </div>
                  <div className="mt-3 space-y-3">
                    <div><Label htmlFor="status-select">Yangi status</Label><Select id="status-select" onChange={(event) => setStatusDraft(event.target.value)} value={statusDraft}>{PATIENT_STATUS_OPTIONS.filter((option) => option.value !== "open" || canManage || detail.data!.inquiry_status === "open").map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</Select></div>
                    <div><Label htmlFor="status-reason">O‘zgarish sababi</Label><TextInput id="status-reason" onChange={(event) => setStatusReason(event.target.value)} placeholder="Nima uchun o‘zgartirilyapti?" value={statusReason} /></div>
                    {changeStatus.isError ? <Alert color="failure">{changeStatus.error.message}</Alert> : null}
                    <Button color="primary" disabled={changeStatus.isPending || statusDraft === currentStatus || statusReason.trim().length < 2} onClick={() => changeStatus.mutate()}>Statusni saqlash</Button>
                  </div>
                </div>
              ) : null}
              {attempt ? (
                <form className="space-y-4 rounded-xl border border-brand-100 bg-brand-50 p-4" onSubmit={(event) => { event.preventDefault(); finishContact.mutate(); }}>
                  <div><p className="font-medium">Aloqa urinishi boshlandi</p><a className="mt-1 inline-block text-lg font-semibold text-brand-800 underline" href={`tel:${attempt.phone_e164}`}>{attempt.phone_e164}</a><button className="mt-1 block text-xs text-brand-800 underline" onClick={() => setSheetId(attempt.sheet_id)} type="button">Varaq: {attempt.sheet_number}</button></div>
                  <div><Label htmlFor="contact-outcome">Natija</Label><Select id="contact-outcome" onChange={(event) => setOutcome(event.target.value)} value={outcome}><option value="answered">Bemor javob berdi</option><option value="no_answer">Javob bermadi</option><option value="busy">Band</option><option value="unreachable">Aloqa qilib bo‘lmadi</option><option value="wrong_number">Noto‘g‘ri raqam</option><option value="aborted">Qo‘ng‘iroq qilinmadi</option></Select></div>
                  <div><Label htmlFor="contact-note">Suhbat izohi</Label><Textarea id="contact-note" onChange={(event) => setNote(event.target.value)} required={outcome === "answered"} rows={3} value={note} /></div>
                  {finishContact.isError ? <Alert color="failure">{finishContact.error.message}</Alert> : null}
                  <Button color="primary" disabled={finishContact.isPending} type="submit">Natijani saqlash</Button>
                </form>
              ) : null}
              <section><h3 className="font-semibold">Tarix</h3><ol className="mt-4 space-y-4">{detail.data.timeline.map((item, index) => { const Icon = item.kind === "contact" ? PhoneCall : item.kind === "appointment" ? CalendarCheck : item.kind === "status" ? RefreshCcw : UserPlus; const tone = item.kind === "contact" ? "bg-sky-100 text-sky-700" : item.kind === "appointment" ? "bg-emerald-100 text-emerald-700" : item.kind === "status" ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-600"; return <li className="flex gap-3" key={`${item.occurred_at}-${index}`}><span className={`grid size-8 shrink-0 place-items-center rounded-full ${tone}`}><Icon aria-hidden="true" className="size-4" /></span><div className="min-w-0 pt-0.5"><p className="text-sm font-medium">{item.title}</p>{item.detail ? <p className="text-xs text-slate-600">{item.detail}</p> : null}<time className="text-xs text-slate-500">{new Date(item.occurred_at).toLocaleString("uz-UZ", { timeZone: "Asia/Tashkent" })}</time></div></li>; })}</ol></section>
            </div>
          ) : null}
        </DrawerItems>
      </Drawer>
      {sheetId ? <div aria-modal="true" className="fixed inset-0 z-50 grid place-items-end bg-slate-950/40 sm:place-items-center sm:p-4" role="dialog"><div className="print-sheet max-h-dvh w-full max-w-3xl overflow-y-auto rounded-t-2xl bg-white p-5 shadow-xl sm:max-h-[90vh] sm:rounded-2xl"><div className="print-hidden flex items-center justify-between gap-3"><h2 className="text-lg font-semibold">Qabul varaqasi</h2><Button aria-label="Varaqani yopish" color="secondary" onClick={() => setSheetId(null)} size="sm"><X className="size-5" /></Button></div>{sheet.isPending ? <div className="mt-4"><QueryLoading /></div> : null}{sheet.isError ? <div className="mt-4"><QueryError error={sheet.error} /></div> : null}{sheet.data ? <div className="mt-5 space-y-5"><header className="border-b border-slate-300 pb-4"><p className="text-xs uppercase text-slate-500">RegUrolog qabul varaqasi</p><h3 className="mt-1 text-xl font-semibold">{sheet.data.number}</h3><p className="mt-2 text-sm">{sheet.data.patient_name} · {sheet.data.phone_e164}</p><p className="text-xs text-slate-500">{sheet.data.local_contact_date} · {sheet.data.timezone}</p></header><section><h4 className="font-semibold">Aloqa urinishlari</h4><div className="mt-2 space-y-2">{sheet.data.attempts.map((item) => <div className="rounded border border-slate-200 p-3 text-sm" key={String(item.id)}>{formatDateTime(item.started_at)} · {contactOutcomeLabel(String(item.outcome))}</div>)}</div></section><section><h4 className="font-semibold">Qabullar</h4><div className="mt-2 space-y-2">{sheet.data.appointments.length ? sheet.data.appointments.map((item) => <div className="rounded border border-slate-200 p-3 text-sm" key={String(item.id)}>{formatDateTime(item.start_at)} · {appointmentStatusLabel(String(item.status))}</div>) : <p className="text-sm text-slate-500">Hali qabul belgilanmagan.</p>}</div></section><Button className="print-hidden" color="primary" onClick={() => window.print()}>Chop etish / PDF</Button></div> : null}</div></div> : null}
    </div>
  );
}
