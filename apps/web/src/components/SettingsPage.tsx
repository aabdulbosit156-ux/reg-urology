import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Badge, Button, Checkbox, Label, Select, TextInput, Textarea } from "flowbite-react";
import { Bell, Bot, Building2, CalendarClock, Link2, UserPlus, Users } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { apiRequest } from "../api/client";
import { botStatusLabel, staffRoleLabel } from "../labels";
import { EmptyState, QueryError, QueryLoading } from "./QueryState";

type Section = "bot" | "clinic" | "schedule" | "notifications" | "staff" | "campaigns";
interface BotStatus { bot_id: number; username: string; display_name: string; status: string; last_update_at: string | null; last_error: string | null }
interface Doctor { id: string; name: string; clinic_address: string; directions: string | null; contact_phone: string; timezone: string; active: boolean }
interface Staff { id: string; full_name: string; telegram_username: string | null; role: string; state: string }
interface Invite { id: string; role: string; state: string; deep_link?: string; qr_data_url?: string; claimed_full_name?: string | null; claimed_username?: string | null }
interface Campaign { id: string; name: string; code: string; utm_source: string; utm_medium: string; utm_campaign: string; deep_link: string | null; qr_data_url: string | null; archived_at: string | null }
interface SettingsVersion { id: string; namespace: string; payload: Record<string, unknown>; version: number; state: string; published_at: string | null }

const sectionItems = [
  ["bot", "Bot va matnlar", Bot],
  ["clinic", "Klinika", Building2],
  ["schedule", "Ish jadvali", CalendarClock],
  ["notifications", "Bildirishnoma", Bell],
  ["staff", "Xodimlar", Users],
  ["campaigns", "UTM", Link2],
] as const;

export function SettingsPage() {
  const queryClient = useQueryClient();
  const [section, setSection] = useState<Section>("bot");
  const [notice, setNotice] = useState<string | null>(null);
  const doctors = useQuery({ queryKey: ["doctors"], queryFn: () => apiRequest<Doctor[]>("/doctors") });
  const doctor = doctors.data?.find((item) => item.active);
  return (
    <div className="space-y-5">
      <div><h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Sozlamalar</h1><p className="mt-1 text-sm text-slate-600">Bot, klinika, jadval, xodim va UTM sozlamalari.</p></div>
      {notice ? <Alert color="success" onDismiss={() => setNotice(null)}>{notice}</Alert> : null}
      <div className="flex gap-2 overflow-x-auto pb-1" role="tablist">{sectionItems.map(([key, label, Icon]) => <Button aria-selected={section === key} color={section === key ? "primary" : "secondary"} key={key} onClick={() => setSection(key)} role="tab" size="sm"><Icon aria-hidden="true" className="mr-2 size-4" />{label}</Button>)}</div>
      {section === "bot" ? <BotSettings onSaved={setNotice} /> : null}
      {section === "clinic" ? <ClinicSettings doctor={doctor} loading={doctors.isPending} onSaved={async () => { await queryClient.invalidateQueries({ queryKey: ["doctors"] }); setNotice("Klinika ma’lumoti saqlandi"); }} /> : null}
      {section === "schedule" ? <ScheduleSettings doctor={doctor} onSaved={setNotice} /> : null}
      {section === "notifications" ? <NotificationSettings onSaved={setNotice} /> : null}
      {section === "staff" ? <StaffSettings /> : null}
      {section === "campaigns" ? <CampaignSettings /> : null}
    </div>
  );
}

function NotificationSettings({ onSaved }: { onSaved: (message: string) => void }) {
  const [enabled, setEnabled] = useState(true);
  const [hours, setHours] = useState("24, 2");
  const [draft, setDraft] = useState<SettingsVersion | null>(null);
  const versions = useQuery({ queryKey: ["settings-versions"], queryFn: () => apiRequest<SettingsVersion[]>("/settings") });
  const published = versions.data?.find((item) => item.namespace === "notifications" && item.state === "published");
  useEffect(() => {
    if (!published) return;
    setEnabled(published.payload.reminders_enabled !== false);
    const savedHours = published.payload.reminder_hours;
    if (Array.isArray(savedHours)) setHours(savedHours.join(", "));
  }, [published]);
  const parsedHours = hours.split(",").map((item) => Number.parseInt(item.trim(), 10)).filter(Number.isFinite);
  const create = useMutation({ mutationFn: () => apiRequest<SettingsVersion>("/settings", { method: "PATCH", body: JSON.stringify({ namespace: "notifications", payload: { reminders_enabled: enabled, reminder_hours: parsedHours } }) }), onSuccess: setDraft });
  const publish = useMutation({ mutationFn: () => apiRequest<SettingsVersion>("/settings/publish", { method: "POST", body: JSON.stringify({ version_id: draft?.id }) }), onSuccess: () => { setDraft(null); onSaved("Bildirishnoma sozlamalari publish qilindi"); void versions.refetch(); } });
  return <section className="max-w-2xl space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div><h2 className="font-semibold">Qabul eslatmalari</h2><p className="mt-1 text-sm text-slate-600">Standart: qabuldan 24 va 2 soat oldin. 1–168 oralig‘ida, ko‘pi bilan 4 ta qiymat kiriting.</p></div><div className="flex items-start gap-2"><Checkbox checked={enabled} id="reminders-enabled" onChange={(event) => setEnabled(event.target.checked)} /><Label htmlFor="reminders-enabled">Telegram eslatmalarini yuborish</Label></div><div><Label htmlFor="reminder-hours">Oldindan necha soat (vergul bilan)</Label><TextInput id="reminder-hours" inputMode="numeric" onChange={(event) => setHours(event.target.value)} placeholder="24, 2" value={hours} /></div>{create.isError ? <QueryError error={create.error} /> : null}{publish.isError ? <QueryError error={publish.error} /> : null}<div className="flex flex-wrap gap-2"><Button color="secondary" disabled={create.isPending || parsedHours.length === 0} onClick={() => create.mutate()}>Draft saqlash</Button><Button color="primary" disabled={!draft || publish.isPending} onClick={() => publish.mutate()}>Publish</Button></div>{published ? <p className="text-xs text-slate-500">Published versiya: {published.version}</p> : null}</section>;
}

function BotSettings({ onSaved }: { onSaved: (message: string) => void }) {
  const queryClient = useQueryClient();
  const [token, setToken] = useState("");
  const [confirmReplace, setConfirmReplace] = useState(false);
  const status = useQuery({ queryKey: ["bot-status"], queryFn: () => apiRequest<BotStatus | null>("/bot-connection"), retry: false });
  const connect = useMutation({
    mutationFn: () => apiRequest<BotStatus>("/bot-connection/connect", { method: "POST", body: JSON.stringify({ token, confirm_replace: confirmReplace }) }),
    onSuccess: async () => { setToken(""); await queryClient.invalidateQueries({ queryKey: ["bot-status"] }); onSaved("Telegram bot ulandi"); },
  });
  return <div className="space-y-4"><section className="max-w-2xl rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex items-center justify-between gap-3"><div><h2 className="font-semibold">Telegram bot</h2><p className="mt-1 text-sm text-slate-600">Token faqat shifrlangan holda serverda saqlanadi.</p></div>{status.data ? <Badge color={status.data.status === "connected" ? "success" : "warning"}>{botStatusLabel(status.data.status)}</Badge> : null}</div>{status.isError && status.error instanceof Error ? <div className="mt-4"><QueryError error={status.error} /></div> : null}{status.data ? <div className="mt-4 rounded-lg bg-slate-50 p-4 text-sm"><p className="font-medium">@{status.data.username}</p><p className="mt-1 text-slate-600">So‘nggi update: {status.data.last_update_at ? new Date(status.data.last_update_at).toLocaleString("uz-UZ") : "hali kelmagan"}</p></div> : null}<form className="mt-5 space-y-3" onSubmit={(event) => { event.preventDefault(); connect.mutate(); }}><div><Label htmlFor="bot-token">Bot token</Label><TextInput autoComplete="off" id="bot-token" onChange={(event) => setToken(event.target.value)} required type="password" value={token} /></div><div className="flex items-start gap-2"><Checkbox checked={confirmReplace} id="confirm-bot-replace" onChange={(event) => setConfirmReplace(event.target.checked)} /><Label htmlFor="confirm-bot-replace">Mavjud botni almashtirishni tasdiqlayman</Label></div>{connect.isError ? <Alert color="failure">{connect.error.message}</Alert> : null}<Button color="primary" disabled={connect.isPending} type="submit">Tekshirish va ulash</Button></form></section><TemplateSettings onSaved={onSaved} /></div>;
}

function TemplateSettings({ onSaved }: { onSaved: (message: string) => void }) {
  const [key, setKey] = useState("welcome");
  const [value, setValue] = useState("Assalomu alaykum. Konsultatsiyaga murojaat qoldirish uchun davom eting.");
  const [draft, setDraft] = useState<SettingsVersion | null>(null);
  const versions = useQuery({ queryKey: ["settings-versions"], queryFn: () => apiRequest<SettingsVersion[]>("/settings") });
  const create = useMutation({ mutationFn: () => apiRequest<SettingsVersion>("/settings", { method: "PATCH", body: JSON.stringify({ namespace: "bot_messages", payload: { [key]: value } }) }), onSuccess: setDraft });
  const publish = useMutation({ mutationFn: () => apiRequest<SettingsVersion>("/settings/publish", { method: "POST", body: JSON.stringify({ version_id: draft?.id }) }), onSuccess: () => { setDraft(null); onSaved("Bot matni publish qilindi"); void versions.refetch(); } });
  const keys = ["welcome", "consent", "full_name_prompt", "phone_prompt", "phone_error", "registered", "reason_prompt", "finished", "already_registered", "appointment_confirmation", "rescheduled", "cancelled", "reminder", "generic_error"];
  return <section className="max-w-2xl rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="font-semibold">Bot matnlari</h2><p className="mt-1 text-sm text-slate-600">Draftni ko‘rib chiqing, so‘ng publish qiling. Placeholderlar: {"{full_name}, {doctor_name}, {date}, {time}, {clinic_address}"}.</p><div className="mt-4 space-y-4"><div><Label htmlFor="template-key">Matn kaliti</Label><Select id="template-key" onChange={(event) => setKey(event.target.value)} value={key}>{keys.map((item) => <option key={item} value={item}>{item}</option>)}</Select></div><div><Label htmlFor="template-value">Matn</Label><Textarea id="template-value" onChange={(event) => setValue(event.target.value)} rows={4} value={value} /></div><div className="rounded-lg border border-slate-200 bg-slate-50 p-4"><p className="text-xs font-medium uppercase text-slate-500">Preview</p><p className="mt-2 whitespace-pre-wrap text-sm">{value}</p></div>{create.isError ? <QueryError error={create.error} /> : null}{publish.isError ? <QueryError error={publish.error} /> : null}<div className="flex gap-2"><Button color="secondary" disabled={create.isPending} onClick={() => create.mutate()}>Draft saqlash</Button><Button color="primary" disabled={!draft || publish.isPending} onClick={() => publish.mutate()}>Publish</Button></div>{versions.data?.find((item) => item.namespace === "bot_messages" && item.state === "published") ? <p className="text-xs text-slate-500">Published versiya: {versions.data.find((item) => item.namespace === "bot_messages" && item.state === "published")?.version}</p> : null}</div></section>;
}

function ClinicSettings({ doctor, loading, onSaved }: { doctor?: Doctor; loading: boolean; onSaved: () => Promise<void> }) {
  const [name, setName] = useState(""); const [address, setAddress] = useState(""); const [directions, setDirections] = useState(""); const [phone, setPhone] = useState("");
  useEffect(() => { if (doctor) { setName(doctor.name); setAddress(doctor.clinic_address); setDirections(doctor.directions ?? ""); setPhone(doctor.contact_phone); } }, [doctor]);
  const save = useMutation({ mutationFn: () => apiRequest<Doctor>("/doctors/primary", { method: "PUT", body: JSON.stringify({ name, clinic_address: address, directions: directions || null, contact_phone: phone }) }), onSuccess: onSaved });
  if (loading) return <QueryLoading />;
  return <form className="max-w-2xl space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm" onSubmit={(event) => { event.preventDefault(); save.mutate(); }}><h2 className="font-semibold">Klinika va doktor</h2><div><Label htmlFor="doctor-name">Doktor nomi</Label><TextInput id="doctor-name" onChange={(event) => setName(event.target.value)} required value={name} /></div><div><Label htmlFor="clinic-address">Klinika manzili</Label><TextInput id="clinic-address" onChange={(event) => setAddress(event.target.value)} required value={address} /></div><div><Label htmlFor="clinic-phone">Aloqa raqami</Label><TextInput id="clinic-phone" onChange={(event) => setPhone(event.target.value)} required value={phone} /></div><div><Label htmlFor="directions">Yo‘l ko‘rsatma</Label><Textarea id="directions" onChange={(event) => setDirections(event.target.value)} rows={3} value={directions} /></div>{save.isError ? <Alert color="failure">{save.error.message}</Alert> : null}<Button color="primary" disabled={save.isPending} type="submit">Saqlash</Button></form>;
}

function ScheduleSettings({ doctor, onSaved }: { doctor?: Doctor; onSaved: (message: string) => void }) {
  const today = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Tashkent" }).format(new Date());
  const [effective, setEffective] = useState(today);
  const [start, setStart] = useState("09:00");
  const [end, setEnd] = useState("13:00");
  const [secondEnabled, setSecondEnabled] = useState(true);
  const [secondStart, setSecondStart] = useState("14:00");
  const [secondEnd, setSecondEnd] = useState("18:00");
  const [activeDays, setActiveDays] = useState([0, 1, 2, 3, 4, 5]);
  const [exceptionDate, setExceptionDate] = useState(today);
  const [exceptionClosed, setExceptionClosed] = useState(true);
  const [exceptionReason, setExceptionReason] = useState("Dam olish kuni");
  const [blockDate, setBlockDate] = useState(today);
  const [blockStart, setBlockStart] = useState("12:00");
  const [blockEnd, setBlockEnd] = useState("12:30");
  const [blockReason, setBlockReason] = useState("Doktor band");
  const save = useMutation({ mutationFn: () => { if (!doctor) throw new Error("Avval doktorni sozlang"); const intervals = [{ start, end }, ...(secondEnabled ? [{ start: secondStart, end: secondEnd }] : [])]; const weekly = Object.fromEntries(Array.from({ length: 7 }, (_, day) => [String(day), activeDays.includes(day) ? intervals : []])); return apiRequest("/schedule/versions", { method: "POST", body: JSON.stringify({ doctor_id: doctor.id, effective_from: effective, weekly_intervals: weekly }) }); }, onSuccess: () => onSaved("Yangi ish jadvali versiyasi saqlandi") });
  const saveException = useMutation({ mutationFn: () => { if (!doctor) throw new Error("Avval doktorni sozlang"); return apiRequest(`/schedule/day-overrides/${exceptionDate}`, { method: "PUT", body: JSON.stringify({ doctor_id: doctor.id, intervals: exceptionClosed ? [] : [{ start, end }, ...(secondEnabled ? [{ start: secondStart, end: secondEnd }] : [])], closed: exceptionClosed, reason: exceptionReason || null }) }); }, onSuccess: () => onSaved("Sana istisnosi saqlandi") });
  const saveBlock = useMutation({ mutationFn: () => { if (!doctor) throw new Error("Avval doktorni sozlang"); return apiRequest("/schedule/blocks", { method: "POST", body: JSON.stringify({ doctor_id: doctor.id, start_at: new Date(`${blockDate}T${blockStart}:00+05:00`).toISOString(), end_at: new Date(`${blockDate}T${blockEnd}:00+05:00`).toISOString(), reason: blockReason }) }); }, onSuccess: () => onSaved("Qisman band blok saqlandi") });
  const dayLabels = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"];
  return <div className="grid gap-4 xl:grid-cols-2"><form className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm" onSubmit={(event) => { event.preventDefault(); save.mutate(); }}><div><h2 className="font-semibold">Haftalik ish vaqti</h2><p className="mt-1 text-sm text-slate-600">Har kun uchun ertalabki va ixtiyoriy ikkinchi interval.</p></div><div><Label htmlFor="schedule-effective">Amal qilish sanasi</Label><TextInput id="schedule-effective" onChange={(event) => setEffective(event.target.value)} type="date" value={effective} /></div><fieldset><legend className="mb-2 text-sm font-medium text-slate-900">Ish kunlari</legend><div className="flex flex-wrap gap-2">{dayLabels.map((label, day) => <label className="flex min-h-11 items-center gap-2 rounded-lg border border-slate-200 px-3" key={label}><Checkbox checked={activeDays.includes(day)} onChange={() => setActiveDays((items) => items.includes(day) ? items.filter((item) => item !== day) : [...items, day])} />{label}</label>)}</div></fieldset><div className="grid gap-3 sm:grid-cols-2"><div><Label htmlFor="schedule-start">1-boshlanish</Label><TextInput id="schedule-start" onChange={(event) => setStart(event.target.value)} step={900} type="time" value={start} /></div><div><Label htmlFor="schedule-end">1-tugash</Label><TextInput id="schedule-end" onChange={(event) => setEnd(event.target.value)} step={900} type="time" value={end} /></div></div><label className="flex items-center gap-2"><Checkbox checked={secondEnabled} onChange={(event) => setSecondEnabled(event.target.checked)} />Ikkinchi interval</label>{secondEnabled ? <div className="grid gap-3 sm:grid-cols-2"><div><Label htmlFor="schedule-second-start">2-boshlanish</Label><TextInput id="schedule-second-start" onChange={(event) => setSecondStart(event.target.value)} step={900} type="time" value={secondStart} /></div><div><Label htmlFor="schedule-second-end">2-tugash</Label><TextInput id="schedule-second-end" onChange={(event) => setSecondEnd(event.target.value)} step={900} type="time" value={secondEnd} /></div></div> : null}{!doctor ? <Alert color="warning">Avval klinika bo‘limida doktorni kiriting.</Alert> : null}{save.isError ? <Alert color="failure">{save.error.message}</Alert> : null}<Button color="primary" disabled={!doctor || save.isPending} type="submit">Yangi versiyani saqlash</Button></form><div className="space-y-4"><form className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm" onSubmit={(event) => { event.preventDefault(); saveException.mutate(); }}><h2 className="font-semibold">Sana istisnosi</h2><div><Label htmlFor="exception-date">Sana</Label><TextInput id="exception-date" onChange={(event) => setExceptionDate(event.target.value)} type="date" value={exceptionDate} /></div><label className="flex items-center gap-2"><Checkbox checked={exceptionClosed} onChange={(event) => setExceptionClosed(event.target.checked)} />To‘liq dam olish</label><div><Label htmlFor="exception-reason">Sabab</Label><TextInput id="exception-reason" onChange={(event) => setExceptionReason(event.target.value)} value={exceptionReason} /></div>{saveException.isError ? <Alert color="failure">{saveException.error.message}</Alert> : null}<Button color="secondary" disabled={!doctor || saveException.isPending} type="submit">Istisnoni saqlash</Button></form><form className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm" onSubmit={(event) => { event.preventDefault(); saveBlock.mutate(); }}><h2 className="font-semibold">Qisman band vaqt</h2><div><Label htmlFor="block-date">Sana</Label><TextInput id="block-date" onChange={(event) => setBlockDate(event.target.value)} type="date" value={blockDate} /></div><div className="grid gap-3 sm:grid-cols-2"><div><Label htmlFor="block-start">Boshlanish</Label><TextInput id="block-start" onChange={(event) => setBlockStart(event.target.value)} step={900} type="time" value={blockStart} /></div><div><Label htmlFor="block-end">Tugash</Label><TextInput id="block-end" onChange={(event) => setBlockEnd(event.target.value)} step={900} type="time" value={blockEnd} /></div></div><div><Label htmlFor="block-reason">Sabab</Label><TextInput id="block-reason" onChange={(event) => setBlockReason(event.target.value)} required value={blockReason} /></div>{saveBlock.isError ? <Alert color="failure">{saveBlock.error.message}</Alert> : null}<Button color="secondary" disabled={!doctor || saveBlock.isPending} type="submit">Blok qo‘shish</Button></form></div></div>;
}

function StaffSettings() {
  const queryClient = useQueryClient(); const [role, setRole] = useState("ADMIN"); const [invite, setInvite] = useState<Invite | null>(null);
  const staff = useQuery({ queryKey: ["staff"], queryFn: () => apiRequest<Staff[]>("/staff") });
  const invites = useQuery({ queryKey: ["staff-invites"], queryFn: () => apiRequest<Invite[]>("/staff/invites") });
  const create = useMutation({ mutationFn: () => apiRequest<Invite>("/staff/invites", { method: "POST", body: JSON.stringify({ role }) }), onSuccess: async (data) => { setInvite(data); await queryClient.invalidateQueries({ queryKey: ["staff"] }); } });
  const approve = useMutation({ mutationFn: (id: string) => apiRequest<Staff>(`/staff/invites/${id}/approve`, { method: "POST" }), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["staff"] }); await queryClient.invalidateQueries({ queryKey: ["staff-invites"] }); } });
  const deactivate = useMutation({ mutationFn: (id: string) => apiRequest<Staff>(`/staff/${id}/deactivate`, { method: "POST" }), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["staff"] }); } });
  return <section className="space-y-4"><form className="flex max-w-lg flex-col gap-3 rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:flex-row sm:items-end" onSubmit={(event) => { event.preventDefault(); create.mutate(); }}><div className="flex-1"><Label htmlFor="invite-role">Xodim roli</Label><Select id="invite-role" onChange={(event) => setRole(event.target.value)} value={role}><option value="ADMIN">Admin</option><option value="DIRECTOR">Director</option></Select></div><Button color="primary" disabled={create.isPending} type="submit"><UserPlus className="mr-2 size-4" />Taklif yaratish</Button></form>{create.isError ? <QueryError error={create.error} /> : null}{approve.isError ? <QueryError error={approve.error} /> : null}{deactivate.isError ? <QueryError error={deactivate.error} /> : null}{invite ? <Alert color="success"><p className="font-medium">Taklif tayyor</p><p className="mt-1 text-sm">Xodim shu QR kodni Telegramda skanerlab yoki havola orqali ochib, taklifni qabul qiladi.</p>{invite.qr_data_url ? <img alt="Xodim taklifi QR kodi" className="mx-auto mt-3 size-48 rounded-lg bg-white p-2" src={invite.qr_data_url} /> : null}{invite.deep_link ? <a className="mt-3 block break-all underline" href={invite.deep_link} rel="noreferrer" target="_blank">{invite.deep_link}</a> : <p className="mt-3 text-sm text-amber-700">QR va havola uchun avval Telegram botni ulang.</p>}</Alert> : null}{invites.data?.filter((item) => item.state === "pending_approval").map((item) => <article className="flex items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4" key={item.id}><div><p className="font-medium">{item.claimed_full_name ?? "Telegram xodim"}</p><p className="text-sm text-slate-600">{staffRoleLabel(item.role)} · tasdiq kutilmoqda</p></div><Button color="primary" onClick={() => approve.mutate(item.id)} size="sm">Tasdiqlash</Button></article>)}{staff.isPending ? <QueryLoading /> : null}{staff.isError ? <QueryError error={staff.error} /> : null}{staff.data?.length === 0 ? <EmptyState title="Xodim yo‘q">Telegram taklif orqali birinchi xodimni qo‘shing.</EmptyState> : null}<div className="grid gap-3 sm:grid-cols-2">{staff.data?.map((item) => <article className="rounded-xl border border-slate-200 bg-white p-4" key={item.id}><div className="flex justify-between gap-3"><div><h3 className="font-medium">{item.full_name}</h3><p className="text-sm text-slate-500">{item.telegram_username ? `@${item.telegram_username}` : "Username yo‘q"}</p></div><Badge color={item.state === "active" ? "success" : "gray"}>{staffRoleLabel(item.role)}</Badge></div>{item.state === "active" ? <Button className="mt-3" color="secondary" onClick={() => deactivate.mutate(item.id)} size="xs">Bloklash</Button> : null}</article>)}</div></section>;
}

function CampaignSettings() {
  const queryClient = useQueryClient(); const [name, setName] = useState(""); const [source, setSource] = useState(""); const [medium, setMedium] = useState("telegram"); const [campaignName, setCampaignName] = useState("");
  const campaigns = useQuery({ queryKey: ["campaigns"], queryFn: () => apiRequest<Campaign[]>("/campaigns") });
  const create = useMutation({ mutationFn: () => apiRequest<Campaign>("/campaigns", { method: "POST", body: JSON.stringify({ name, utm_source: source, utm_medium: medium, utm_campaign: campaignName, utm_content: null, utm_term: null }) }), onSuccess: async () => { setName(""); setSource(""); setCampaignName(""); await queryClient.invalidateQueries({ queryKey: ["campaigns"] }); } });
  return <section className="space-y-4"><form className="grid gap-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm md:grid-cols-2" onSubmit={(event) => { event.preventDefault(); create.mutate(); }}><div><Label htmlFor="campaign-label">Kampaniya nomi</Label><TextInput id="campaign-label" onChange={(event) => setName(event.target.value)} required value={name} /></div><div><Label htmlFor="utm-source">UTM source</Label><TextInput id="utm-source" onChange={(event) => setSource(event.target.value)} required value={source} /></div><div><Label htmlFor="utm-medium">UTM medium</Label><TextInput id="utm-medium" onChange={(event) => setMedium(event.target.value)} required value={medium} /></div><div><Label htmlFor="utm-campaign">UTM campaign</Label><TextInput id="utm-campaign" onChange={(event) => setCampaignName(event.target.value)} required value={campaignName} /></div>{create.isError ? <div className="md:col-span-2"><QueryError error={create.error} /></div> : null}<div className="md:col-span-2"><Button color="primary" disabled={create.isPending} type="submit">Link yaratish</Button></div></form>{campaigns.isPending ? <QueryLoading /> : null}{campaigns.isError ? <QueryError error={campaigns.error} /> : null}<div className="grid gap-3 lg:grid-cols-2">{campaigns.data?.map((item) => <article className="rounded-xl border border-slate-200 bg-white p-4" key={item.id}><div className="flex justify-between gap-3"><h3 className="font-medium">{item.name}</h3><Badge color={item.archived_at ? "gray" : "success"}>{item.archived_at ? "Arxiv" : "Faol"}</Badge></div><p className="mt-1 text-xs text-slate-500">{item.utm_source} / {item.utm_medium} / {item.utm_campaign}</p>{item.deep_link ? <a className="mt-3 block break-all text-sm text-brand-800 underline" href={item.deep_link} rel="noreferrer" target="_blank">{item.deep_link}</a> : <p className="mt-3 text-sm text-amber-700">Link uchun avval botni ulang.</p>}</article>)}</div></section>;
}
