# Frontend SPA — build with Node, serve static files with nginx (both Alpine, patch-pinned).
FROM node:22.23.0-alpine3.24 AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . ./
# API base URL is baked into the bundle at build time. Default points at the
# API published on the host (docker-compose maps it to localhost:8000).
ARG VITE_API_BASE=http://localhost:8000
ENV VITE_API_BASE=$VITE_API_BASE
RUN npm run build

FROM nginx:1.31.2-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
