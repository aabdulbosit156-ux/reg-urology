import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Badge, Button, Drawer, DrawerItems, Spinner, ThemeProvider } from "flowbite-react";
import { CircleAlert, LogOut, Menu, ShieldCheck, X } from "lucide-react";
import { useState } from "react";

import { getCurrentSession, rootLogout, type AuthSession } from "./api/auth";
import { ApiStatus } from "./components/ApiStatus";
import { AppNavigation, type AppPage } from "./components/AppNavigation";
import { CalendarPage } from "./components/CalendarPage";
import { DashboardPage } from "./components/DashboardPage";
import { PatientsPage } from "./components/PatientsPage";
import { RootLogin } from "./components/RootLogin";
import { SettingsPage } from "./components/SettingsPage";
import { regurologTheme } from "./theme";

function LoadingScreen() {
  return <main className="grid min-h-dvh place-items-center bg-slate-50 px-4"><div className="text-center" role="status"><Spinner aria-label="Sessiya tekshirilmoqda" size="lg" /><p className="mt-4 text-sm text-slate-600">Sessiya tekshirilmoqda…</p></div></main>;
}

function StartupError({ retry }: { retry: () => void }) {
  return <main className="grid min-h-dvh place-items-center bg-slate-50 px-4"><div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><Alert color="failure" icon={CircleAlert}><span className="font-medium">Server tayyor emas.</span> API yoki PostgreSQL ulanishini tekshiring.</Alert><Button className="mt-5 min-h-11 w-full" color="secondary" onClick={retry}>Qayta tekshirish</Button></div></main>;
}

function AppShell({ session }: { session: AuthSession }) {
  const queryClient = useQueryClient();
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false);
  const [page, setPage] = useState<AppPage>("dashboard");
  const [bookingInquiry, setBookingInquiry] = useState<string>();
  const logout = useMutation({ mutationFn: rootLogout, onSuccess: () => queryClient.setQueryData(["auth", "session"], null) });
  function navigate(nextPage: AppPage) { setPage(nextPage); setMobileNavigationOpen(false); }
  function openCalendar(inquiryId: string) { setBookingInquiry(inquiryId); setPage("calendar"); }
  const logoutButton = <Button className="min-h-11" color="secondary" disabled={logout.isPending} onClick={() => logout.mutate()} size="sm"><LogOut aria-hidden="true" className="mr-2 size-4" />Chiqish</Button>;
  const navigation = <AppNavigation active={page} onNavigate={navigate} session={session} />;
  return <div className="min-h-dvh bg-slate-50 text-slate-950">
    <header className="sticky top-0 z-20 flex min-h-16 items-center justify-between border-b border-slate-200 bg-white px-4 lg:hidden"><div><p className="font-semibold">RegUrolog</p><p className="text-xs text-slate-500">Toshkent vaqti · UTC+5</p></div><Button aria-label="Navigatsiyani ochish" className="min-h-11 min-w-11" color="secondary" onClick={() => setMobileNavigationOpen(true)} size="sm"><Menu aria-hidden="true" className="size-5" /></Button></header>
    <Drawer className="max-w-[min(22rem,calc(100vw-2rem))]" onClose={() => setMobileNavigationOpen(false)} open={mobileNavigationOpen} position="left"><div className="mb-5 flex items-center justify-between gap-3"><h2 className="text-lg font-semibold">RegUrolog menyusi</h2><Button aria-label="Menyuni yopish" className="min-h-11 min-w-11" color="secondary" onClick={() => setMobileNavigationOpen(false)} size="sm"><X aria-hidden="true" className="size-5" /></Button></div><DrawerItems>{navigation}<div className="mt-6 border-t border-slate-200 pt-5">{logoutButton}</div></DrawerItems></Drawer>
    <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-slate-200 bg-white p-5 lg:flex lg:flex-col"><div className="mb-8 flex items-center gap-3"><span className="grid size-10 place-items-center rounded-xl bg-brand-700 text-white"><ShieldCheck aria-hidden="true" className="size-5" /></span><div><p className="font-semibold">RegUrolog</p><p className="text-xs text-slate-500">Klinika boshqaruvi</p></div></div>{navigation}<div className="mt-auto border-t border-slate-200 pt-5"><Badge className="mb-3" color="primary">{session.principal.role} · {session.principal.full_name ?? (session.principal.kind === "root" ? "Root sessiya" : "Xodim")}</Badge>{logoutButton}</div></aside>
    <main className="px-4 py-6 sm:px-6 lg:ml-64 lg:px-8 lg:py-8"><div className="mx-auto max-w-7xl">{logout.isError ? <Alert className="mb-5" color="failure" icon={CircleAlert}>Sessiyadan chiqib bo‘lmadi. Sahifani yangilab qayta urinib ko‘ring.</Alert> : null}<div className="mb-5 flex justify-end"><ApiStatus /></div>{page === "dashboard" ? <DashboardPage session={session} /> : null}{page === "patients" ? <PatientsPage onBook={openCalendar} /> : null}{page === "calendar" ? <CalendarPage canCorrect={session.principal.role !== "ADMIN"} initialInquiryId={bookingInquiry} /> : null}{page === "settings" && session.principal.role !== "ADMIN" ? <SettingsPage /> : null}</div></main>
  </div>;
}

export function App() {
  const session = useQuery({ queryKey: ["auth", "session"], queryFn: getCurrentSession, retry: false, staleTime: 30_000 });
  return <ThemeProvider theme={regurologTheme}>{session.isPending ? <LoadingScreen /> : null}{session.isError ? <StartupError retry={() => void session.refetch()} /> : null}{session.data === null ? <RootLogin /> : null}{session.data ? <AppShell session={session.data} /> : null}</ThemeProvider>;
}
