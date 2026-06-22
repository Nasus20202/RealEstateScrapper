import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { getSettings, getStats } from "../../api/client";
import type {
  StatsBucketOut,
  StatsGroupOut,
  StatsOut,
  StatsProviderOut,
  StatsQuery,
} from "../../api/types";
import { formatNumber, formatPrice, formatPricePerM2 } from "../listings/format";

function percent(value: number, total: number): string {
  if (total === 0) return "0%";
  return `${Math.round((value / total) * 100)}%`;
}

function formatDecimal(value: number | null, suffix = ""): string {
  return value == null ? "—" : `${value.toFixed(1).replace(".0", "")}${suffix}`;
}

type SortKey = "count" | "avg_price" | "avg_price_per_m2" | "avg_area_m2" | "located_pct";

interface SortState {
  key: SortKey;
  dir: "asc" | "desc";
}

const SORT_COLUMNS: { key: SortKey; label: string }[] = [
  { key: "count", label: "Oferty" },
  { key: "avg_price", label: "Śr. cena" },
  { key: "avg_price_per_m2", label: "Śr. cena/m²" },
  { key: "avg_area_m2", label: "Śr. metraż" },
  { key: "located_pct", label: "Mapa" },
];

function sortValue(row: StatsGroupOut, key: SortKey): number {
  if (key === "located_pct") return row.count === 0 ? 0 : row.located_count / row.count;
  return (row as unknown as Record<string, number>)[key] ?? 0;
}

function sortedRows(rows: StatsGroupOut[], sort: SortState): StatsGroupOut[] {
  const copy = [...rows];
  copy.sort((a, b) => {
    const va = sortValue(a, sort.key);
    const vb = sortValue(b, sort.key);
    return sort.dir === "asc" ? va - vb : vb - va;
  });
  return copy;
}

function GroupTable({
  title,
  rows,
  sort,
  onSort,
}: {
  title: string;
  rows: StatsGroupOut[];
  sort: SortState;
  onSort: (key: SortKey) => void;
}) {
  const displayed = sortedRows(rows, sort);
  function arrow(key: SortKey) {
    if (sort.key !== key) return "";
    return sort.dir === "asc" ? " ▲" : " ▼";
  }
  return (
    <section className="stats-card stats-card--wide">
      <h3>{title}</h3>
      <div className="stats-table-wrap">
        <table className="stats-table">
          <thead>
            <tr>
              <th>Nazwa</th>
              {SORT_COLUMNS.map((col) => (
                <th key={col.key} className="stats-table__sortable" onClick={() => onSort(col.key)}>
                  {col.label}
                  {arrow(col.key)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {displayed.map((row) => (
              <tr key={row.key}>
                <td>{row.key}</td>
                <td>{formatNumber(row.count)}</td>
                <td>{formatPrice(row.avg_price)}</td>
                <td>{formatPricePerM2(row.avg_price_per_m2)}</td>
                <td>{formatDecimal(row.avg_area_m2, " m²")}</td>
                <td>{percent(row.located_count, row.count)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ProviderTable({
  providers,
  sort,
  onSort,
}: {
  providers: StatsProviderOut[];
  sort: SortState;
  onSort: (key: SortKey) => void;
}) {
  const copy = [...providers];
  copy.sort((a, b) => {
    const va = sortValue(a as unknown as StatsGroupOut, sort.key);
    const vb = sortValue(b as unknown as StatsGroupOut, sort.key);
    return sort.dir === "asc" ? va - vb : vb - va;
  });
  function arrow(key: SortKey) {
    if (sort.key !== key) return "";
    return sort.dir === "asc" ? " ▲" : " ▼";
  }
  return (
    <section className="stats-card stats-card--wide">
      <h3>Providerzy</h3>
      <div className="stats-table-wrap">
        <table className="stats-table">
          <thead>
            <tr>
              <th>Nazwa</th>
              <th>Status</th>
              <th>Ostatni run</th>
              {SORT_COLUMNS.map((col) => (
                <th key={col.key} className="stats-table__sortable" onClick={() => onSort(col.key)}>
                  {col.label}
                  {arrow(col.key)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {copy.map((row) => (
              <tr key={row.source_id}>
                <td>{row.display_name}</td>
                <td>
                  <span className={row.enabled ? "badge badge--ok" : "badge badge--off"}>
                    {row.enabled ? "aktywny" : "wyłączony"}
                  </span>
                </td>
                <td>
                  {row.last_run_at
                    ? `${row.last_run_status ?? "?"} ${row.last_run_at.slice(0, 16).replace("T", " ")}`
                    : "—"}
                </td>
                <td>{formatNumber(row.count)}</td>
                <td>{formatPrice(row.avg_price)}</td>
                <td>{formatPricePerM2(row.avg_price_per_m2)}</td>
                <td>{formatDecimal(row.avg_area_m2, " m²")}</td>
                <td>{percent(row.located_count, row.count)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function BucketChart({ title, rows }: { title: string; rows: StatsBucketOut[] }) {
  const max = Math.max(1, ...rows.map((row) => row.count));
  return (
    <section className="stats-card">
      <h3>{title}</h3>
      <div className="stats-bars">
        {rows.map((row) => (
          <div key={row.key} className="stats-bar">
            <div className="stats-bar__label">
              <span>{row.key}</span>
              <strong>{formatNumber(row.count)}</strong>
            </div>
            <div className="stats-bar__track">
              <span style={{ width: `${Math.max(4, (row.count / max) * 100)}%` }} />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

interface FilterState {
  city: string;
  min_price: string;
  max_price: string;
  min_rooms: string;
  max_rooms: string;
  market: string;
  source_ids: string[];
}

function filtersFromParams(params: URLSearchParams): FilterState {
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

function paramsFromFilters(form: FilterState, current: URLSearchParams): URLSearchParams {
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

function queryFromFilters(filters: FilterState): StatsQuery {
  return {
    city: filters.city.trim() || undefined,
    source_id: filters.source_ids.length > 0 ? filters.source_ids : undefined,
    min_price: Number(filters.min_price) || undefined,
    max_price: Number(filters.max_price) || undefined,
    min_rooms: Number(filters.min_rooms) || undefined,
    max_rooms: Number(filters.max_rooms) || undefined,
    market: filters.market || undefined,
  };
}

export function StatsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [stats, setStats] = useState<StatsOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sources, setSources] = useState<string[]>([]);
  const [sorts, setSorts] = useState<Record<string, SortState>>({});

  function getSort(tableId: string): SortState {
    return sorts[tableId] ?? { key: "count", dir: "desc" };
  }

  function onSort(tableId: string, key: SortKey) {
    setSorts((prev) => {
      const cur = prev[tableId] ?? { key: "count" as SortKey, dir: "desc" as const };
      return {
        ...prev,
        [tableId]: {
          key,
          dir: cur.key === key && cur.dir === "desc" ? "asc" : "desc",
        },
      };
    });
  }

  const filters = useMemo(() => filtersFromParams(searchParams), [searchParams]);

  useEffect(() => {
    let ignore = false;

    void (async () => {
      try {
        const query = queryFromFilters(filters);
        const data = await getStats(query);
        if (!ignore) {
          setStats(data);
          setError(null);
        }
      } catch (err) {
        if (!ignore) {
          setError(err instanceof Error ? err.message : "Błąd pobierania statystyk");
        }
      }
    })();

    return () => {
      ignore = true;
    };
  }, [filters]);

  useEffect(() => {
    void getSettings()
      .then((s) => setSources(s.sources))
      .catch(() => {});
  }, []);

  function update(field: keyof FilterState, value: string) {
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

  if (error) return <p className="error">{error}</p>;
  if (!stats) return <p className="loading">Ładowanie statystyk…</p>;

  const { overview } = stats;

  return (
    <section className="stats-page">
      <header className="stats-header">
        <div>
          <h2>Statystyki rynku</h2>
          <p>Przekrój aktywnych ofert według lokalizacji, źródeł, cen i kompletności danych.</p>
        </div>
        {overview.latest_seen && (
          <span>Ostatnia obserwacja: {overview.latest_seen.slice(0, 16).replace("T", " ")}</span>
        )}
      </header>

      <form className="map-filters" onSubmit={applyFilters}>
        <label htmlFor="stats-city">
          Miasto
          <input
            id="stats-city"
            value={filters.city}
            onChange={(e) => update("city", e.target.value)}
            placeholder="np. Gdańsk"
          />
        </label>
        <label htmlFor="stats-min-price">
          Cena min.
          <input
            id="stats-min-price"
            inputMode="numeric"
            value={filters.min_price}
            onChange={(e) => update("min_price", e.target.value)}
          />
        </label>
        <label htmlFor="stats-max-price">
          Cena maks.
          <input
            id="stats-max-price"
            inputMode="numeric"
            value={filters.max_price}
            onChange={(e) => update("max_price", e.target.value)}
          />
        </label>
        <label htmlFor="stats-min-rooms">
          Pokoje min.
          <input
            id="stats-min-rooms"
            inputMode="numeric"
            value={filters.min_rooms}
            onChange={(e) => update("min_rooms", e.target.value)}
          />
        </label>
        <label htmlFor="stats-max-rooms">
          Pokoje maks.
          <input
            id="stats-max-rooms"
            inputMode="numeric"
            value={filters.max_rooms}
            onChange={(e) => update("max_rooms", e.target.value)}
          />
        </label>
        <label htmlFor="stats-market">
          Rynek
          <select
            id="stats-market"
            value={filters.market}
            onChange={(e) => update("market", e.target.value)}
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
        <button type="submit">Filtruj</button>
      </form>

      <div className="stats-kpis">
        <div className="stats-kpi">
          <span>Aktywne oferty</span>
          <strong>{formatNumber(overview.active_count)}</strong>
          <small>łącznie w bazie: {formatNumber(overview.total_count)}</small>
        </div>
        <div className="stats-kpi">
          <span>Średnia cena</span>
          <strong>{formatPrice(overview.avg_price)}</strong>
          <small>
            min/max: {formatPrice(overview.min_price)} / {formatPrice(overview.max_price)}
          </small>
        </div>
        <div className="stats-kpi">
          <span>Średnia cena/m²</span>
          <strong>{formatPricePerM2(overview.avg_price_per_m2)}</strong>
          <small>wycenione: {percent(overview.priced_count, overview.active_count)}</small>
        </div>
        <div className="stats-kpi">
          <span>Kompletność mapy</span>
          <strong>{percent(overview.located_count, overview.active_count)}</strong>
          <small>{formatNumber(overview.located_count)} ofert z koordynatami</small>
        </div>
        <div className="stats-kpi">
          <span>Średni metraż</span>
          <strong>{formatDecimal(overview.avg_area_m2, " m²")}</strong>
          <small>pokoje: {formatDecimal(overview.avg_rooms)}</small>
        </div>
        <div className="stats-kpi">
          <span>Jakość treści</span>
          <strong>{percent(overview.with_description_count, overview.active_count)}</strong>
          <small>zdjęcia: {percent(overview.with_images_count, overview.active_count)}</small>
        </div>
      </div>

      <div className="stats-grid">
        <GroupTable
          title="Dzielnice"
          rows={stats.by_district}
          sort={getSort("district")}
          onSort={(k) => onSort("district", k)}
        />
        <GroupTable
          title="Źródła"
          rows={stats.by_source}
          sort={getSort("source")}
          onSort={(k) => onSort("source", k)}
        />
        <GroupTable
          title="Miasta"
          rows={stats.by_city}
          sort={getSort("city")}
          onSort={(k) => onSort("city", k)}
        />
        <GroupTable
          title="Rynek"
          rows={stats.by_market}
          sort={getSort("market")}
          onSort={(k) => onSort("market", k)}
        />
        <ProviderTable
          providers={stats.by_provider}
          sort={getSort("provider")}
          onSort={(k) => onSort("provider", k)}
        />
        <BucketChart title="Rozkład pokoi" rows={stats.by_rooms} />
        <BucketChart title="Koszyki cenowe" rows={stats.price_buckets} />
      </div>
    </section>
  );
}
