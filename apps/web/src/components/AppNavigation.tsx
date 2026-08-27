import { Activity, BarChart3, CalendarDays, Settings, Users } from "lucide-react";

import type { AuthSession } from "../api/auth";

export type AppPage = "dashboard" | "patients" | "calendar" | "activity" | "settings";

const items = [
  { key: "dashboard", label: "Boshqaruv", icon: BarChart3 },
  { key: "patients", label: "Bemorlar", icon: Users },
  { key: "calendar", label: "Kalendar", icon: CalendarDays },
  { key: "activity", label: "Faoliyat", icon: Activity },
  { key: "settings", label: "Sozlamalar", icon: Settings },
] as const;

// Faoliyat va Sozlamalar faqat menejerlar (DIRECTOR / root) uchun.
const MANAGER_ONLY = new Set<AppPage>(["activity", "settings"]);

export function AppNavigation({ active, onNavigate, session }: { active: AppPage; onNavigate: (page: AppPage) => void; session: AuthSession }) {
  return <nav aria-label="Asosiy navigatsiya" className="space-y-1">{items.filter((item) => !(MANAGER_ONLY.has(item.key) && session.principal.role === "ADMIN")).map(({ key, label, icon: Icon }) => <button aria-current={active === key ? "page" : undefined} className={`flex min-h-11 w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm font-medium outline-none transition focus-visible:ring-2 focus-visible:ring-brand-600 focus-visible:ring-offset-2 ${active === key ? "bg-brand-50 text-brand-800" : "text-slate-600 hover:bg-slate-100 hover:text-slate-950"}`} key={key} onClick={() => onNavigate(key)} type="button"><Icon aria-hidden="true" className="size-5 shrink-0" /><span>{label}</span></button>)}</nav>;
}
