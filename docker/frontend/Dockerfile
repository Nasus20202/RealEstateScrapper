# Frontend SPA — build with pnpm, serve static files with nginx.
FROM node:24.17.0-alpine3.24 AS build
WORKDIR /app

RUN corepack enable && corepack prepare pnpm@11.8.0 --activate
COPY pnpm-workspace.yaml pnpm-lock.yaml ./
COPY frontend/package.json ./frontend/package.json
RUN pnpm install --frozen-lockfile

COPY frontend ./frontend
# API base URL is baked into the bundle at build time. Default points at the
# API published on the host (docker-compose maps it to localhost:8000).
ARG VITE_API_BASE=http://localhost:8000
ENV VITE_API_BASE=$VITE_API_BASE
RUN pnpm --dir frontend build

FROM nginx:1.31.2-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html
EXPOSE 80
