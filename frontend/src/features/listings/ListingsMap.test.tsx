import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { ListingOut } from "../../api/types";

// react-leaflet renders real Leaflet (needs layout/DOM jsdom can't provide), so
// mock it to lightweight passthrough components and assert our wiring instead.
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
    heatLayer: vi.fn(() => ({
      addTo: vi.fn(),
      remove: vi.fn(),
    })),
  },
}));

vi.mock("leaflet.heat", () => ({}));

import { ListingsMap } from "./ListingsMap";

function listing(over: Partial<ListingOut> = {}): ListingOut {
  return {
    id: 1,
    source_id: "otodom",
    external_id: "x",
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
    ...over,
  };
}

function renderMap(listings: ListingOut[]) {
  return render(
    <MemoryRouter>
      <ListingsMap listings={listings} />
    </MemoryRouter>,
  );
}

function renderHeatMap(listings: ListingOut[]) {
  return render(
    <MemoryRouter>
      <ListingsMap listings={listings} metric="heat_price" />
    </MemoryRouter>,
  );
}

describe("ListingsMap", () => {
  it("shows empty state when no listings have coordinates", () => {
    renderMap([listing({ id: 1 }), listing({ id: 2 })]);
    expect(screen.getByText(/Brak ofert ze współrzędnymi/)).toBeInTheDocument();
    expect(screen.queryByTestId("map")).not.toBeInTheDocument();
  });

  it("renders marker only for listings with coordinates", () => {
    renderMap([
      listing({ id: 1, lat: 54.35, lon: 18.65, title: "Z mapą" }),
      listing({ id: 2, lat: 54.5, lon: 18.5, title: "Też z mapą" }),
      listing({ id: 3, lat: null, lon: null, title: "Bez mapy" }),
    ]);
    expect(screen.getAllByTestId("marker")).toHaveLength(2);
    const link = screen.getByText("Z mapą").closest("a");
    expect(link).toHaveAttribute("href", "/listings/1");
    expect(screen.queryByText("Bez mapy")).not.toBeInTheDocument();
  });

  it("shows prices on markers and details in popup", () => {
    renderMap([listing({ id: 1, lat: 54.35, lon: 18.65, price: 400000 })]);
    expect(screen.getByTestId("tooltip")).toHaveTextContent("400K");
    expect(screen.getByText(/8000 zł\/m²|8 000 zł\/m²/)).toBeInTheDocument();
    expect(screen.getByText("2 pok. · 50 m²")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Szczegóły" })).toHaveAttribute("href", "/listings/1");
  });

  it("groups nearby listings into one marker", () => {
    renderMap([
      listing({ id: 1, lat: 54.3501, lon: 18.6501, title: "Pierwsza" }),
      listing({ id: 2, lat: 54.3502, lon: 18.6502, title: "Druga" }),
    ]);
    expect(screen.getAllByTestId("marker")).toHaveLength(1);
    expect(screen.getByTestId("tooltip")).toHaveTextContent("400K");
    expect(screen.getByRole("link", { name: /Pierwsza/ })).toHaveAttribute("href", "/listings/1");
    expect(screen.getByRole("link", { name: /Druga/ })).toHaveAttribute("href", "/listings/2");
  });

  it("renders heatmap from listing points when hex API returns empty", async () => {
    const L = await import("leaflet");
    renderHeatMap([listing({ id: 1, lat: 54.35, lon: 18.65 })]);
    expect(L.default.heatLayer).toHaveBeenCalledWith(
      [[54.35, 18.65, expect.any(Number)]],
      expect.objectContaining({ radius: 42 }),
    );
  });
});
