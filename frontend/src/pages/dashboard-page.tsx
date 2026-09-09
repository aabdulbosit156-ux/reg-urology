import { useCallback, useEffect, useState } from "react";
import { CalendarCheck01, ClipboardCheck, TrendUp01, Users01 } from "@untitledui/icons";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { ChartTooltipContent } from "@/components/application/charts/charts-base";
import { useLiveUpdates } from "@/hooks/use-live-updates";
import { ApiError, api } from "@/lib/api-client";
import { useAuth } from "@/providers/auth-provider";
import type { DashboardOut } from "@/types/dashboard";

interface StatCardProps {
    label: string;
    value: number;
    icon: React.FC<{ className?: string }>;
}

const StatCard = ({ label, value, icon: Icon }: StatCardProps) => (
    <div className="flex items-center gap-4 rounded-xl border border-secondary bg-primary p-5">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-brand-secondary">
            <Icon className="size-5 text-fg-brand-primary" />
        </div>
        <div>
            <p className="text-sm text-tertiary">{label}</p>
            <p className="text-2xl font-semibold text-primary">{value}</p>
        </div>
    </div>
);

function formatDay(iso: string): string {
    return new Date(iso).toLocaleDateString("uz-UZ", { day: "2-digit", month: "2-digit" });
}

export const DashboardPage = () => {
    const { me } = useAuth();
    const isAnalyst = me?.role === "analyst";

    const [data, setData] = useState<DashboardOut | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const loadDashboard = useCallback(async () => {
        try {
            const result = await api.get<DashboardOut>("/dashboard");
            setData(result);
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "Ma'lumotlarni yuklashda xatolik");
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        loadDashboard();
    }, [loadDashboard]);

    useLiveUpdates(loadDashboard);

    if (isLoading) {
        return <p className="text-sm text-tertiary">Yuklanmoqda...</p>;
    }

    if (error || !data) {
        return <p className="text-sm text-error-primary">{error ?? "Ma'lumotlar topilmadi"}</p>;
    }

    return (
        <div className="flex flex-col gap-6">
            <div>
                <h1 className="text-xl font-semibold text-primary">Dashboard</h1>
                <p className="text-sm text-tertiary">Klinika faoliyati bo'yicha umumiy ko'rsatkichlar</p>
            </div>

            {isAnalyst ? (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <StatCard label="Jarayondagi bemorlar" value={data.segment_in_progress} icon={Users01} />
                    <StatCard label="Yuklangan analizlar (siz)" value={data.my_analyses_uploaded ?? 0} icon={ClipboardCheck} />
                </div>
            ) : (
                <>
                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                        <StatCard label="Yangi leadlar" value={data.segment_new} icon={Users01} />
                        <StatCard label="Jarayonda" value={data.segment_in_progress} icon={TrendUp01} />
                        <StatCard label="Bugungi qabullar" value={data.appointments_today} icon={CalendarCheck01} />
                        <StatCard label="Kutilayotgan analizlar" value={data.analyses_pending} icon={ClipboardCheck} />
                    </div>

                    <div className="rounded-xl border border-secondary bg-primary p-5">
                        <h2 className="mb-4 text-sm font-semibold text-primary">So'nggi 14 kunlik leadlar</h2>
                        <div className="h-64 w-full">
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={data.daily_leads} margin={{ left: 0, right: 0, top: 8, bottom: 0 }}>
                                    <defs>
                                        <linearGradient id="leadsFill" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="var(--color-utility-brand-500)" stopOpacity={0.35} />
                                            <stop offset="95%" stopColor="var(--color-utility-brand-500)" stopOpacity={0} />
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid vertical={false} className="stroke-border-tertiary" />
                                    <XAxis
                                        dataKey="date"
                                        tickFormatter={formatDay}
                                        tickLine={false}
                                        axisLine={false}
                                        className="text-xs"
                                        tick={{ fill: "currentColor" }}
                                    />
                                    <Tooltip content={<ChartTooltipContent labelFormatter={(label) => formatDay(label as string)} />} />
                                    <Area
                                        type="monotone"
                                        dataKey="count"
                                        name="Leadlar"
                                        stroke="var(--color-utility-brand-600)"
                                        strokeWidth={2}
                                        fill="url(#leadsFill)"
                                    />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
};
