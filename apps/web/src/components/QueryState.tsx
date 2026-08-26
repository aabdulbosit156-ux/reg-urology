import { Alert, Button, Spinner } from "flowbite-react";
import { CircleAlert, Inbox } from "lucide-react";
import type { ReactNode } from "react";

import { ApiClientError } from "../api/client";

export function QueryLoading({ label = "Ma’lumotlar yuklanmoqda" }: { label?: string }) {
  return (
    <div className="grid min-h-48 place-items-center rounded-xl border border-slate-200 bg-white p-6" role="status">
      <div className="text-center">
        <Spinner aria-label={label} />
        <p className="mt-3 text-sm text-slate-600">{label}…</p>
      </div>
    </div>
  );
}

export function QueryError({ error, retry }: { error: Error; retry?: () => void }) {
  const apiError = error instanceof ApiClientError ? error : null;
  return (
    <Alert color={apiError?.status === 403 ? "warning" : "failure"} icon={CircleAlert}>
      <div>
        <p className="font-medium">
          {apiError?.status === 403 ? "Bu bo‘lim uchun ruxsat yo‘q" : error.message}
        </p>
        {apiError?.requestId ? <p className="mt-1 text-xs">So‘rov: {apiError.requestId}</p> : null}
        {retry ? (
          <Button className="mt-3" color="secondary" onClick={retry} size="xs">
            Qayta urinish
          </Button>
        ) : null}
      </div>
    </Alert>
  );
}

export function EmptyState({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="grid min-h-48 place-items-center rounded-xl border border-dashed border-slate-300 bg-white p-6 text-center">
      <div>
        <Inbox aria-hidden="true" className="mx-auto size-7 text-slate-400" />
        <h3 className="mt-3 font-semibold">{title}</h3>
        <div className="mt-1 text-sm text-slate-600">{children}</div>
      </div>
    </div>
  );
}
