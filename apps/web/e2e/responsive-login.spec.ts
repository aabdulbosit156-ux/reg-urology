import { expect, test } from "@playwright/test";

test("root login fits the target viewport", async ({ page }, testInfo) => {
  await page.goto("/");

  await page.getByRole("tab", { name: "Root" }).click();
  await expect(page.getByRole("heading", { name: "Root orqali kirish" })).toBeVisible();
  await expect(page.getByLabel("Admin token")).toBeVisible();
  await expect(page.getByRole("button", { name: "Xavfsiz kirish" })).toBeVisible();

  const hasPageOverflow = await page.evaluate(
    () =>
      document.documentElement.scrollWidth > window.innerWidth ||
      document.body.scrollWidth > window.innerWidth,
  );
  expect(hasPageOverflow).toBe(false);

  const buttonBox = await page.getByRole("button", { name: "Xavfsiz kirish" }).boundingBox();
  expect(buttonBox?.height).toBeGreaterThanOrEqual(44);

  await page.screenshot({
    fullPage: true,
    path: testInfo.outputPath(`regurolog-${testInfo.project.name}-root-login.png`),
  });
});

test("authenticated calendar uses responsive agenda without overflow", async ({ page }, testInfo) => {
  const today = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Tashkent" }).format(new Date());
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    if (url.endsWith("/auth/me")) {
      await route.fulfill({
        json: {
          principal: { kind: "root", role: "DEV", staff_id: null, full_name: null },
          expires_at: "2026-08-27T00:00:00Z",
          csrf_token: null,
        },
      });
      return;
    }
    if (url.endsWith("/health/live")) {
      await route.fulfill({ json: { status: "ok", service: "regurolog-api", timezone: "Asia/Tashkent" } });
      return;
    }
    if (url.includes("/analytics/cohort")) {
      await route.fulfill({ json: { mode: "registration_cohort", date_from: today, date_to: today, metrics: {}, daily: [] } });
      return;
    }
    if (url.endsWith("/doctors")) {
      await route.fulfill({ json: [{ id: "11111111-1111-4111-8111-111111111111", name: "Doktor Sardor", clinic_address: "Toshkent", directions: null, contact_phone: "+998900000000", timezone: "Asia/Tashkent", active: true }] });
      return;
    }
    if (url.includes("/calendar/availability")) {
      await route.fulfill({ json: { doctor_id: "11111111-1111-4111-8111-111111111111", local_date: today, timezone: "Asia/Tashkent", configured: true, slots: [{ start_at: `${today}T04:00:00Z`, end_at: `${today}T04:15:00Z`, available: true, state: "available" }] } });
      return;
    }
    if (url.includes("/calendar/summary")) {
      await route.fulfill({ json: { doctor_id: "11111111-1111-4111-8111-111111111111", date_from: `${today.slice(0, 7)}-01`, date_to: today, timezone: "Asia/Tashkent", days: [{ local_date: today, configured: true, total_slots: 4, available_slots: 3, blocked_slots: 0, scheduled: 1, checked_in: 0, completed: 0, no_show: 0, cancelled: 0 }] } });
      return;
    }
    if (url.includes("/appointments")) {
      await route.fulfill({ json: [] });
      return;
    }
    await route.fulfill({ status: 404, json: { code: "NOT_FOUND", message: "Topilmadi", field_errors: [], request_id: "e2e" } });
  });
  await page.goto("/");
  if ((page.viewportSize()?.width ?? 1440) < 1024) {
    await page.getByRole("button", { name: "Navigatsiyani ochish" }).click();
    await page.getByTestId("flowbite-drawer").getByRole("button", { name: "Kalendar" }).click();
  } else {
    await page.locator("aside").getByRole("button", { name: "Kalendar" }).click();
  }
  await expect(page.getByRole("heading", { name: "Kalendar" })).toBeVisible();
  if ((page.viewportSize()?.width ?? 1440) < 640) {
    await expect(page.locator('[aria-label="Mobil agenda"]')).toBeVisible();
  }
  await page.getByRole("button", { name: "Oy", exact: true }).click();
  await expect(page.getByText("1 yozilgan · 3 bo‘sh")).toBeVisible();
  const hasPageOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth || document.body.scrollWidth > window.innerWidth,
  );
  expect(hasPageOverflow).toBe(false);
  await page.screenshot({ fullPage: true, path: testInfo.outputPath(`regurolog-${testInfo.project.name}-calendar.png`) });
});
