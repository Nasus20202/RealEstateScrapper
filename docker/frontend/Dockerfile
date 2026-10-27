FROM node:24.22.1-alpine@sha256:06d7adf3e0ef61a13f1d28682726366f97a15aa1888c934d3ecec86c33918b53 AS build
WORKDIR /app

RUN corepack enable

COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./

RUN corepack install

RUN --mount=type=cache,id=pnpm,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile

COPY frontend/ .

RUN pnpm build

FROM nginx:1.31.8-alpine@sha256:1ef7ca94d7879df82421428ce13bd1eaa412404953859cf7a5b6512c25e67a60
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
