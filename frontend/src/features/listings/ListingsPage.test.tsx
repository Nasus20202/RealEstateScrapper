// frontend/src/features/listings/ListingsPage.test.tsx
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { ListingsPage } from "./ListingsPage";
import { server } from "../../test/server";

const BASE = "http://localhost:8000";

function listing(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    source_id: "otodom",
    external_id: "x1",
    url: "http://x",
    title: "Ładne 2pok",
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
    score: 92,
    reason: "blisko morza",
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ListingsPage />
    </MemoryRouter>,
  );
}

describe("ListingsPage", () => {
  it("renderuje wyniki ze score i reason oraz cenę/m²", async () => {
    server.use(
      http.get(`${BASE}/listings`, () =>
        HttpResponse.json({ items: [listing()], total: 1 }),
      ),
    );
    renderPage();
    expect(await screen.findByText("Ładne 2pok")).toBeInTheDocument();
    expect(screen.getByText(/Znaleziono: 1/)).toBeInTheDocument();
    expect(screen.getByText(/8000/)).toBeInTheDocument();
    expect(screen.getByText(/92/)).toBeInTheDocument();
    expect(screen.getByText(/blisko morza/)).toBeInTheDocument();
    expect(screen.getByText("otodom")).toBeInTheDocument();
  });

  it("wysyła filtry i NL query jako parametry zapytania", async () => {
    let captured = "";
    server.use(
      http.get(`${BASE}/listings`, ({ request }) => {
        captured = new URL(request.url).search;
        return HttpResponse.json({ items: [], total: 0 });
      }),
    );
    renderPage();
    await screen.findByText(/Znaleziono: 0/);

    await userEvent.type(screen.getByLabelText("Miasto"), "Gdansk");
    await userEvent.type(screen.getByLabelText("Cena maks."), "500000");
    await userEvent.type(screen.getByLabelText("Pokoje min."), "2");

    // Expand hidden filters
    await userEvent.click(screen.getByRole("button", { name: /Więcej filtrów/i }));

    await userEvent.type(
      screen.getByLabelText("Dzielnice (przecinki)"),
      "Wrzeszcz, Oliwa",
    );
    await userEvent.type(
      screen.getByLabelText("Zapytanie (NL)"),
      "blisko morza",
    );
    await userEvent.click(screen.getByRole("button", { name: "Szukaj" }));

    await waitFor(() => {
      const params = new URLSearchParams(captured);
      expect(params.get("city")).toBe("Gdansk");
      expect(params.get("max_price")).toBe("500000");
      expect(params.get("min_rooms")).toBe("2");
      expect(params.getAll("district")).toEqual(["Wrzeszcz", "Oliwa"]);
      expect(params.get("q")).toBe("blisko morza");
    });
  });

  it("paginacja zwiększa offset", async () => {
    const offsets: string[] = [];
    server.use(
      http.get(`${BASE}/listings`, ({ request }) => {
        offsets.push(new URL(request.url).searchParams.get("offset") ?? "");
        return HttpResponse.json({
          items: [listing()],
          total: 120,
        });
      }),
    );
    renderPage();
    await screen.findByText("Ładne 2pok");
    await userEvent.click(screen.getByRole("button", { name: "Następna" }));
    await waitFor(() => expect(offsets).toContain("50"));
  });

  it("link prowadzi do szczegółów oferty", async () => {
    server.use(
      http.get(`${BASE}/listings`, () =>
        HttpResponse.json({ items: [listing({ id: 7 })], total: 1 }),
      ),
    );
    renderPage();
    const card = (await screen.findByText("Ładne 2pok")).closest("a");
    expect(card).toHaveAttribute("href", "/listings/7");
    within(document.body); // sanity
  });
});
