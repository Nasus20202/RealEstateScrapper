// frontend/src/features/searches/SavedSearchesPage.test.tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { SavedSearchesPage } from "./SavedSearchesPage";
import { server } from "../../test/server";

const BASE = "http://localhost:8000";

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="loc">{location.pathname + location.search}</div>;
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/searches"]}>
      <Routes>
        <Route path="/searches" element={<SavedSearchesPage />} />
        <Route path="/" element={<LocationProbe />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("SavedSearchesPage", () => {
  it("listuje i tworzy zapisane wyszukiwanie", async () => {
    let posted: unknown = null;
    server.use(
      http.get(`${BASE}/searches`, () =>
        HttpResponse.json([
          {
            id: 1,
            name: "Tanie 2pok",
            filters: { max_price: 500000 },
            nl_query: "blisko morza",
            created_at: "2026-06-01T00:00:00Z",
          },
        ]),
      ),
      http.post(`${BASE}/searches`, async ({ request }) => {
        posted = await request.json();
        return HttpResponse.json(
          { id: 2, name: "Nowe", filters: {}, nl_query: null, created_at: "x" },
          { status: 201 },
        );
      }),
    );
    renderPage();
    expect(await screen.findByText("Tanie 2pok")).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("Nazwa"), "Nowe");
    await userEvent.type(screen.getByLabelText("Zapytanie NL"), "z balkonem");
    await userEvent.click(screen.getByRole("button", { name: "Zapisz wyszukiwanie" }));

    await waitFor(() =>
      expect(posted).toEqual({
        name: "Nowe",
        filters: {},
        nl_query: "z balkonem",
      }),
    );
  });

  it("Zastosuj nawiguje do listingów z parametrami", async () => {
    server.use(
      http.get(`${BASE}/searches`, () =>
        HttpResponse.json([
          {
            id: 1,
            name: "Tanie 2pok",
            filters: { max_price: 500000, district: ["Wrzeszcz"] },
            nl_query: "blisko morza",
            created_at: "2026-06-01T00:00:00Z",
          },
        ]),
      ),
    );
    renderPage();
    await screen.findByText("Tanie 2pok");
    await userEvent.click(screen.getByRole("button", { name: "Zastosuj" }));

    const loc = await screen.findByTestId("loc");
    expect(loc.textContent).toContain("/?");
    expect(loc.textContent).toContain("max_price=500000");
    expect(loc.textContent).toContain("district=Wrzeszcz");
    expect(loc.textContent).toContain("q=blisko+morza");
  });
});
