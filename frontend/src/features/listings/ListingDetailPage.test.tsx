// frontend/src/features/listings/ListingDetailPage.test.tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ListingDetailPage } from "./ListingDetailPage";
import { server } from "../../test/server";

vi.mock("react-leaflet", () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="detail-map">{children}</div>
  ),
  TileLayer: () => <div data-testid="detail-tile" />,
  Marker: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="detail-marker">{children}</div>
  ),
  Popup: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

const BASE = "/api";

function detail(overrides: Record<string, unknown> = {}) {
  return {
    id: 7,
    source_id: "otodom",
    external_id: "x7",
    url: "http://x7",
    title: "Mieszkanie z widokiem",
    price: 600000,
    price_per_m2: 10000,
    area_m2: 60,
    rooms: 3,
    floor: 2,
    total_floors: 4,
    city: "Gdansk",
    district: "Oliwa",
    street: "Morska",
    market: "secondary",
    description: "Opis ogłoszenia z portalu",
    attributes: { tags: ["BALCONY", "PARKING_SPOT"] },
    images: ["http://img/1.jpg", "http://img/2.jpg"],
    posted_at: "2026-06-01T00:00:00Z",
    status: "active",
    lat: 54.4,
    lon: 18.6,
    score: null,
    reason: null,
    price_history: [
      { price: 650000, observed_at: "2026-05-01T00:00:00Z" },
      { price: 600000, observed_at: "2026-06-01T00:00:00Z" },
    ],
    summary: "Słoneczne, blisko parku",
    features: { balkon: true, winda: false },
    duplicate_listing_ids: [8, 9],
    ...overrides,
  };
}

function renderAt(id: number) {
  return render(
    <MemoryRouter initialEntries={[`/listings/${id}`]}>
      <Routes>
        <Route path="/listings/:id" element={<ListingDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ListingDetailPage", () => {
  it("renders fields, gallery, price history, summary, and duplicates", async () => {
    server.use(
      http.get(`${BASE}/listings/7`, () => HttpResponse.json(detail())),
      http.get(`${BASE}/favorites`, () => HttpResponse.json([])),
    );
    renderAt(7);
    expect(await screen.findByText("Mieszkanie z widokiem")).toBeInTheDocument();
    expect(screen.getByText("Słoneczne, blisko parku")).toBeInTheDocument();
    expect(screen.getByText("Opis ogłoszenia z portalu")).toBeInTheDocument();
    expect(screen.getByText(/BALCONY/)).toBeInTheDocument();
    expect(screen.getByText(/balkon/)).toBeInTheDocument();
    expect(screen.getAllByRole("img").length).toBeGreaterThanOrEqual(2);
    const dup8 = screen.getByRole("link", { name: "8" });
    expect(dup8).toHaveAttribute("href", "/listings/8");
    expect(screen.getByRole("link", { name: "9" })).toBeInTheDocument();
    expect(screen.getAllByText("Morska, Oliwa, Gdansk").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByTestId("detail-map")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Otwórz w OpenStreetMap/ })).toHaveAttribute(
      "href",
      expect.stringContaining("54.4"),
    );
  });

  it("opens gallery in lightbox and navigates to next photo", async () => {
    server.use(
      http.get(`${BASE}/listings/7`, () => HttpResponse.json(detail())),
      http.get(`${BASE}/favorites`, () => HttpResponse.json([])),
    );
    renderAt(7);
    await userEvent.click(await screen.findByRole("button", { name: /Powiększ zdjęcie 1/ }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /zdjęcie 1 z 2/ })).toHaveAttribute(
      "src",
      "http://img/1.jpg",
    );
    await userEvent.click(screen.getByRole("button", { name: "Następne zdjęcie" }));
    expect(screen.getByRole("img", { name: /zdjęcie 2 z 2/ })).toHaveAttribute(
      "src",
      "http://img/2.jpg",
    );
  });

  it("favorite toggle adds listing", async () => {
    let posted: unknown = null;
    server.use(
      http.get(`${BASE}/listings/7`, () => HttpResponse.json(detail())),
      http.get(`${BASE}/favorites`, () => HttpResponse.json([])),
      http.post(`${BASE}/favorites`, async ({ request }) => {
        posted = await request.json();
        return HttpResponse.json(
          { id: 1, listing_id: 7, created_at: "2026-06-21T00:00:00Z" },
          { status: 201 },
        );
      }),
    );
    renderAt(7);
    const button = await screen.findByRole("button", { name: /Dodaj do ulubionych/ });
    await userEvent.click(button);
    await waitFor(() => expect(posted).toEqual({ listing_id: 7 }));
    expect(await screen.findByRole("button", { name: /Usuń z ulubionych/ })).toBeInTheDocument();
  });

  it("shows message on 404", async () => {
    server.use(
      http.get(`${BASE}/listings/123`, () =>
        HttpResponse.json({ detail: "listing not found" }, { status: 404 }),
      ),
      http.get(`${BASE}/favorites`, () => HttpResponse.json([])),
    );
    renderAt(123);
    expect(await screen.findByText(/Nie znaleziono oferty/)).toBeInTheDocument();
  });
});
