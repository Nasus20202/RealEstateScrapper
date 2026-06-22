import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { server } from "../../test/server";
import { StatsPage } from "./StatsPage";

const BASE = "http://localhost:8000";

describe("StatsPage", () => {
  it("renderuje podsumowanie i agregacje", async () => {
    server.use(
      http.get(`${BASE}/stats`, () =>
        HttpResponse.json({
          overview: {
            active_count: 1234,
            total_count: 1300,
            priced_count: 1200,
            located_count: 900,
            with_images_count: 1000,
            with_description_count: 800,
            avg_price: 765432,
            avg_price_per_m2: 12345,
            avg_area_m2: 61.2,
            avg_rooms: 2.6,
            min_price: 250000,
            max_price: 2200000,
            latest_seen: "2026-06-22T12:00:00Z",
          },
          by_district: [
            {
              key: "Wrzeszcz",
              count: 120,
              priced_count: 118,
              located_count: 100,
              avg_price: 800000,
              avg_price_per_m2: 14000,
              avg_area_m2: 58,
              avg_rooms: 2.4,
              min_price: 400000,
              max_price: 1500000,
            },
          ],
          by_source: [],
          by_city: [],
          by_market: [],
          by_rooms: [{ key: "2", count: 500 }],
          price_buckets: [{ key: "600k-800k", count: 300 }],
        }),
      ),
    );

    render(
      <MemoryRouter>
        <StatsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Statystyki rynku")).toBeInTheDocument();
    expect(screen.getByText("1 234")).toBeInTheDocument();
    expect(screen.getByText("765 432 zł")).toBeInTheDocument();
    expect(screen.getByText("Wrzeszcz")).toBeInTheDocument();
    expect(screen.getByText("600k-800k")).toBeInTheDocument();
  });
});
