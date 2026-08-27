import { useQuery } from "@tanstack/react-query";
import { Badge, Select } from "flowbite-react";
import { CalendarCheck, ListChecks } from "lucide-react";
import { useState } from "react";

import { apiRequest } from "../api/client";
import { actionLabel, staffRoleLabel } from "../labels";
import { EmptyState, QueryError, QueryLoading } from "./QueryState";

interface StaffStat {
  staff_id: string;
  full_name: string;
  role: string;
  state: string;
  appointments_created: number;
  actions: number;
}

interface ActivityLog {
  id: string;
  occurred_at: string;
  actor_kind: string;
  actor_name: string | null;
  action: string;
  entity_type: string;
  note: string | null;
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString("uz-UZ", { timeZone: "Asia/Tashkent" });
}

export function ActivityPage() {
  const [actor, setActor] = useState("");
  const stats = useQuery({
    queryKey: ["staff-stats"],
    queryFn: () => apiRequest<StaffStat[]>("/activity/staff-stats"),
  });
  const logs = useQuery({
    queryKey: ["activity-logs", actor],
    queryFn: () => apiRequest<ActivityLog[]>(`/activity/logs${actor ? `?actor_id=${actor}` : ""}`),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Faoliyat</h1>
        <p className="mt-1 text-sm text-slate-600">Xodimlar statistikasi va tizim harakatlari tarixi.</p>
      </div>

      <section aria-label="Xodimlar statistikasi">
        {stats.isPending ? <QueryLoading label="Statistika yuklanmoqda" /> : null}
        {stats.isError ? <QueryError error={stats.error} retry={() => void stats.refetch()} /> : null}
        {stats.data?.length === 0 ? <EmptyState title="Xodim yo‘q">Hali biror xodim qo‘shilmagan.</EmptyState> : null}
        {stats.data?.length ? (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {stats.data.map((member) => (
              <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" key={member.staff_id}>
                <div className="flex items-center gap-3">
                  <span className={`grid size-10 shrink-0 place-items-center rounded-full text-sm font-semibold ${member.state === "active" ? "bg-brand-100 text-brand-800" : "bg-slate-100 text-slate-500"}`}>{member.full_name.slice(0, 1).toUpperCase()}</span>
                  <div className="min-w-0">
                    <p className="truncate font-medium">{member.full_name}</p>
                    <p className="text-xs text-slate-500">{staffRoleLabel(member.role)}{member.state !== "active" ? " · bloklangan" : ""}</p>
                  </div>
                </div>
                <div className="mt-4 grid grid-cols-2 gap-3">
                  <div className="rounded-lg bg-slate-50 p-3">
                    <div className="flex items-center gap-1.5 text-brand-700"><CalendarCheck aria-hidden="true" className="size-4" /><span className="text-2xl font-semibold tabular-nums">{member.appointments_created}</span></div>
                    <p className="mt-1 text-xs text-slate-500">Qabulga yozgan</p>
                  </div>
                  <div className="rounded-lg bg-slate-50 p-3">
                    <div className="flex items-center gap-1.5 text-slate-700"><ListChecks aria-hidden="true" className="size-4" /><span className="text-2xl font-semibold tabular-nums">{member.actions}</span></div>
                    <p className="mt-1 text-xs text-slate-500">Amallar</p>
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : null}
      </section>

      <section aria-label="Faoliyat loglari">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-semibold">Faoliyat loglari</h2>
          <div className="w-full sm:w-60">
            <Select aria-label="Xodim bo‘yicha filtr" onChange={(event) => setActor(event.target.value)} value={actor}>
              <option value="">Barcha xodimlar</option>
              {stats.data?.map((member) => <option key={member.staff_id} value={member.staff_id}>{member.full_name}</option>)}
            </Select>
          </div>
        </div>
        {logs.isPending ? <div className="mt-3"><QueryLoading label="Loglar yuklanmoqda" /></div> : null}
        {logs.isError ? <div className="mt-3"><QueryError error={logs.error} retry={() => void logs.refetch()} /></div> : null}
        {logs.data?.length === 0 ? <div className="mt-3"><EmptyState title="Log yo‘q">Tanlangan filtr bo‘yicha harakatlar topilmadi.</EmptyState></div> : null}
        {logs.data?.length ? (
          <div className="mt-3 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-600">
                  <tr><th className="px-4 py-3">Vaqt</th><th className="px-4 py-3">Xodim</th><th className="px-4 py-3">Amal</th><th className="px-4 py-3">Izoh</th></tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {logs.data.map((log) => (
                    <tr key={log.id}>
                      <td className="whitespace-nowrap px-4 py-3 tabular-nums text-slate-600">{formatDateTime(log.occurred_at)}</td>
                      <td className="whitespace-nowrap px-4 py-3 font-medium">{log.actor_name ?? (log.actor_kind === "root" ? "Root operator" : "Tizim")}</td>
                      <td className="px-4 py-3"><Badge color="gray">{actionLabel(log.action)}</Badge></td>
                      <td className="px-4 py-3 text-slate-600">{log.note ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}
