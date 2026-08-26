import { defineRailway, postgres, preserve, project, service } from "railway/iac";

export default defineRailway((context) => {
  const production = context.environment === "production";
  const database = postgres("postgres");

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
      SESSION_SECRET: preserve(),
      APP_ENCRYPTION_KEY: preserve(),
      WEBHOOK_SECRET: preserve(),
      PUBLIC_BASE_URL: preserve(),
      ALLOWED_ORIGINS: preserve(),
      COOKIE_SECURE: "true",
      TRUST_PROXY_HEADERS: "true",
      ROOT_SESSION_TTL_SECONDS: "3600",
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
      SESSION_SECRET: preserve(),
      APP_ENCRYPTION_KEY: preserve(),
      WEBHOOK_SECRET: preserve(),
      PUBLIC_BASE_URL: preserve(),
      ALLOWED_ORIGINS: preserve(),
      COOKIE_SECURE: "true",
      TRUST_PROXY_HEADERS: "true",
      WORKER_POLL_SECONDS: "1",
      INBOX_PAYLOAD_RETENTION_HOURS: "24",
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
