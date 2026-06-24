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
  description: string | null;
  attributes: Record<string, unknown>;
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

export interface MapHexOut {
  id: string;
  geometry: {
    type: "Polygon";
    coordinates: number[][][];
  };
  count: number;
  avg_price: number | null;
  avg_price_per_m2: number | null;
}

export interface StatsOverviewOut {
  active_count: number;
  total_count: number;
  priced_count: number;
  located_count: number;
  with_images_count: number;
  with_description_count: number;
  avg_price: number | null;
  avg_price_per_m2: number | null;
  avg_area_m2: number | null;
  avg_rooms: number | null;
  min_price: number | null;
  max_price: number | null;
  latest_seen: string | null;
}

export interface StatsGroupOut {
  key: string;
  count: number;
  priced_count: number;
  located_count: number;
  avg_price: number | null;
  avg_price_per_m2: number | null;
  avg_area_m2: number | null;
  avg_rooms: number | null;
  min_price: number | null;
  max_price: number | null;
}

export interface StatsBucketOut {
  key: string;
  count: number;
}

export interface StatsProviderOut {
  source_id: string;
  display_name: string;
  enabled: boolean;
  count: number;
  priced_count: number;
  located_count: number;
  avg_price: number | null;
  avg_price_per_m2: number | null;
  avg_area_m2: number | null;
  avg_rooms: number | null;
  min_price: number | null;
  max_price: number | null;
  last_run_at: string | null;
  last_run_status: string | null;
}

export interface StatsOut {
  overview: StatsOverviewOut;
  by_district: StatsGroupOut[];
  by_source: StatsGroupOut[];
  by_city: StatsGroupOut[];
  by_market: StatsGroupOut[];
  by_rooms: StatsBucketOut[];
  price_buckets: StatsBucketOut[];
  by_provider: StatsProviderOut[];
}

export interface ListingsQuery {
  city?: string;
  district?: string[];
  source_id?: string[];
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

export interface MapBoundsQuery {
  north: number;
  south: number;
  east: number;
  west: number;
}

export interface StatsQuery {
  city?: string;
  district?: string[];
  source_id?: string[];
  min_price?: number;
  max_price?: number;
  min_rooms?: number;
  max_rooms?: number;
  market?: string;
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
  city?: string;
  min_price?: number;
  max_price?: number;
  min_area?: number;
  max_area?: number;
  min_rooms?: number;
  max_rooms?: number;
  market?: string;
  source_ids?: string[];
  max_pages?: number;
  source_max_pages?: Record<string, number>;
}

export interface ScrapeResponse {
  runs: ScrapeRunOut[];
}

export interface EnrichmentRequest {
  limit?: number;
  only_missing_embeddings?: boolean;
}

export interface EnrichmentResponse {
  selected_listings: number;
  enriched_listings: number;
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
  scheduler_enabled: boolean;
  scheduler_cron: string | null;
  default_cities: string[];
  sources: string[];
  source_max_pages: Record<string, number>;
  source_crons: Record<string, string>;
}

export interface SettingsUpdate {
  scheduler_interval_minutes?: number;
  scheduler_enabled?: boolean;
  scheduler_cron?: string | null;
  default_cities?: string[];
  enabled_source_ids?: string[];
  source_max_pages?: Record<string, number>;
  source_crons?: Record<string, string>;
}

export interface HealthOut {
  status: string;
  database: string;
}

export interface CleanupResponse {
  deleted_listings: number;
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

export interface ScrapeLogEvent {
  type: "scrape_log";
  source_id: string;
  message: string;
}
