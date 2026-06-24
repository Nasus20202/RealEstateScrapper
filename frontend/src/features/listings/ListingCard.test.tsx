import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ListingOut } from "../../api/types";
import { ListingCard } from "./ListingCard";

function listing(overrides: Partial<ListingOut> = {}): ListingOut {
  return {
    id: 1,
    source_id: "otodom",
    external_id: "x1",
    url: "http://x",
    title: "Oferta",
    price: 400000,
    price_per_m2: 8000,
    area_m2: 50,
    rooms: 2,
    floor: null,
    total_floors: null,
    city: "Gdańsk",
    district: "Wrzeszcz",
    street: null,
    lat: null,
    lon: null,
    market: "secondary",
    description: null,
    attributes: {},
    images: [],
    posted_at: null,
    status: "active",
    score: null,
    reason: null,
    ...overrides,
  };
}

describe("ListingCard", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("middle-click opens details in new tab and prevents autoscroll", () => {
    const open = vi.spyOn(window, "open").mockImplementation(() => null);
    render(
      <MemoryRouter>
        <ListingCard listing={listing()} onPreview={() => {}} />
      </MemoryRouter>,
    );

    const card = screen.getByRole("button");
    const event = new MouseEvent("mousedown", { button: 1, bubbles: true, cancelable: true });
    const dispatched = card.dispatchEvent(event);

    expect(dispatched).toBe(false);
    expect(event.defaultPrevented).toBe(true);
    expect(open).toHaveBeenCalledWith("/listings/1", "_blank", "noopener");
  });
});
