export interface HealthResponse {
  status: "ok";
  service: "regurolog-api";
  timezone: "Asia/Tashkent";
}

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch("/api/v1/health/live", {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error("API holatini olib bo‘lmadi");
  }

  return (await response.json()) as HealthResponse;
}
