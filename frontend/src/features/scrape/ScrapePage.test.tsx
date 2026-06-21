// frontend/src/features/scrape/ScrapePage.test.tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ScrapeEvent } from "../../api/types";
import { ScrapePage } from "./ScrapePage";
import { server } from "../../test/server";

const BASE = "http://localhost:8000";

// Podmiana izolowanego modułu SSE — test wstrzykuje fake.
let lastHandler: ((event: ScrapeEvent) => void) | null = null;
const unsubscribe = vi.fn();
vi.mock("../../api/events", () => ({
  subscribeScrapeEvents: (onEvent: (event: ScrapeEvent) => void) => {
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
    status: "success",
    new_count: 3,
    updated_count: 1,
    gone_count: 0,
    unchanged_count: 10,
    error_message: null,
    ...overrides,
  };
}

beforeEach(() => {
  lastHandler = null;
  unsubscribe.mockClear();
});
afterEach(() => vi.clearAllMocks());

describe("ScrapePage", () => {
  it("renderuje listę ostatnich przebiegów", async () => {
    server.use(http.get(`${BASE}/scrape/runs`, () => HttpResponse.json([run()])));
    render(<ScrapePage />);
    expect(await screen.findByText(/otodom/)).toBeInTheDocument();
    expect(screen.getByText(/success/)).toBeInTheDocument();
    expect(screen.getByText(/nowe: 3/)).toBeInTheDocument();
  });

  it("formularz wysyła POST /scrape z poprawnym body", async () => {
    let body: unknown = null;
    server.use(
      http.get(`${BASE}/scrape/runs`, () => HttpResponse.json([])),
      http.post(`${BASE}/scrape`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ runs: [run({ status: "running" })] });
      }),
    );
    render(<ScrapePage />);
    await screen.findByRole("button", { name: "Uruchom scraping" });

    await userEvent.type(screen.getByLabelText("Miasto"), "Gdansk");
    await userEvent.clear(screen.getByLabelText("Maks. stron"));
    await userEvent.type(screen.getByLabelText("Maks. stron"), "3");
    await userEvent.type(
      screen.getByLabelText("Źródła (przecinki)"),
      "otodom, olx",
    );
    await userEvent.click(screen.getByRole("button", { name: "Uruchom scraping" }));

    await waitFor(() =>
      expect(body).toEqual({
        city: "Gdansk",
        max_pages: 3,
        source_ids: ["otodom", "olx"],
      }),
    );
  });

  it("panel postępu pokazuje zdarzenia SSE wstrzyknięte przez fake", async () => {
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

    expect(
      await screen.findByText(/otodom — running \(nowe 2, akt\. 1\)/),
    ).toBeInTheDocument();
  });
});
