import { expect, test } from "@playwright/test";

test("root login fits the target viewport", async ({ page }, testInfo) => {
  await page.goto("/");

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
