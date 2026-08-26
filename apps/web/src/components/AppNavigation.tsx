import { BarChart3, Settings, Users } from "lucide-react";

const items = [
  { label: "Boshqaruv", icon: BarChart3 },
  { label: "Bemorlar", icon: Users, current: true },
  { label: "Sozlamalar", icon: Settings },
];

export function AppNavigation({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav aria-label="Asosiy navigatsiya" className="space-y-1">
      {items.map(({ label, icon: Icon, current }) => (
        <button
          className={`flex min-h-11 w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm font-medium outline-none transition focus-visible:ring-2 focus-visible:ring-brand-600 focus-visible:ring-offset-2 ${
            current
              ? "bg-brand-50 text-brand-800"
              : "text-slate-600 hover:bg-slate-100 hover:text-slate-950"
          }`}
          key={label}
          onClick={onNavigate}
          type="button"
        >
          <Icon aria-hidden="true" className="size-5 shrink-0" />
          <span>{label}</span>
        </button>
      ))}
    </nav>
  );
}
