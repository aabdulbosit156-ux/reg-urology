import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Badge,
  Button,
  Drawer,
  DrawerItems,
  Spinner,
  ThemeProvider,
} from "flowbite-react";
import { CircleAlert, LogOut, Menu, ShieldCheck, X } from "lucide-react";
import { useState } from "react";

import { getCurrentSession, rootLogout } from "./api/auth";
import { ApiStatus } from "./components/ApiStatus";
import { AppNavigation } from "./components/AppNavigation";
import { RootLogin } from "./components/RootLogin";
import { regurologTheme } from "./theme";

const phaseItems = [
  {
    title: "Root sessiya",
    text: "ADMIN_TOKEN serverda tekshiriladi; brauzerga qisqa, HttpOnly sessiya beriladi.",
  },
  {
    title: "PostgreSQL poydevori",
    text: "Sessiya, rate-limit va audit jadvallari Alembic migratsiyasi bilan boshqariladi.",
  },
  {
    title: "Railway tayyorgarligi",
    text: "Web bitta ochiq manzil beradi, API esa Railway private network ichida qoladi.",
  },
];

function LoadingScreen() {
  return (
    <main className="grid min-h-dvh place-items-center bg-slate-50 px-4">
      <div className="text-center" role="status">
        <Spinner aria-label="Sessiya tekshirilmoqda" size="lg" />
        <p className="mt-4 text-sm text-slate-600">Sessiya tekshirilmoqda…</p>
      </div>
    </main>
  );
}

function StartupError({ retry }: { retry: () => void }) {
  return (
    <main className="grid min-h-dvh place-items-center bg-slate-50 px-4">
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <Alert color="failure" icon={CircleAlert}>
          <span className="font-medium">Server tayyor emas.</span> API yoki PostgreSQL ulanishini
          tekshiring.
        </Alert>
        <Button className="mt-5 min-h-11 w-full" color="secondary" onClick={retry}>
          Qayta tekshirish
        </Button>
      </div>
    </main>
  );
}

function AppShell() {
  const queryClient = useQueryClient();
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false);
  const logout = useMutation({
    mutationFn: rootLogout,
    onSuccess: () => queryClient.setQueryData(["auth", "session"], null),
  });

  const logoutButton = (
    <Button
      className="min-h-11"
      color="secondary"
      disabled={logout.isPending}
      onClick={() => logout.mutate()}
      size="sm"
    >
      <LogOut aria-hidden="true" className="mr-2 size-4" />
      Chiqish
    </Button>
  );

  return (
    <div className="min-h-dvh bg-slate-50 text-slate-950">
      <header className="sticky top-0 z-20 flex min-h-16 items-center justify-between border-b border-slate-200 bg-white px-4 lg:hidden">
        <div>
          <p className="font-semibold">RegUrolog</p>
          <p className="text-xs text-slate-500">Toshkent vaqti · UTC+5</p>
        </div>
        <Button
          aria-label="Navigatsiyani ochish"
          className="min-h-11 min-w-11"
          color="secondary"
          onClick={() => setMobileNavigationOpen(true)}
          size="sm"
        >
          <Menu aria-hidden="true" className="size-5" />
        </Button>
      </header>

      <Drawer
        className="max-w-[min(22rem,calc(100vw-2rem))]"
        onClose={() => setMobileNavigationOpen(false)}
        open={mobileNavigationOpen}
        position="left"
      >
        <div className="mb-5 flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">RegUrolog menyusi</h2>
          <Button
            aria-label="Menyuni yopish"
            className="min-h-11 min-w-11"
            color="secondary"
            onClick={() => setMobileNavigationOpen(false)}
            size="sm"
          >
            <X aria-hidden="true" className="size-5" />
          </Button>
        </div>
        <DrawerItems>
          <AppNavigation onNavigate={() => setMobileNavigationOpen(false)} />
          <div className="mt-6 border-t border-slate-200 pt-5">{logoutButton}</div>
        </DrawerItems>
      </Drawer>

      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-slate-200 bg-white p-5 lg:flex lg:flex-col">
        <div className="mb-8 flex items-center gap-3">
          <span className="grid size-10 place-items-center rounded-xl bg-brand-700 text-white">
            <ShieldCheck aria-hidden="true" className="size-5" />
          </span>
          <div>
            <p className="font-semibold">RegUrolog</p>
            <p className="text-xs text-slate-500">Klinika boshqaruvi</p>
          </div>
        </div>
        <AppNavigation />
        <div className="mt-auto border-t border-slate-200 pt-5">
          <Badge className="mb-3" color="primary">
            DEV · Root sessiya
          </Badge>
          {logoutButton}
        </div>
      </aside>

      <main className="px-4 py-6 sm:px-6 lg:ml-64 lg:px-10 lg:py-10">
        <div className="mx-auto max-w-6xl">
          {logout.isError ? (
            <Alert className="mb-5" color="failure" icon={CircleAlert}>
              Sessiyadan chiqib bo‘lmadi. Sahifani yangilab qayta urinib ko‘ring.
            </Alert>
          ) : null}
          <div className="flex flex-col gap-4 border-b border-slate-200 pb-6 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="mb-2 text-sm font-medium text-brand-700">1-bosqich</p>
              <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
                Xavfsiz kirish poydevori
              </h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600 sm:text-base">
                Root sessiya, PostgreSQL readiness va Railway native deploy kontrakti real API
                bilan ulandi.
              </p>
            </div>
            <ApiStatus />
          </div>

          <section aria-labelledby="tayyorlanganlar" className="py-6 sm:py-8">
            <h2 className="mb-4 text-lg font-semibold" id="tayyorlanganlar">
              Tayyorlangan asoslar
            </h2>
            <div className="grid gap-4 md:grid-cols-3">
              {phaseItems.map((item) => (
                <article
                  className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
                  key={item.title}
                >
                  <h3 className="font-semibold">{item.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{item.text}</p>
                </article>
              ))}
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}

export function App() {
  const session = useQuery({
    queryKey: ["auth", "session"],
    queryFn: getCurrentSession,
    retry: false,
    staleTime: 30_000,
  });

  return (
    <ThemeProvider theme={regurologTheme}>
      {session.isPending ? <LoadingScreen /> : null}
      {session.isError ? <StartupError retry={() => void session.refetch()} /> : null}
      {session.data === null ? <RootLogin /> : null}
      {session.data ? <AppShell /> : null}
    </ThemeProvider>
  );
}
