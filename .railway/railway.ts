import { defineRailway, postgres, preserve, project, service } from "railway/iac";

export default defineRailway((context) => {
  const production = context.environment === "production";
  const database = postgres("postgres");

  const api = service("api", {
    build: "uv sync --frozen",
    start:
      "uv run --no-sync uvicorn regurolog_api.main:app --app-dir apps/api/src --host 0.0.0.0 --port $PORT",
    healthcheck: "/api/v1/health/ready",
    healthcheckTimeout: 30,
    replicas: 1,
    env: {
      PORT: "8000",
      REGUROLOG_ENV: production ? "production" : "staging",
      DATABASE_URL: database.env.DATABASE_URL,
      ADMIN_TOKEN: preserve(),
      SESSION_SECRET: preserve(),
      PUBLIC_BASE_URL: preserve(),
      ALLOWED_ORIGINS: preserve(),
      COOKIE_SECURE: "true",
      TRUST_PROXY_HEADERS: "true",
      ROOT_SESSION_TTL_SECONDS: "3600",
    },
  });

  const web = service("web", {
    build: "npm ci --include=dev && npm run build --workspace @regurolog/web",
    start: "npm run start --workspace @regurolog/web",
    healthcheck: "/healthz",
    healthcheckTimeout: 30,
    replicas: 1,
    env: {
      PORT: "8080",
      NODE_ENV: "production",
      API_UPSTREAM_HOST: api.env.RAILWAY_PRIVATE_DOMAIN,
      API_UPSTREAM_PORT: api.env.PORT,
    },
  });

  return project("regurolog", { resources: [database, api, web] });
});
