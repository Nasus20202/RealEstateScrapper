// frontend/src/features/favorites/FavoritesPage.test.tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { FavoritesPage } from "./FavoritesPage";
import { server } from "../../test/server";

const BASE = "/api";

function listing(id: number, title: string) {
  return {
    id,
    source_id: "otodom",
    external_id: `x${id}`,
    url: "http://x",
    title,
    price: 400000,
    price_per_m2: 8000,
    area_m2: 50,
    rooms: 2,
    floor: null,
    total_floors: null,
    city: "Gdansk",
    district: "Wrzeszcz",
    street: null,
    market: "secondary",
    description: null,
    attributes: {},
    images: [],
    posted_at: null,
    status: "active",
    score: null,
    reason: null,
    price_history: [],
    summary: null,
    features: null,
    duplicate_listing_ids: [],
  };
}

describe("FavoritesPage", () => {
  it("resolves favorites to listings and removes", async () => {
    let deleted = false;
    server.use(
      http.get(`${BASE}/favorites`, () =>
        HttpResponse.json([{ id: 1, listing_id: 7, created_at: "2026-06-01T00:00:00Z" }]),
      ),
      http.get(`${BASE}/listings/7`, () => HttpResponse.json(listing(7, "Ulubiona oferta"))),
      http.delete(`${BASE}/favorites/7`, () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    render(
      <MemoryRouter>
        <FavoritesPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText("Ulubiona oferta")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Usuń" }));
    await waitFor(() => expect(deleted).toBe(true));
    await waitFor(() => expect(screen.queryByText("Ulubiona oferta")).not.toBeInTheDocument());
  });
});
