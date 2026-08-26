import { defineRailway, postgres, preserve, project, service } from "railway/iac";

export default defineRailway((context) => {
  const production = context.environment === "production";
  const database = postgres("postgres");

  // Single service: the root Dockerfile builds the UI + API into one image that
  // serves the frontend, exposes the API and runs the Telegram worker in-process
  // (REGUROLOG_PROCESS=all). ADMIN_TOKEN is the only secret an operator sets —
  // SESSION_SECRET / APP_ENCRYPTION_KEY / WEBHOOK_SECRET are derived from it, and
  // PUBLIC_BASE_URL / COOKIE_SECURE / TRUST_PROXY_HEADERS are auto-configured on
  // Railway. Migrations run automatically on container start.
  const app = service("app", {
    healthcheck: "/api/v1/health/ready",
    healthcheckTimeout: 30,
    replicas: 1,
    env: {
      PORT: "8000",
      REGUROLOG_PROCESS: "all",
      REGUROLOG_ENV: production ? "production" : "staging",
      DATABASE_URL: database.env.DATABASE_URL,
      ADMIN_TOKEN: preserve(),
    },
  });

  return project("regurolog", { resources: [database, app] });
});
