# syntax=docker/dockerfile:1.7

ARG NODE_VERSION=24.19.0

FROM node:${NODE_VERSION}-alpine3.23 AS web-build

WORKDIR /app
ENV CI=true

RUN npm install --global npm@10.9.8

COPY package.json package-lock.json ./
COPY apps/web/package.json ./apps/web/package.json

RUN --mount=type=cache,id=npm,target=/root/.npm \
    npm ci --omit=dev --ignore-scripts

COPY apps/web ./apps/web

RUN npm run build --workspace=@regurolog/web


FROM node:${NODE_VERSION}-alpine3.23 AS web-runtime

LABEL org.opencontainers.image.title="RegUrolog Web" \
      org.opencontainers.image.description="RegUrolog static UI and private API reverse proxy"

WORKDIR /app

ENV NODE_ENV=production \
    HOST=0.0.0.0 \
    PORT=8080

COPY --from=web-build --chown=node:node /app/apps/web/dist ./apps/web/dist
COPY --from=web-build --chown=node:node /app/apps/web/server.mjs ./apps/web/server.mjs

USER node

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:' + (process.env.PORT || '8080') + '/healthz').then((response) => { if (!response.ok) process.exit(1) }).catch(() => process.exit(1))"

CMD ["node", "apps/web/server.mjs"]
