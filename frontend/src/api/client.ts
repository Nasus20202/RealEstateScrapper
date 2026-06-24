import type {
  CreateSavedSearch,
  FavoriteOut,
  HealthOut,
  ListingDetailOut,
  ListingOut,
  ListingsQuery,
  ListingsResponse,
  MapBoundsQuery,
  MapHexOut,
  SavedSearchOut,
  ScrapeRequest,
  ScrapeResponse,
  ScrapeRunOut,
  SettingsOut,
  SettingsUpdate,
  CleanupResponse,
  StatsOut,
  StatsQuery,
} from "./types";

export const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // ignore non-JSON error bodies
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

function buildListingsQuery(query: ListingsQuery & Partial<MapBoundsQuery>): string {
  const params = new URLSearchParams();
  if (query.city) params.set("city", query.city);
  for (const d of query.district ?? []) params.append("district", d);
  for (const source of query.source_id ?? []) params.append("source_id", source);
  if (query.min_price != null) params.set("min_price", String(query.min_price));
  if (query.max_price != null) params.set("max_price", String(query.max_price));
  if (query.min_area != null) params.set("min_area", String(query.min_area));
  if (query.max_area != null) params.set("max_area", String(query.max_area));
  if (query.min_rooms != null) params.set("min_rooms", String(query.min_rooms));
  if (query.max_rooms != null) params.set("max_rooms", String(query.max_rooms));
  if (query.market) params.set("market", query.market);
  if (query.q) params.set("q", query.q);
  if (query.sort_by) params.set("sort_by", query.sort_by);
  if (query.sort_dir) params.set("sort_dir", query.sort_dir);
  if (query.north != null) params.set("north", String(query.north));
  if (query.south != null) params.set("south", String(query.south));
  if (query.east != null) params.set("east", String(query.east));
  if (query.west != null) params.set("west", String(query.west));
  params.set("limit", String(query.limit ?? 50));
  params.set("offset", String(query.offset ?? 0));
  return params.toString();
}

export function getHealth(): Promise<HealthOut> {
  return request<HealthOut>("/health");
}

export function getListings(query: ListingsQuery): Promise<ListingsResponse> {
  return request<ListingsResponse>(`/listings?${buildListingsQuery(query)}`);
}

export function getMapHexes(query: ListingsQuery, sizeM = 850): Promise<MapHexOut[]> {
  const params = buildListingsQuery({ ...query, limit: undefined, offset: undefined });
  return request<MapHexOut[]>(`/listings/map/hexes?${params}&size_m=${sizeM}`);
}

export function getMapPoints(
  query: ListingsQuery & Partial<MapBoundsQuery>,
): Promise<ListingsResponse> {
  const params = buildListingsQuery({ ...query, offset: undefined });
  return request<ListingsResponse>(`/listings/map/points?${params}`);
}

export function getListing(id: number): Promise<ListingDetailOut> {
  return request<ListingDetailOut>(`/listings/${id}`);
}

export function getStats(query?: StatsQuery): Promise<StatsOut> {
  const params = new URLSearchParams();
  if (query?.city) params.set("city", query.city);
  for (const d of query?.district ?? []) params.append("district", d);
  for (const s of query?.source_id ?? []) params.append("source_id", s);
  if (query?.min_price != null) params.set("min_price", String(query.min_price));
  if (query?.max_price != null) params.set("max_price", String(query.max_price));
  if (query?.min_rooms != null) params.set("min_rooms", String(query.min_rooms));
  if (query?.max_rooms != null) params.set("max_rooms", String(query.max_rooms));
  if (query?.market) params.set("market", query.market);
  const qs = params.toString();
  return request<StatsOut>(`/stats${qs ? `?${qs}` : ""}`);
}

export function postScrape(body: ScrapeRequest): Promise<ScrapeResponse> {
  return request<ScrapeResponse>("/scrape", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getRuns(limit = 50): Promise<ScrapeRunOut[]> {
  return request<ScrapeRunOut[]>(`/scrape/runs?limit=${limit}`);
}

export function getRun(id: number): Promise<ScrapeRunOut> {
  return request<ScrapeRunOut>(`/scrape/runs/${id}`);
}

export function getSearches(): Promise<SavedSearchOut[]> {
  return request<SavedSearchOut[]>("/searches");
}

export function createSearch(body: CreateSavedSearch): Promise<SavedSearchOut> {
  return request<SavedSearchOut>("/searches", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function deleteSearch(id: number): Promise<void> {
  return request<void>(`/searches/${id}`, { method: "DELETE" });
}

export function getFavorites(): Promise<FavoriteOut[]> {
  return request<FavoriteOut[]>("/favorites");
}

export function addFavorite(listing_id: number): Promise<FavoriteOut> {
  return request<FavoriteOut>("/favorites", {
    method: "POST",
    body: JSON.stringify({ listing_id }),
  });
}

export function removeFavorite(listing_id: number): Promise<void> {
  return request<void>(`/favorites/${listing_id}`, { method: "DELETE" });
}

export function getSettings(): Promise<SettingsOut> {
  return request<SettingsOut>("/settings");
}

export function updateSettings(body: SettingsUpdate): Promise<SettingsOut> {
  return request<SettingsOut>("/settings", {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function cleanupDatabase(): Promise<CleanupResponse> {
  return request<CleanupResponse>("/cleanup", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export type {
  CreateSavedSearch,
  FavoriteOut,
  HealthOut,
  ListingDetailOut,
  ListingOut,
  ListingsQuery,
  ListingsResponse,
  MapBoundsQuery,
  MapHexOut,
  SavedSearchOut,
  ScrapeRequest,
  ScrapeResponse,
  ScrapeRunOut,
  SettingsOut,
  SettingsUpdate,
  CleanupResponse,
  StatsOut,
};
