# Frontend Instructions

Instructions for agents/developers working in `frontend/`.

## Stack

- Standalone frontend project in `frontend/`.
- React 19 + Vite 8 + TypeScript 6 + react-router-dom v7.
- Vitest 4 + Testing Library + MSW + jsdom 29.

## Rules

- Lint: `pnpm lint` must pass from `frontend/`.
- Formatting: run `pnpm format` before committing frontend changes.
- API base defaults to `/api`; nginx and Vite dev server proxy it to the backend.
- `VITE_API_BASE` can override the API base for custom deployments.

## Commands

- Install: `pnpm install`
- Dev server: `pnpm dev`
- Production build: `pnpm build` (`tsc -b && vite build`)
- Tests: `pnpm exec vitest run`
- Lint: `pnpm lint`
- Format: `pnpm format`
