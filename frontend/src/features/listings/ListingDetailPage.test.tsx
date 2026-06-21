// frontend/src/features/listings/ListingDetailPage.test.tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { ListingDetailPage } from "./ListingDetailPage";
import { server } from "../../test/server";

const BASE = "http://localhost:8000";

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
    images: ["http://img/1.jpg", "http://img/2.jpg"],
    posted_at: "2026-06-01T00:00:00Z",
    status: "active",
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
  it("renderuje pola, galerię, historię cen, podsumowanie i duplikaty", async () => {
    server.use(
      http.get(`${BASE}/listings/7`, () => HttpResponse.json(detail())),
      http.get(`${BASE}/favorites`, () => HttpResponse.json([])),
    );
    renderAt(7);
    expect(await screen.findByText("Mieszkanie z widokiem")).toBeInTheDocument();
    expect(screen.getByText("Słoneczne, blisko parku")).toBeInTheDocument();
    expect(screen.getByText(/balkon/)).toBeInTheDocument();
    expect(screen.getAllByRole("img").length).toBeGreaterThanOrEqual(2);
    const dup8 = screen.getByRole("link", { name: "8" });
    expect(dup8).toHaveAttribute("href", "/listings/8");
    expect(screen.getByRole("link", { name: "9" })).toBeInTheDocument();
  });

  it("przełącznik ulubionych dodaje ofertę", async () => {
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
    expect(
      await screen.findByRole("button", { name: /Usuń z ulubionych/ }),
    ).toBeInTheDocument();
  });

  it("pokazuje komunikat przy 404", async () => {
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
