// frontend/src/features/listings/ListingsPage.test.tsx
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { ListingsPage } from "./ListingsPage";
import { server } from "../../test/server";

const BASE = "/api";

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
    description: "<p>Duży balkon, zielona okolica i szybki dojazd do SKM.</p>",
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
  function setupSettings() {
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
          source_max_pages: {},
          source_crons: {},
        }),
      ),
    );
  }

  it("renders results with score, reason, and price/m²", async () => {
    setupSettings();
    server.use(
      http.get(`${BASE}/listings`, () => HttpResponse.json({ items: [listing()], total: 1 })),
    );
    renderPage();
    expect(await screen.findByText("Ładne 2pok")).toBeInTheDocument();
    expect(screen.getByText(/Znaleziono: 1/)).toBeInTheDocument();
    expect(screen.getByText(/8 000/)).toBeInTheDocument();
    expect(screen.getByText(/92/)).toBeInTheDocument();
    expect(screen.getByText(/blisko morza/)).toBeInTheDocument();
    expect(screen.getAllByText("otodom").length).toBeGreaterThan(0);
  });

  it("sends filters and NL query as query params", async () => {
    setupSettings();
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

    await userEvent.click(screen.getByLabelText("Wrzeszcz"));
    await userEvent.click(screen.getByLabelText("Oliwa"));
    await userEvent.click(screen.getByLabelText("hossa"));
    await userEvent.type(screen.getByLabelText("Zapytanie (NL)"), "blisko morza");
    await userEvent.click(screen.getByRole("button", { name: "Szukaj" }));

    await waitFor(() => {
      const params = new URLSearchParams(captured);
      expect(params.get("city")).toBe("Gdansk");
      expect(params.get("max_price")).toBe("500000");
      expect(params.get("min_rooms")).toBe("2");
      expect(params.getAll("district")).toEqual(["Wrzeszcz", "Oliwa"]);
      expect(params.getAll("source_id")).toEqual(["hossa"]);
      expect(params.get("q")).toBe("blisko morza");
    });
  });

  it("pagination increases offset", async () => {
    setupSettings();
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

  it("link goes to listing details", async () => {
    setupSettings();
    server.use(
      http.get(`${BASE}/listings`, () =>
        HttpResponse.json({ items: [listing({ id: 7 })], total: 1 }),
      ),
    );
    renderPage();
    await screen.findByText("Ładne 2pok");
    expect(screen.getByRole("link", { name: "Szczegóły" })).toHaveAttribute("href", "/listings/7");
    within(document.body); // sanity
  });

  it("switches views: default, compact, and list", async () => {
    setupSettings();
    server.use(
      http.get(`${BASE}/listings`, () => HttpResponse.json({ items: [listing()], total: 1 })),
    );
    renderPage();
    await screen.findByText("Ładne 2pok");

    expect(screen.getByRole("button", { name: "Domyślny" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await userEvent.click(screen.getByRole("button", { name: "Lista" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Lista" })).toHaveAttribute("aria-pressed", "true");
      expect(document.querySelector(".listings-grid--list")).toBeInTheDocument();
    });
    expect(screen.getByText(/Duży balkon/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Kompaktowy" }));
    await waitFor(() => {
      expect(document.querySelector(".listing-card--compact")).toBeInTheDocument();
    });
  });
});
