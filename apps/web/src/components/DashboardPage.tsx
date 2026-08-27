import { useQuery } from "@tanstack/react-query";
import { Badge } from "flowbite-react";
import { CalendarCheck, PhoneCall, UserCheck, Users } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type { AuthSession } from "../api/auth";
import { apiRequest } from "../api/client";
import { QueryError, QueryLoading } from "./QueryState";

interface Analytics {
  mode: string;
  date_from: string;
  date_to: string;
  metrics: Record<string, number | null>;
  daily: Array<Record<string, string | number>>;
  breakdowns?: Record<string, Array<Record<string, string | number>>>;
}

interface NoShowItem { appointment_id: string; patient_name: string; phone_masked: string; operator_name: string | null; start_at: string; source: string; rescheduled: boolean }

function tashkentDate(offsetDays = 0) {
  const date = new Date(Date.now() + offsetDays * 86_400_000);
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Tashkent",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const value = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${value.year}-${value.month}-${value.day}`;
}

export function DashboardPage({ session }: { session: AuthSession }) {
  const mode = session.principal.role === "ADMIN" ? "activity" : "cohort";
  const query = useQuery({
    queryKey: ["analytics", mode],
    queryFn: () =>
      apiRequest<Analytics>(
        `/analytics/${mode}?date_from=${tashkentDate(-6)}&date_to=${tashkentDate()}`,
      ),
  });
  const noShows = useQuery({
    queryKey: ["no-shows", mode],
    queryFn: () => apiRequest<NoShowItem[]>(`/reports/no-shows?date_from=${tashkentDate(-6)}&date_to=${tashkentDate()}`),
    enabled: mode === "cohort",
  });
  if (query.isPending) return <QueryLoading label="Ko‘rsatkichlar yuklanmoqda" />;
  if (query.isError) return <QueryError error={query.error} retry={() => void query.refetch()} />;

  const metrics = query.data.metrics;
  const cards: Array<[string, number | null | undefined, LucideIcon]> =
    mode === "cohort"
      ? [
          ["Murojaatlar", metrics.inquiries, Users],
          ["Aloqa boshlandi", metrics.contact_started, PhoneCall],
          ["Bemor javob berdi", metrics.answered, UserCheck],
          ["Qabulga yozilgan", metrics.booked, CalendarCheck],
        ]
      : [
          ["Aloqa urinishlari", metrics.contact_attempts, PhoneCall],
          ["Bemor javob berdi", metrics.answered, UserCheck],
          ["Qabullar", metrics.appointments, CalendarCheck],
          ["Yakunlangan", metrics.completed, Users],
        ];
  const maxDaily = Math.max(1, ...query.data.daily.map((item) => Number(item.inquiries ?? item.attempts ?? 0)));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Boshqaruv</h1>
          <p className="mt-1 text-sm text-slate-600">
            {mode === "cohort" ? "Oxirgi 7 kun registratsiya cohorti" : "Oxirgi 7 kunlik o‘z faoliyatingiz"}
          </p>
        </div>
        <Badge className="hidden sm:inline-flex" color="primary">Toshkent vaqti · UTC+5</Badge>
      </div>
      <section aria-label="Asosiy ko‘rsatkichlar" className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        {cards.map(([label, value, Icon]) => (
          <article className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm" key={String(label)}>
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs leading-snug text-slate-600 sm:text-sm">{String(label)}</p>
              <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand-700"><Icon aria-hidden="true" className="size-4 sm:size-5" /></span>
            </div>
            <p className="mt-2 text-2xl font-semibold tabular-nums sm:mt-3 sm:text-3xl">{Number(value ?? 0)}</p>
          </article>
        ))}
      </section>
      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" aria-labelledby="daily-title">
        <h2 className="font-semibold" id="daily-title">Kunlik dinamika</h2>
        <div className="mt-6 flex h-52 items-end gap-2 overflow-x-auto pb-1">
          {query.data.daily.map((item) => {
            const value = Number(item.inquiries ?? item.attempts ?? 0);
            return (
              <div className="flex min-w-12 flex-1 flex-col items-center justify-end gap-2" key={String(item.date)}>
                <span className="text-xs font-medium tabular-nums">{value}</span>
                <div
                  aria-label={`${item.date}: ${value}`}
                  className="w-full max-w-14 rounded-t bg-brand-600"
                  style={{ height: `${Math.max(4, (value / maxDaily) * 144)}px` }}
                />
                <span className="text-[11px] text-slate-500">{String(item.date).slice(5)}</span>
              </div>
            );
          })}
        </div>
      </section>
      {mode === "cohort" && query.data.breakdowns?.utm?.length ? <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm"><h2 className="p-5 font-semibold">UTM natijalari</h2><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="border-y border-slate-200 bg-slate-50 text-xs uppercase text-slate-600"><tr><th className="px-5 py-3">Manba</th><th className="px-5 py-3">Murojaat</th><th className="px-5 py-3">Yozilgan</th></tr></thead><tbody>{query.data.breakdowns.utm.map((item) => <tr className="border-b border-slate-100" key={String(item.source)}><td className="px-5 py-3 font-medium">{item.source}</td><td className="px-5 py-3 tabular-nums">{item.inquiries}</td><td className="px-5 py-3 tabular-nums">{item.booked}</td></tr>)}</tbody></table></div></section> : null}
      {mode === "cohort" ? <section className="space-y-3"><h2 className="font-semibold">Kelmaganlar</h2>{noShows.isPending ? <QueryLoading label="No-show hisoboti yuklanmoqda" /> : null}{noShows.isError ? <QueryError error={noShows.error} /> : null}{noShows.data?.length === 0 ? <p className="rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-600">Tanlangan davrda kelmaganlar yo‘q.</p> : null}{noShows.data?.map((item) => <article className="flex flex-col gap-2 rounded-xl border border-slate-200 bg-white p-4 sm:flex-row sm:items-center sm:justify-between" key={item.appointment_id}><div><p className="font-medium">{item.patient_name}</p><p className="text-sm text-slate-600">{item.phone_masked} · {item.source}</p></div><div className="text-sm sm:text-right"><p>{new Date(item.start_at).toLocaleString("uz-UZ", { timeZone: "Asia/Tashkent" })}</p><p className="text-xs text-slate-500">{item.operator_name ?? "Mas’ul yo‘q"}{item.rescheduled ? " · ko‘chirilgan" : ""}</p></div></article>)}</section> : null}
    </div>
  );
}
