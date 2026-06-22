import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { getListings } from "../../api/client";
import type { ListingOut, ListingsQuery } from "../../api/types";
import { ListingsMap, type MapMetric } from "./ListingsMap";

const MAP_LIMIT = 1000;

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

export function ListingsMapPage() {
  const [searchParams] = useSearchParams();
  const [items, setItems] = useState<ListingOut[]>([]);
  const [total, setTotal] = useState(0);
  const [metric, setMetric] = useState<MapMetric>("price");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getListings(queryFromParams(searchParams));
      setItems(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Błąd pobierania mapy");
    } finally {
      setLoading(false);
    }
  }, [searchParams]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="map-page">
      <div className="map-page__header">
        <div>
          <h2>Mapa ofert</h2>
          <p>
            Pokazano {items.length} z {total} ofert z aktualnych filtrów.
            {loading && <span className="loading-dot"> •••</span>}
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
      {error && <p className="error">{error}</p>}
      <ListingsMap listings={items} metric={metric} />
    </section>
  );
}
