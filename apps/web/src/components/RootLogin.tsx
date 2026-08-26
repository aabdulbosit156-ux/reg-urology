import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Label, Spinner, TextInput } from "flowbite-react";
import { CircleAlert, KeyRound, LockKeyhole, ShieldCheck } from "lucide-react";
import { FormEvent, useState } from "react";

import { ApiClientError, rootLogin } from "../api/auth";

export function RootLogin() {
  const queryClient = useQueryClient();
  const [token, setToken] = useState("");
  const login = useMutation({
    mutationFn: rootLogin,
    onSuccess: (session) => {
      setToken("");
      queryClient.setQueryData(["auth", "session"], session);
    },
  });

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
            <h1 className="mt-5 text-2xl font-semibold tracking-tight">Root orqali kirish</h1>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Railway yoki lokal muhitda o‘rnatilgan <code>ADMIN_TOKEN</code> qiymatini kiriting.
            </p>

            {error ? (
              <Alert className="mt-5" color="failure" icon={CircleAlert} role="alert">
                <span className="font-medium">Kirish amalga oshmadi.</span> {error.message}
                {error.requestId ? (
                  <span className="mt-1 block text-xs">So‘rov: {error.requestId}</span>
                ) : null}
              </Alert>
            ) : null}

            <form className="mt-6 space-y-5" onSubmit={submit}>
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
            </form>

            <p className="mt-5 text-xs leading-5 text-slate-500">
              Token brauzer xotirasiga saqlanmaydi va URL orqali yuborilmaydi.
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}
