// frontend/src/features/scrape/ScrapePage.test.tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ScrapeEvent, ScrapeLogEvent } from "../../api/types";
import { ScrapePage } from "./ScrapePage";
import { server } from "../../test/server";

const BASE = "http://localhost:8000";

// Podmiana izolowanego modułu SSE — test wstrzykuje fake.
let lastHandler: ((event: ScrapeEvent | ScrapeLogEvent) => void) | null = null;
const unsubscribe = vi.fn();
vi.mock("../../api/events", () => ({
  subscribeScrapeEvents: (onEvent: (event: ScrapeEvent | ScrapeLogEvent) => void) => {
    lastHandler = onEvent;
    return unsubscribe;
  },
}));

function run(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    source_id: "otodom",
    started_at: "2026-06-20T10:00:00Z",
    finished_at: "2026-06-20T10:05:00Z",
    status: "done",
    new_count: 3,
    updated_count: 1,
    gone_count: 0,
    unchanged_count: 10,
    error_message: null,
    ...overrides,
  };
}

function setupMocks() {
  server.use(
    http.get(`${BASE}/settings`, () =>
      HttpResponse.json({
        llm_enabled: false,
        llm_base_url: "http://x",
        llm_model: null,
        llm_embedding_model: null,
        llm_api_key_set: false,
        scheduler_interval_minutes: null,
        scheduler_enabled: false,
        scheduler_cron: null,
        default_cities: ["Gdańsk", "Gdynia", "Sopot"],
        sources: ["otodom", "hossa"],
      }),
    ),
  );
}

beforeEach(() => {
  lastHandler = null;
  unsubscribe.mockClear();
});
afterEach(() => vi.clearAllMocks());

describe("ScrapePage", () => {
  it("renderuje listę ostatnich przebiegów", async () => {
    setupMocks();
    server.use(http.get(`${BASE}/scrape/runs`, () => HttpResponse.json([run()])));
    render(<ScrapePage />);
    // Source name in row
    expect(await screen.findAllByText("otodom")).not.toHaveLength(0);
    // Status chip
    expect(await screen.findByText("done")).toBeInTheDocument();
    // New count "+3"
    expect(await screen.findByText("+3")).toBeInTheDocument();
  });

  it("formularz wysyła POST /scrape z poprawnym body", async () => {
    setupMocks();
    let body: unknown = null;
    server.use(
      http.get(`${BASE}/scrape/runs`, () => HttpResponse.json([])),
      http.post(`${BASE}/scrape`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ runs: [run({ status: "running" })] });
      }),
    );
    render(<ScrapePage />);
    await screen.findByRole("button", { name: "Uruchom" });

    // Clear pre-filled city and type new value
    await userEvent.clear(screen.getByLabelText("Miasto"));
    await userEvent.type(screen.getByLabelText("Miasto"), "Sopot");
    await userEvent.clear(screen.getByLabelText("Maks. stron"));
    await userEvent.type(screen.getByLabelText("Maks. stron"), "3");

    await userEvent.click(screen.getByRole("button", { name: "Uruchom" }));

    await waitFor(() =>
      expect(body).toMatchObject({
        city: "Sopot",
        max_pages: 3,
      }),
    );
  });

  it("panel postępu pokazuje zdarzenia SSE wstrzyknięte przez fake", async () => {
    setupMocks();
    server.use(http.get(`${BASE}/scrape/runs`, () => HttpResponse.json([])));
    render(<ScrapePage />);
    await waitFor(() => expect(lastHandler).not.toBeNull());

    lastHandler!({
      type: "scrape",
      source_id: "otodom",
      status: "running",
      new: 2,
      updated: 1,
      gone: 0,
      unchanged: 5,
    });

    // Event row shows source, status and counts
    expect(await screen.findByText("otodom", { selector: ".scrape-event__source" })).toBeInTheDocument();
    expect(await screen.findByText("running", { selector: ".scrape-event__status" })).toBeInTheDocument();
    expect(await screen.findByText(/\+2 nowych/)).toBeInTheDocument();

    lastHandler!({
      type: "scrape_log",
      source_id: "otodom",
      message: "Pobieram stronę 1",
    });

    expect(await screen.findByText("Pobieram stronę 1")).toBeInTheDocument();
  });
});
