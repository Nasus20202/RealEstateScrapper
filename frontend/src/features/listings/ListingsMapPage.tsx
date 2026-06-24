import { useCallback, useEffect, useMemo, useRef, useState, useTransition } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { getMapHexes, getMapPoints, getSettings } from "../../api/client";
import type { ListingOut, ListingsQuery, MapBoundsQuery, MapHexOut } from "../../api/types";
import { ListingsMap, type MapMetric, type MapViewport } from "./ListingsMap";

const DEBOUNCE_MS = 300;

const MAP_LIMIT = 1_000;

function queryFromParams(params: URLSearchParams): ListingsQuery {
  return {
    city: params.get("city") ?? undefined,
    district: params.getAll("district"),
    source_id: params.getAll("source_id"),
    min_price: Number(params.get("min_price")) || undefined,
    max_price: Number(params.get("max_price")) || undefined,
    min_area: Number(params.get("min_area")) || undefined,
    max_area: Number(params.get("max_area")) || undefined,
    min_rooms: Number(params.get("min_rooms")) || undefined,
    max_rooms: Number(params.get("max_rooms")) || undefined,
    market: params.get("market") ?? undefined,
    q: params.get("q") ?? undefined,
    sort_by: "date",
    sort_dir: "desc",
    limit: MAP_LIMIT,
    offset: 0,
  };
}

function boundsFromViewport(viewport: MapViewport): MapBoundsQuery {
  return {
    north: viewport.north,
    south: viewport.south,
    east: viewport.east,
    west: viewport.west,
  };
}

function paramsFromFilters(form: MapFilterState, current: URLSearchParams): URLSearchParams {
  const params = new URLSearchParams(current);
  for (const key of [
    "city",
    "min_price",
    "max_price",
    "min_rooms",
    "max_rooms",
    "market",
    "source_id",
  ]) {
    params.delete(key);
  }
  if (form.city.trim()) params.set("city", form.city.trim());
  if (form.min_price.trim()) params.set("min_price", form.min_price.trim());
  if (form.max_price.trim()) params.set("max_price", form.max_price.trim());
  if (form.min_rooms.trim()) params.set("min_rooms", form.min_rooms.trim());
  if (form.max_rooms.trim()) params.set("max_rooms", form.max_rooms.trim());
  if (form.market) params.set("market", form.market);
  for (const source of form.source_ids) params.append("source_id", source);
  return params;
}

function filtersFromParams(params: URLSearchParams): MapFilterState {
  return {
    city: params.get("city") ?? "",
    min_price: params.get("min_price") ?? "",
    max_price: params.get("max_price") ?? "",
    min_rooms: params.get("min_rooms") ?? "",
    max_rooms: params.get("max_rooms") ?? "",
    market: params.get("market") ?? "",
    source_ids: params.getAll("source_id"),
  };
}

interface MapFilterState {
  city: string;
  min_price: string;
  max_price: string;
  min_rooms: string;
  max_rooms: string;
  market: string;
  source_ids: string[];
}

export function ListingsMapPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [items, setItems] = useState<ListingOut[]>([]);
  const [hexes, setHexes] = useState<MapHexOut[]>([]);
  const filters = useMemo(() => filtersFromParams(searchParams), [searchParams]);
  const [sources, setSources] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [metric, setMetric] = useState<MapMetric>("price");
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [viewport, setViewport] = useState<MapViewport | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const isHeat = metric === "heat_price" || metric === "heat_count";

  const load = useCallback(
    (nextViewport: MapViewport | null) => {
      if (abortRef.current) abortRef.current.abort();

      startTransition(async () => {
        try {
          const baseQuery = queryFromParams(searchParams);
          const bounds = nextViewport ? boundsFromViewport(nextViewport) : {};
          const query = { ...baseQuery, ...bounds };
          if (isHeat) {
            const mapHexes = await getMapHexes(query);
            setHexes(mapHexes);
            setItems([]);
            setTotal(0);
          } else {
            const res = await getMapPoints(query);
            setItems(res.items);
            setHexes([]);
            setTotal(res.total);
          }
        } catch (err) {
          setError(err instanceof Error ? err.message : "Błąd pobierania mapy");
        }
      });
    },
    [searchParams, startTransition, isHeat],
  );

  useEffect(() => {
    if (viewport == null) {
      load(null);
      return;
    }
    debounceRef.current = setTimeout(() => load(viewport), DEBOUNCE_MS);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [load, viewport]);

  useEffect(() => {
    void getSettings()
      .then((settings) => setSources(settings.sources))
      .catch(() => {});
  }, []);

  function update(field: keyof MapFilterState, value: string) {
    const next = { ...filters, [field]: value };
    setSearchParams(paramsFromFilters(next, searchParams));
  }

  function toggleSource(source: string) {
    const nextIds = filters.source_ids.includes(source)
      ? filters.source_ids.filter((s) => s !== source)
      : [...filters.source_ids, source];
    const next = { ...filters, source_ids: nextIds };
    setSearchParams(paramsFromFilters(next, searchParams));
  }

  function applyFilters(event: React.FormEvent) {
    event.preventDefault();
    setSearchParams(paramsFromFilters(filters, searchParams));
  }

  function onViewport(nextViewport: MapViewport) {
    setViewport((current) => {
      if (
        current &&
        Math.abs(current.north - nextViewport.north) < 0.0005 &&
        Math.abs(current.south - nextViewport.south) < 0.0005 &&
        Math.abs(current.east - nextViewport.east) < 0.0005 &&
        Math.abs(current.west - nextViewport.west) < 0.0005 &&
        current.zoom === nextViewport.zoom
      ) {
        return current;
      }
      return nextViewport;
    });
  }

  return (
    <section className="map-page">
      <div className="map-page__header">
        <div>
          <h2>Mapa ofert</h2>
          <p>
            Pokazano {items.length} z {total} ofert w widocznym obszarze.
            {isPending && <span className="loading-dot"> •••</span>}
          </p>
        </div>
        <div className="toolbar-right">
          <div className="view-toggle" role="group" aria-label="Tryb mapy">
            <button
              type="button"
              className={metric === "price" ? "active" : ""}
              onClick={() => setMetric("price")}
            >
              Ceny
            </button>
            <button
              type="button"
              className={metric === "count" ? "active" : ""}
              onClick={() => setMetric("count")}
            >
              Ilość
            </button>
            <button
              type="button"
              className={metric === "heat_price" ? "active" : ""}
              onClick={() => setMetric("heat_price")}
            >
              Heat ceny
            </button>
            <button
              type="button"
              className={metric === "heat_count" ? "active" : ""}
              onClick={() => setMetric("heat_count")}
            >
              Heat ilości
            </button>
          </div>
          <Link className="btn-link" to={`/?${searchParams.toString()}`}>
            Lista
          </Link>
        </div>
      </div>
      <form className="map-filters" onSubmit={applyFilters}>
        <label htmlFor="map-city">
          Miasto
          <input
            id="map-city"
            value={filters.city}
            onChange={(event) => update("city", event.target.value)}
            placeholder="np. Gdańsk"
          />
        </label>
        <label htmlFor="map-min-price">
          Cena min.
          <input
            id="map-min-price"
            inputMode="numeric"
            value={filters.min_price}
            onChange={(event) => update("min_price", event.target.value)}
          />
        </label>
        <label htmlFor="map-max-price">
          Cena maks.
          <input
            id="map-max-price"
            inputMode="numeric"
            value={filters.max_price}
            onChange={(event) => update("max_price", event.target.value)}
          />
        </label>
        <label htmlFor="map-min-rooms">
          Pokoje min.
          <input
            id="map-min-rooms"
            inputMode="numeric"
            value={filters.min_rooms}
            onChange={(event) => update("min_rooms", event.target.value)}
          />
        </label>
        <label htmlFor="map-market">
          Rynek
          <select
            id="map-market"
            value={filters.market}
            onChange={(event) => update("market", event.target.value)}
          >
            <option value="">Wszystkie</option>
            <option value="primary">Pierwotny</option>
            <option value="secondary">Wtórny</option>
          </select>
        </label>
        {sources.length > 0 && (
          <div className="map-filters__sources">
            {sources.map((source) => (
              <label key={source} className="multi-select-option">
                <input
                  type="checkbox"
                  checked={filters.source_ids.includes(source)}
                  onChange={() => toggleSource(source)}
                />
                {source}
              </label>
            ))}
          </div>
        )}
        <button type="submit">Filtruj mapę</button>
      </form>
      {error && <p className="error">{error}</p>}
      <ListingsMap listings={items} metric={metric} hexes={hexes} onViewport={onViewport} />
    </section>
  );
}
