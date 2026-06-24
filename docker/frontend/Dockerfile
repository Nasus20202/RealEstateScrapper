# Frontend SPA — build with pnpm, serve static files with nginx.
FROM node:24.18.0-alpine AS build
WORKDIR /app

RUN corepack enable && corepack prepare pnpm@11.8.0 --activate
COPY frontend/pnpm-workspace.yaml frontend/pnpm-lock.yaml ./
COPY frontend/package.json ./frontend/package.json
RUN pnpm install --frozen-lockfile

COPY frontend ./frontend
RUN pnpm --dir frontend build

FROM nginx:1.31.2-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html
EXPOSE 80
