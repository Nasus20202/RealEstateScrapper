// frontend/src/features/listings/ListingsPage.tsx
import { useCallback, useEffect, useState } from "react";

import { getListings } from "../../api/client";
import type { ListingOut, ListingsQuery } from "../../api/types";
import { ListingCard } from "./ListingCard";
import { ListingsMap } from "./ListingsMap";

const PAGE_SIZE = 50;

type View = "list" | "compact" | "map";

interface FormState {
  city: string;
  max_price: string;
  min_price: string;
  min_rooms: string;
  max_rooms: string;
  min_area: string;
  max_area: string;
  districts: string;
  market: string;
  q: string;
}

const EMPTY_FORM: FormState = {
  city: "",
  max_price: "",
  min_price: "",
  min_rooms: "",
  max_rooms: "",
  min_area: "",
  max_area: "",
  districts: "",
  market: "",
  q: "",
};

const SORT_OPTIONS = [
  { value: "date-desc", label: "Najnowsze" },
  { value: "date-asc", label: "Najstarsze" },
  { value: "price_per_m2-asc", label: "Cena/m² rosnąco" },
  { value: "price_per_m2-desc", label: "Cena/m² malejąco" },
  { value: "price-asc", label: "Cena rosnąco" },
  { value: "price-desc", label: "Cena malejąco" },
  { value: "area-desc", label: "Największe" },
  { value: "area-asc", label: "Najmniejsze" },
];

function toNumber(value: string): number | undefined {
  const trimmed = value.trim();
  if (trimmed === "") return undefined;
  const parsed = Number(trimmed);
  return Number.isNaN(parsed) ? undefined : parsed;
}

function buildQuery(form: FormState, offset: number, sort: string): ListingsQuery {
  const districts = form.districts
    .split(",")
    .map((d) => d.trim())
    .filter((d) => d.length > 0);
  const [sort_by, sort_dir] = sort.split("-") as [string, "asc" | "desc"];
  return {
    city: form.city.trim() || undefined,
    min_price: toNumber(form.min_price),
    max_price: toNumber(form.max_price),
    min_rooms: toNumber(form.min_rooms),
    max_rooms: toNumber(form.max_rooms),
    min_area: toNumber(form.min_area),
    max_area: toNumber(form.max_area),
    district: districts.length > 0 ? districts : undefined,
    market: form.market.trim() || undefined,
    q: form.q.trim() || undefined,
    sort_by,
    sort_dir,
    limit: PAGE_SIZE,
    offset,
  };
}

export function ListingsPage() {
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [applied, setApplied] = useState<FormState>(EMPTY_FORM);
  const [offset, setOffset] = useState(0);
  const [sort, setSort] = useState("date-desc");
  const [items, setItems] = useState<ListingOut[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState<View>("list");
  const [showMore, setShowMore] = useState(false);

  const load = useCallback(async (current: FormState, currentOffset: number, currentSort: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await getListings(buildQuery(current, currentOffset, currentSort));
      setItems(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Błąd pobierania");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(applied, offset, sort);
  }, [applied, offset, sort, load]);

  function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setOffset(0);
    setApplied(form);
  }

  function onSortChange(value: string) {
    setSort(value);
    setOffset(0);
  }

  function update(field: keyof FormState, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  return (
    <section className="listings-page">
      <form className="filters" onSubmit={onSubmit}>
        <label htmlFor="f-city">
          Miasto
          <input id="f-city" value={form.city} onChange={(e) => update("city", e.target.value)} placeholder="np. Gdańsk" />
        </label>

        <label htmlFor="f-min-price">
          Cena min.
          <input
            id="f-min-price"
            inputMode="numeric"
            value={form.min_price}
            onChange={(e) => update("min_price", e.target.value)}
            placeholder="zł"
          />
        </label>

        <label htmlFor="f-max-price">
          Cena maks.
          <input
            id="f-max-price"
            inputMode="numeric"
            value={form.max_price}
            onChange={(e) => update("max_price", e.target.value)}
            placeholder="zł"
          />
        </label>

        <label htmlFor="f-min-rooms">
          Pokoje min.
          <input
            id="f-min-rooms"
            inputMode="numeric"
            value={form.min_rooms}
            onChange={(e) => update("min_rooms", e.target.value)}
            placeholder="1"
          />
        </label>

        <label htmlFor="f-max-rooms">
          Pokoje maks.
          <input
            id="f-max-rooms"
            inputMode="numeric"
            value={form.max_rooms}
            onChange={(e) => update("max_rooms", e.target.value)}
            placeholder="5"
          />
        </label>

        <label htmlFor="f-market">
          Rynek
          <select id="f-market" value={form.market} onChange={(e) => update("market", e.target.value)}>
            <option value="">Wszystkie</option>
            <option value="primary">Pierwotny</option>
            <option value="secondary">Wtórny</option>
          </select>
        </label>

        <div className="filters__more-toggle">
          <button type="button" className="btn-ghost btn-sm" onClick={() => setShowMore((v) => !v)}>
            {showMore ? "Mniej filtrów ▲" : "Więcej filtrów ▼"}
          </button>
        </div>

        {showMore && (
          <>
            <label htmlFor="f-min-area">
              Pow. min. (m²)
              <input
                id="f-min-area"
                inputMode="decimal"
                value={form.min_area}
                onChange={(e) => update("min_area", e.target.value)}
              />
            </label>

            <label htmlFor="f-max-area">
              Pow. maks. (m²)
              <input
                id="f-max-area"
                inputMode="decimal"
                value={form.max_area}
                onChange={(e) => update("max_area", e.target.value)}
              />
            </label>

            <label htmlFor="f-districts">
              Dzielnice (przecinki)
              <input
                id="f-districts"
                value={form.districts}
                onChange={(e) => update("districts", e.target.value)}
                placeholder="Wrzeszcz, Oliwa, …"
              />
            </label>

            <label htmlFor="f-q">
              Zapytanie (NL)
              <input id="f-q" value={form.q} onChange={(e) => update("q", e.target.value)} placeholder="np. blisko morza z balkonem" />
            </label>
          </>
        )}

        <button type="submit" className="filters__submit">Szukaj</button>
      </form>

      <div className="listings-toolbar">
        <p className="listings-page__total">
          Znaleziono: {total}
          {loading && <span className="loading-dot"> •••</span>}
        </p>
        <div className="toolbar-right">
          <label htmlFor="sort-select" className="sort-label">
            Sortuj:
            <select id="sort-select" value={sort} onChange={(e) => onSortChange(e.target.value)}>
              {SORT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </label>
          <div className="view-toggle" role="group" aria-label="Widok">
            <button
              type="button"
              className={view === "list" ? "active" : ""}
              aria-pressed={view === "list"}
              onClick={() => setView("list")}
            >
              Lista
            </button>
            <button
              type="button"
              className={view === "compact" ? "active" : ""}
              aria-pressed={view === "compact"}
              onClick={() => setView("compact")}
            >
              Kompakt
            </button>
            <button
              type="button"
              className={view === "map" ? "active" : ""}
              aria-pressed={view === "map"}
              onClick={() => setView("map")}
            >
              Mapa
            </button>
          </div>
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      {view === "map" ? (
        <ListingsMap listings={items} />
      ) : items.length === 0 && !loading ? (
        <p className="empty-state">Brak ofert. Zmień filtry lub uruchom scraping.</p>
      ) : (
        <div className={view === "compact" ? "listings-grid listings-grid--compact" : "listings-grid"}>
          {items.map((item) => (
            <ListingCard key={item.id} listing={item} />
          ))}
        </div>
      )}

      <div className="pagination">
        <button
          type="button"
          className="btn-ghost"
          disabled={offset === 0}
          onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
        >
          Poprzednia
        </button>
        <span>
          {currentPage} / {totalPages}
        </span>
        <button
          type="button"
          className="btn-ghost"
          disabled={offset + PAGE_SIZE >= total}
          onClick={() => setOffset((o) => o + PAGE_SIZE)}
        >
          Następna
        </button>
      </div>
    </section>
  );
}
