// frontend/src/features/listings/ListingsPage.tsx
import { useCallback, useEffect, useState } from "react";

import { getListings } from "../../api/client";
import type { ListingOut, ListingsQuery } from "../../api/types";
import { ListingCard } from "./ListingCard";
import { ListingsMap } from "./ListingsMap";

const PAGE_SIZE = 50;

type View = "list" | "map";

interface FormState {
  city: string;
  max_price: string;
  min_price: string;
  min_rooms: string;
  max_rooms: string;
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
  districts: "",
  market: "",
  q: "",
};

function toNumber(value: string): number | undefined {
  const trimmed = value.trim();
  if (trimmed === "") return undefined;
  const parsed = Number(trimmed);
  return Number.isNaN(parsed) ? undefined : parsed;
}

function buildQuery(form: FormState, offset: number): ListingsQuery {
  const districts = form.districts
    .split(",")
    .map((d) => d.trim())
    .filter((d) => d.length > 0);
  return {
    city: form.city.trim() || undefined,
    min_price: toNumber(form.min_price),
    max_price: toNumber(form.max_price),
    min_rooms: toNumber(form.min_rooms),
    max_rooms: toNumber(form.max_rooms),
    district: districts.length > 0 ? districts : undefined,
    market: form.market.trim() || undefined,
    q: form.q.trim() || undefined,
    limit: PAGE_SIZE,
    offset,
  };
}

export function ListingsPage() {
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [applied, setApplied] = useState<FormState>(EMPTY_FORM);
  const [offset, setOffset] = useState(0);
  const [items, setItems] = useState<ListingOut[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState<View>("list");

  const load = useCallback(async (current: FormState, currentOffset: number) => {
    setLoading(true);
    setError(null);
    try {
      const res = await getListings(buildQuery(current, currentOffset));
      setItems(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Błąd pobierania");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(applied, offset);
  }, [applied, offset, load]);

  function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setOffset(0);
    setApplied(form);
  }

  function update(field: keyof FormState, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  return (
    <section className="listings-page">
      <form className="filters" onSubmit={onSubmit}>
        <label htmlFor="f-city">
          Miasto
          <input id="f-city" value={form.city} onChange={(e) => update("city", e.target.value)} />
        </label>

        <label htmlFor="f-min-price">
          Cena min.
          <input
            id="f-min-price"
            inputMode="numeric"
            value={form.min_price}
            onChange={(e) => update("min_price", e.target.value)}
          />
        </label>

        <label htmlFor="f-max-price">
          Cena maks.
          <input
            id="f-max-price"
            inputMode="numeric"
            value={form.max_price}
            onChange={(e) => update("max_price", e.target.value)}
          />
        </label>

        <label htmlFor="f-min-rooms">
          Pokoje min.
          <input
            id="f-min-rooms"
            inputMode="numeric"
            value={form.min_rooms}
            onChange={(e) => update("min_rooms", e.target.value)}
          />
        </label>

        <label htmlFor="f-max-rooms">
          Pokoje maks.
          <input
            id="f-max-rooms"
            inputMode="numeric"
            value={form.max_rooms}
            onChange={(e) => update("max_rooms", e.target.value)}
          />
        </label>

        <label htmlFor="f-districts">
          Dzielnice (przecinki)
          <input
            id="f-districts"
            value={form.districts}
            onChange={(e) => update("districts", e.target.value)}
          />
        </label>

        <label htmlFor="f-market">
          Rynek
          <input id="f-market" value={form.market} onChange={(e) => update("market", e.target.value)} />
        </label>

        <label htmlFor="f-q">
          Zapytanie (NL)
          <input id="f-q" value={form.q} onChange={(e) => update("q", e.target.value)} />
        </label>

        <button type="submit">Szukaj</button>
      </form>

      <div className="listings-toolbar">
        <p className="listings-page__total">Znaleziono: {total}</p>
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
            className={view === "map" ? "active" : ""}
            aria-pressed={view === "map"}
            onClick={() => setView("map")}
          >
            Mapa
          </button>
        </div>
      </div>

      {error && <p className="error">{error}</p>}
      {loading && <p className="loading">Ładowanie…</p>}

      {view === "map" ? (
        <ListingsMap listings={items} />
      ) : items.length === 0 && !loading ? (
        <p className="empty-state">Brak ofert. Zmień filtry lub uruchom scraping.</p>
      ) : (
        <div className="listings-grid">
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
          {Math.floor(offset / PAGE_SIZE) + 1} /{" "}
          {Math.max(1, Math.ceil(total / PAGE_SIZE))}
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
