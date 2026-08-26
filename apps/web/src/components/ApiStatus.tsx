import { useQuery } from "@tanstack/react-query";
import { Badge, Button, Spinner } from "flowbite-react";
import { CircleAlert, CircleCheck } from "lucide-react";

import { getHealth } from "../api/health";

export function ApiStatus() {
  const health = useQuery({ queryKey: ["health"], queryFn: getHealth });

  if (health.isPending) {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-600" role="status">
        <Spinner aria-label="API tekshirilmoqda" size="sm" />
        API tekshirilmoqda…
      </div>
    );
  }

  if (health.isError) {
    return (
      <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center">
        <Badge color="failure" icon={CircleAlert}>
          API bilan aloqa yo‘q
        </Badge>
        <Button color="secondary" onClick={() => void health.refetch()} size="xs">
          Qayta tekshirish
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Badge color="primary" icon={CircleCheck}>
        API ishlayapti
      </Badge>
      <span className="text-sm text-slate-600">Toshkent vaqti · UTC+5</span>
    </div>
  );
}
