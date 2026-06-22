import { http, HttpResponse } from "msw";

const BASE = "http://localhost:8000";

export const handlers = [
  http.get(`${BASE}/health`, () => HttpResponse.json({ status: "ok", database: "ok" })),
  http.get(`${BASE}/listings`, () => HttpResponse.json({ items: [], total: 0 })),
  http.get(`${BASE}/stats`, () =>
    HttpResponse.json({
      overview: {
        active_count: 0,
        total_count: 0,
        priced_count: 0,
        located_count: 0,
        with_images_count: 0,
        with_description_count: 0,
        avg_price: null,
        avg_price_per_m2: null,
        avg_area_m2: null,
        avg_rooms: null,
        min_price: null,
        max_price: null,
        latest_seen: null,
      },
      by_district: [],
      by_source: [],
      by_city: [],
      by_market: [],
      by_rooms: [],
      price_buckets: [],
    }),
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
      scheduler_enabled: false,
      scheduler_cron: null,
      default_cities: ["Gdańsk", "Gdynia", "Sopot"],
      sources: ["otodom"],
    }),
  ),
];
