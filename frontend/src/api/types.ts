export interface ListingOut {
  id: number;
  source_id: string;
  external_id: string;
  url: string;
  title: string;
  price: number | null;
  price_per_m2: number | null;
  area_m2: number | null;
  rooms: number | null;
  floor: number | null;
  total_floors: number | null;
  city: string | null;
  district: string | null;
  street: string | null;
  lat: number | null;
  lon: number | null;
  market: string | null;
  images: string[];
  posted_at: string | null;
  status: string;
  score: number | null;
  reason: string | null;
}

export interface PriceHistoryEntry {
  price: number;
  observed_at: string;
}

export interface ListingDetailOut extends ListingOut {
  price_history: PriceHistoryEntry[];
  summary: string | null;
  features: Record<string, unknown> | null;
  duplicate_listing_ids: number[];
}

export interface ListingsResponse {
  items: ListingOut[];
  total: number;
}

export interface ListingsQuery {
  city?: string;
  district?: string[];
  min_price?: number;
  max_price?: number;
  min_area?: number;
  max_area?: number;
  min_rooms?: number;
  max_rooms?: number;
  market?: string;
  q?: string;
  sort_by?: string;
  sort_dir?: "asc" | "desc";
  limit?: number;
  offset?: number;
}

export interface ScrapeRunOut {
  id: number;
  source_id: string;
  started_at: string;
  finished_at: string | null;
  status: string;
  new_count: number;
  updated_count: number;
  gone_count: number;
  unchanged_count: number;
  error_message: string | null;
}

export interface ScrapeRequest {
  city: string;
  min_price?: number;
  max_price?: number;
  min_area?: number;
  max_area?: number;
  min_rooms?: number;
  max_rooms?: number;
  market?: string;
  source_ids?: string[];
  max_pages?: number;
}

export interface ScrapeResponse {
  runs: ScrapeRunOut[];
}

export interface SavedSearchOut {
  id: number;
  name: string;
  filters: Record<string, unknown>;
  nl_query: string | null;
  created_at: string;
}

export interface CreateSavedSearch {
  name: string;
  filters: Record<string, unknown>;
  nl_query?: string | null;
}

export interface FavoriteOut {
  id: number;
  listing_id: number;
  created_at: string;
}

export interface SettingsOut {
  llm_enabled: boolean;
  llm_base_url: string;
  llm_model: string | null;
  llm_embedding_model: string | null;
  llm_api_key_set: boolean;
  scheduler_interval_minutes: number | null;
  sources: string[];
}

export interface SettingsUpdate {
  scheduler_interval_minutes?: number;
  enabled_source_ids?: string[];
}

export interface HealthOut {
  status: string;
  database: string;
}

export interface ScrapeEvent {
  type: string;
  source_id: string;
  status: string;
  new: number;
  updated: number;
  gone: number;
  unchanged: number;
}
