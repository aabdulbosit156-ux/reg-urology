import { defineRailway, postgres, preserve, project, service } from "railway/iac";

export default defineRailway((context) => {
  const production = context.environment === "production";
  const database = postgres("postgres");

  // ADMIN_TOKEN is the single secret an operator must set. SESSION_SECRET,
  // APP_ENCRYPTION_KEY and WEBHOOK_SECRET are derived from it in code, and
  // COOKIE_SECURE / TRUST_PROXY_HEADERS default to true on Railway. PUBLIC_BASE_URL
  // is only needed for the Telegram webhook — set it to the web service's URL.
  const api = service("api", {
    healthcheck: "/api/v1/health/ready",
    healthcheckTimeout: 30,
    replicas: 1,
    env: {
      PORT: "8000",
      RAILWAY_DOCKERFILE_PATH: "/Dockerfile.backend",
      REGUROLOG_PROCESS: "api",
      REGUROLOG_ENV: production ? "production" : "staging",
      DATABASE_URL: database.env.DATABASE_URL,
      ADMIN_TOKEN: preserve(),
      PUBLIC_BASE_URL: preserve(),
    },
  });

  const worker = service("worker", {
    replicas: 1,
    env: {
      RAILWAY_DOCKERFILE_PATH: "/Dockerfile.backend",
      REGUROLOG_PROCESS: "worker",
      REGUROLOG_ENV: production ? "production" : "staging",
      DATABASE_URL: database.env.DATABASE_URL,
      ADMIN_TOKEN: preserve(),
      PUBLIC_BASE_URL: preserve(),
    },
  });

  const web = service("web", {
    healthcheck: "/healthz",
    healthcheckTimeout: 30,
    replicas: 1,
    env: {
      PORT: "8080",
      NODE_ENV: "production",
      RAILWAY_DOCKERFILE_PATH: "/Dockerfile",
      API_UPSTREAM_HOST: api.env.RAILWAY_PRIVATE_DOMAIN,
      API_UPSTREAM_PORT: api.env.PORT,
    },
  });

  return project("regurolog", { resources: [database, api, worker, web] });
});
