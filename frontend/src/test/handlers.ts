import { http, HttpResponse } from "msw";

const BASE = "http://localhost:8000";

export const handlers = [
  http.get(`${BASE}/health`, () =>
    HttpResponse.json({ status: "ok", database: "ok" }),
  ),
  http.get(`${BASE}/listings`, () =>
    HttpResponse.json({ items: [], total: 0 }),
  ),
  http.get(`${BASE}/scrape/runs`, () => HttpResponse.json([])),
  http.get(`${BASE}/searches`, () => HttpResponse.json([])),
  http.get(`${BASE}/favorites`, () => HttpResponse.json([])),
  http.get(`${BASE}/settings`, () =>
    HttpResponse.json({
      llm_enabled: false,
      llm_base_url: "https://openrouter.ai/api/v1",
      llm_model: null,
      llm_embedding_model: null,
      llm_api_key_set: false,
      scheduler_interval_minutes: null,
      sources: ["otodom"],
    }),
  ),
];
