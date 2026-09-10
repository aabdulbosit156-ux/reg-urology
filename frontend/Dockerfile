# Build-time config (frontend + backend are separate Railway services). Railway forwards
# matching service variables into these ARGs; Vite inlines VITE_* at build time.
ARG VITE_API_URL
ARG VITE_TELEGRAM_BOT

FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_API_URL
ARG VITE_TELEGRAM_BOT
ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_TELEGRAM_BOT=${VITE_TELEGRAM_BOT}
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
ENV PORT=8080
EXPOSE 8080
