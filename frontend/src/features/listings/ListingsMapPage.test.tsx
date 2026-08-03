import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ListingsMapPage } from "./ListingsMapPage";
import { server } from "../../test/server";

vi.mock("react-leaflet", () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="map">{children}</div>
  ),
  TileLayer: () => <div data-testid="tile" />,
  CircleMarker: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="marker">{children}</div>
  ),
  Polygon: ({ children }: { children: React.ReactNode }) => <div data-testid="hex">{children}</div>,
  Popup: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Tooltip: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="tooltip">{children}</div>
  ),
  useMap: () => ({}),
  useMapEvents: () => null,
}));

vi.mock("leaflet", () => ({
  default: {
    heatLayer: vi.fn(() => ({ addTo: vi.fn(), remove: vi.fn() })),
  },
}));

vi.mock("leaflet.heat", () => ({}));

const BASE = "/api";

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/mapa"]}>
      <ListingsMapPage />
    </MemoryRouter>,
  );
}

function setupBase() {
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
        default_cities: [],
        sources: ["otodom"],
        source_max_pages: {},
        source_crons: {},
      }),
    ),
    http.get(`${BASE}/listings/filter-options`, () =>
      HttpResponse.json({
        cities: ["Gdańsk"],
        districts: ["Wrzeszcz", "Oliwa"],
        districts_by_city: { Gdańsk: ["Wrzeszcz", "Oliwa"] },
      }),
    ),
  );
}

describe("ListingsMapPage", () => {
  it("carries status=all into map points requests when option enabled", async () => {
    setupBase();
    const statuses: string[] = [];
    server.use(
      http.get(`${BASE}/listings/map/points`, ({ request }) => {
        statuses.push(new URL(request.url).searchParams.get("status") ?? "");
        return HttpResponse.json({ items: [], total: 0 });
      }),
    );
    renderPage();
    await waitFor(() => expect(statuses.length).toBeGreaterThan(0));
    expect(statuses).toContain("");

    await userEvent.click(screen.getByLabelText("Pokaż zarchiwizowane"));
    await waitFor(() => expect(statuses).toContain("all"));
  });

  it("carries status=all into map hex requests when option enabled", async () => {
    setupBase();
    const statuses: string[] = [];
    server.use(
      http.get(`${BASE}/listings/map/hexes`, ({ request }) => {
        statuses.push(new URL(request.url).searchParams.get("status") ?? "");
        return HttpResponse.json([]);
      }),
    );
    renderPage();
    await userEvent.click(screen.getByRole("button", { name: "Heat ilości" }));
    await waitFor(() => expect(statuses.length).toBeGreaterThan(0));
    expect(statuses).toContain("");

    await userEvent.click(screen.getByLabelText("Pokaż zarchiwizowane"));
    await waitFor(() => expect(statuses).toContain("all"));
  });
});
