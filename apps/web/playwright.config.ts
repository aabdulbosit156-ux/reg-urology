import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results",
  fullyParallel: true,
  forbidOnly: true,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:4173",
    channel: process.env.CI ? "chromium" : "msedge",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "mobile-390",
      use: {
        ...devices["Desktop Edge"],
        viewport: { width: 390, height: 844 },
        hasTouch: true,
        isMobile: true,
      },
    },
    {
      name: "desktop-1440",
      use: {
        ...devices["Desktop Edge"],
        viewport: { width: 1440, height: 1000 },
      },
    },
    {
      name: "tablet-768",
      use: {
        ...devices["Desktop Edge"],
        viewport: { width: 768, height: 1024 },
        hasTouch: true,
      },
    },
    {
      name: "laptop-1024",
      use: {
        ...devices["Desktop Edge"],
        viewport: { width: 1024, height: 900 },
      },
    },
  ],
  webServer: [
    {
      command: "uv run uvicorn regurolog_api.main:app --app-dir apps/api/src --host 127.0.0.1 --port 8000",
      cwd: "../..",
      url: "http://127.0.0.1:8000/api/v1/health/live",
      reuseExistingServer: true,
      timeout: 30_000,
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 4173",
      cwd: ".",
      url: "http://127.0.0.1:4173",
      reuseExistingServer: true,
      timeout: 30_000,
    },
  ],
});
