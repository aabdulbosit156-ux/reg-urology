import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Label, Spinner, TextInput } from "flowbite-react";
import { CircleAlert, KeyRound, LockKeyhole, ShieldCheck } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import {
  ApiClientError,
  createStaffChallenge,
  exchangeStaffChallenge,
  getStaffChallenge,
  rootLogin,
  type LoginChallenge,
} from "../api/auth";

export function RootLogin() {
  const queryClient = useQueryClient();
  const [token, setToken] = useState("");
  const [mode, setMode] = useState<"staff" | "root">("staff");
  const [challenge, setChallenge] = useState<LoginChallenge | null>(null);
  const login = useMutation({
    mutationFn: rootLogin,
    onSuccess: (session) => {
      setToken("");
      queryClient.setQueryData(["auth", "session"], session);
    },
  });
  const staffLogin = useMutation({
    mutationFn: createStaffChallenge,
    onSuccess: setChallenge,
  });
  const exchange = useMutation({
    mutationFn: exchangeStaffChallenge,
    onSuccess: (session) => queryClient.setQueryData(["auth", "session"], session),
  });

  useEffect(() => {
    if (!challenge || ["rejected", "expired", "consumed"].includes(challenge.state)) return;
    const timer = window.setInterval(() => {
      void getStaffChallenge()
        .then((current) => {
          setChallenge((previous) => ({ ...current, deep_link: previous?.deep_link, qr_data_url: previous?.qr_data_url }));
          if (current.state === "approved" && !exchange.isPending) exchange.mutate();
        })
        .catch(() => undefined);
    }, 2_000);
    return () => window.clearInterval(timer);
  }, [challenge, exchange]);

  const error = login.error instanceof ApiClientError ? login.error : null;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (token.trim()) login.mutate(token);
  }

  return (
    <main className="grid min-h-dvh bg-slate-50 lg:grid-cols-[minmax(0,1fr)_minmax(28rem,0.8fr)]">
      <section className="hidden bg-brand-800 px-10 py-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="flex items-center gap-3">
          <span className="grid size-11 place-items-center rounded-xl bg-white/10">
            <ShieldCheck aria-hidden="true" className="size-6" />
          </span>
          <div>
            <p className="text-lg font-semibold">RegUrolog</p>
            <p className="text-sm text-teal-100">Klinika boshqaruv tizimi</p>
          </div>
        </div>
        <div className="max-w-xl">
          <p className="text-sm font-medium text-teal-100">Xavfsiz dastlabki sozlash</p>
          <h1 className="mt-3 text-4xl font-semibold leading-tight tracking-tight">
            Root kirish faqat tizim operatori uchun
          </h1>
          <p className="mt-5 max-w-lg text-base leading-7 text-teal-50">
            Root sessiya bir soatga beriladi. Kundalik ishda har bir xodim o‘z Telegram hisobi
            orqali kiradi.
          </p>
        </div>
        <p className="text-sm text-teal-100">Toshkent vaqti · UTC+5</p>
      </section>

      <section className="flex min-h-dvh items-center justify-center px-4 py-8 sm:px-8">
        <div className="w-full max-w-md">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <span className="grid size-11 place-items-center rounded-xl bg-brand-700 text-white">
              <ShieldCheck aria-hidden="true" className="size-6" />
            </span>
            <div>
              <p className="font-semibold">RegUrolog</p>
              <p className="text-sm text-slate-500">Klinika boshqaruv tizimi</p>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-8">
            <span className="grid size-12 place-items-center rounded-xl bg-brand-50 text-brand-800">
              <KeyRound aria-hidden="true" className="size-6" />
            </span>
            <div className="mt-5 flex gap-2" role="tablist"><Button aria-selected={mode === "staff"} color={mode === "staff" ? "primary" : "secondary"} onClick={() => setMode("staff")} role="tab" size="sm">Xodim</Button><Button aria-selected={mode === "root"} color={mode === "root" ? "primary" : "secondary"} onClick={() => setMode("root")} role="tab" size="sm">Root</Button></div>
            <h1 className="mt-5 text-2xl font-semibold tracking-tight">{mode === "staff" ? "Telegram orqali kirish" : "Root orqali kirish"}</h1>
            <p className="mt-2 text-sm leading-6 text-slate-600">{mode === "staff" ? "Shaxsiy Telegram hisobingizda kirishni tasdiqlang." : <>Railway yoki lokal muhitda o‘rnatilgan <code>ADMIN_TOKEN</code> qiymatini kiriting.</>}</p>

            {error ? (
              <Alert className="mt-5" color="failure" icon={CircleAlert} role="alert">
                <span className="font-medium">Kirish amalga oshmadi.</span> {error.message}
                {error.requestId ? (
                  <span className="mt-1 block text-xs">So‘rov: {error.requestId}</span>
                ) : null}
              </Alert>
            ) : null}

            {mode === "root" ? <form className="mt-6 space-y-5" onSubmit={submit}>
              <div>
                <Label htmlFor="admin-token">Admin token</Label>
                <TextInput
                  autoComplete="current-password"
                  className="mt-2"
                  disabled={login.isPending}
                  icon={LockKeyhole}
                  id="admin-token"
                  minLength={1}
                  onChange={(event) => {
                    setToken(event.target.value);
                    if (login.isError) login.reset();
                  }}
                  placeholder="Tokenni kiriting"
                  required
                  type="password"
                  value={token}
                />
              </div>
              <Button
                className="min-h-11 w-full"
                color="primary"
                disabled={login.isPending || !token.trim()}
                type="submit"
              >
                {login.isPending ? (
                  <>
                    <Spinner aria-label="Kirish tekshirilmoqda" className="mr-2" size="sm" />
                    Tekshirilmoqda…
                  </>
                ) : (
                  "Xavfsiz kirish"
                )}
              </Button>
            </form> : <div className="mt-6 space-y-4">{staffLogin.isError ? <Alert color="failure">{staffLogin.error.message}</Alert> : null}{exchange.isError ? <Alert color="failure">{exchange.error.message}</Alert> : null}{challenge ? <div className="text-center">{challenge.qr_data_url ? <img alt="Telegram kirish QR kodi" className="mx-auto size-48" src={challenge.qr_data_url} /> : null}<p className="mt-3 text-sm text-slate-600">Moslashtirish kodi</p><p className="mt-1 text-3xl font-semibold tracking-[0.2em] tabular-nums">{challenge.matching_code}</p>{challenge.deep_link ? <a className="mt-4 flex min-h-11 w-full items-center justify-center rounded-lg bg-brand-700 px-4 text-sm font-medium text-white hover:bg-brand-800 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-brand-100" href={challenge.deep_link} rel="noreferrer" target="_blank">Telegramda ochish</a> : null}<p aria-live="polite" className="mt-3 text-xs text-slate-500">Holat: {challenge.state === "approved" ? "Tasdiqlandi" : challenge.state === "awaiting_confirmation" ? "Telegramda tasdiqlash kutilmoqda" : "Telegram ochilishi kutilmoqda"}</p></div> : <Button className="w-full" color="primary" disabled={staffLogin.isPending} onClick={() => staffLogin.mutate()}>{staffLogin.isPending ? "Tayyorlanmoqda…" : "Telegram bilan kirish"}</Button>}</div>}

            <p className="mt-5 text-xs leading-5 text-slate-500">
              Token brauzer xotirasiga saqlanmaydi va URL orqali yuborilmaydi.
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}
