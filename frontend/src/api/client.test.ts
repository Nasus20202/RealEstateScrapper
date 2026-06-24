import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { addFavorite, ApiError, getListing, getListings, postScrape } from "./client";
import { server } from "../test/server";

describe("api client", () => {
  it("builds correct query string with repeated district", async () => {
    let captured = "";
    server.use(
      http.get("/api/listings", ({ request }) => {
        captured = new URL(request.url).search;
        return HttpResponse.json({ items: [], total: 0 });
      }),
    );
    await getListings({
      city: "Gdansk",
      district: ["Wrzeszcz", "Oliwa"],
      max_price: 500000,
      min_rooms: 2,
      q: "blisko morza",
      limit: 50,
      offset: 0,
    });
    const params = new URLSearchParams(captured);
    expect(params.getAll("district")).toEqual(["Wrzeszcz", "Oliwa"]);
    expect(params.get("city")).toBe("Gdansk");
    expect(params.get("max_price")).toBe("500000");
    expect(params.get("min_rooms")).toBe("2");
    expect(params.get("q")).toBe("blisko morza");
    expect(params.get("limit")).toBe("50");
    expect(params.get("offset")).toBe("0");
  });

  it("getListings parses response", async () => {
    server.use(
      http.get("/api/listings", () =>
        HttpResponse.json({
          items: [{ id: 1, title: "Ładne 2pok" }],
          total: 1,
        }),
      ),
    );
    const res = await getListings({});
    expect(res.total).toBe(1);
    expect(res.items[0].title).toBe("Ładne 2pok");
  });

  it("getListing throws typed ApiError on 404", async () => {
    server.use(
      http.get("/api/listings/999", () =>
        HttpResponse.json({ detail: "listing not found" }, { status: 404 }),
      ),
    );
    await expect(getListing(999)).rejects.toBeInstanceOf(ApiError);
    await expect(getListing(999)).rejects.toMatchObject({ status: 404 });
  });

  it("postScrape sends JSON body and parses runs", async () => {
    let body: unknown = null;
    server.use(
      http.post("/api/scrape", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ runs: [{ id: 7, source_id: "otodom" }] });
      }),
    );
    const res = await postScrape({ city: "Gdansk", max_pages: 2 });
    expect(body).toEqual({ city: "Gdansk", max_pages: 2 });
    expect(res.runs[0].id).toBe(7);
  });

  it("addFavorite POSTs listing_id", async () => {
    let body: unknown = null;
    server.use(
      http.post("/api/favorites", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(
          { id: 1, listing_id: 42, created_at: "2026-06-21T00:00:00Z" },
          { status: 201 },
        );
      }),
    );
    const fav = await addFavorite(42);
    expect(body).toEqual({ listing_id: 42 });
    expect(fav.listing_id).toBe(42);
  });
});
