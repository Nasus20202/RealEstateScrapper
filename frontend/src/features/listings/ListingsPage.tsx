// frontend/src/features/listings/ListingsPage.tsx
import { useCallback, useEffect, useMemo, useState, useTransition } from "react";
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import { useMap } from "react-leaflet";
import { useSearchParams } from "react-router-dom";

import { getListings, getSettings } from "../../api/client";
import type { ListingOut, ListingsQuery } from "../../api/types";
import { formatPrice, formatPricePerM2 } from "./format";
import { HtmlDescription } from "./html";
import { ListingCard } from "./ListingCard";

const DEFAULT_PAGE_SIZE = 50;
const PAGE_SIZE_OPTIONS = [25, 50, 100, 200];

const DISTRICTS = [
  "Aniołki",
  "Brzeźno",
  "Chełm",
  "Dolny Sopot",
  "Działki Leśne",
  "Górny Sopot",
  "Jasień",
  "Karwiny",
  "Letnica",
  "Mały Kack",
  "Morena",
  "Oliwa",
  "Orłowo",
  "Osowa",
  "Piecki-Migowo",
  "Przymorze",
  "Redłowo",
  "Śródmieście",
  "Ujeścisko",
  "Witomino",
  "Wrzeszcz",
  "Zaspa",
  "Żabianka",
];

type View = "default" | "compact" | "list";

interface FormState {
  city: string;
  max_price: string;
  min_price: string;
  min_rooms: string;
  max_rooms: string;
  min_area: string;
  max_area: string;
  districts: string[];
  market: string;
  source_ids: string[];
  q: string;
}

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

function buildQuery(
  form: FormState,
  offset: number,
  sort: string,
  pageSize: number,
): ListingsQuery {
  const [sort_by, sort_dir] = sort.split("-") as [string, "asc" | "desc"];
  return {
    city: form.city.trim() || undefined,
    min_price: toNumber(form.min_price),
    max_price: toNumber(form.max_price),
    min_rooms: toNumber(form.min_rooms),
    max_rooms: toNumber(form.max_rooms),
    min_area: toNumber(form.min_area),
    max_area: toNumber(form.max_area),
    district: form.districts.length > 0 ? form.districts : undefined,
    source_id: form.source_ids.length > 0 ? form.source_ids : undefined,
    market: form.market.trim() || undefined,
    q: form.q.trim() || undefined,
    sort_by,
    sort_dir,
    limit: pageSize,
    offset,
  };
}

function formFromParams(params: URLSearchParams): FormState {
  return {
    city: params.get("city") ?? "",
    max_price: params.get("max_price") ?? "",
    min_price: params.get("min_price") ?? "",
    min_rooms: params.get("min_rooms") ?? "",
    max_rooms: params.get("max_rooms") ?? "",
    min_area: params.get("min_area") ?? "",
    max_area: params.get("max_area") ?? "",
    districts: params.getAll("district"),
    market: params.get("market") ?? "",
    source_ids: params.getAll("source_id"),
    q: params.get("q") ?? "",
  };
}

function pageSizeFromParams(params: URLSearchParams): number {
  const parsed = Number(params.get("limit") ?? DEFAULT_PAGE_SIZE);
  return PAGE_SIZE_OPTIONS.includes(parsed) ? parsed : DEFAULT_PAGE_SIZE;
}

function offsetFromParams(params: URLSearchParams): number {
  const parsed = Number(params.get("offset") ?? 0);
  return Number.isNaN(parsed) || parsed < 0 ? 0 : parsed;
}

function sortFromParams(params: URLSearchParams): string {
  const sortBy = params.get("sort_by") ?? "date";
  const sortDir = params.get("sort_dir") ?? "desc";
  const value = `${sortBy}-${sortDir}`;
  return SORT_OPTIONS.some((option) => option.value === value) ? value : "date-desc";
}

function viewFromParams(params: URLSearchParams): View {
  const view = params.get("view");
  if (view === "compact" || view === "list") return view;
  return "default";
}

function paramsFromState(
  form: FormState,
  offset: number,
  sort: string,
  pageSize: number,
  view: View,
): URLSearchParams {
  const params = new URLSearchParams();
  if (form.city.trim()) params.set("city", form.city.trim());
  if (form.min_price.trim()) params.set("min_price", form.min_price.trim());
  if (form.max_price.trim()) params.set("max_price", form.max_price.trim());
  if (form.min_rooms.trim()) params.set("min_rooms", form.min_rooms.trim());
  if (form.max_rooms.trim()) params.set("max_rooms", form.max_rooms.trim());
  if (form.min_area.trim()) params.set("min_area", form.min_area.trim());
  if (form.max_area.trim()) params.set("max_area", form.max_area.trim());
  for (const district of form.districts) params.append("district", district);
  if (form.market.trim()) params.set("market", form.market.trim());
  for (const source of form.source_ids) params.append("source_id", source);
  if (form.q.trim()) params.set("q", form.q.trim());
  const [sort_by, sort_dir] = sort.split("-");
  params.set("sort_by", sort_by);
  params.set("sort_dir", sort_dir);
  params.set("limit", String(pageSize));
  if (offset > 0) params.set("offset", String(offset));
  if (view !== "default") params.set("view", view);
  return params;
}

function previewAddress(listing: ListingOut): string {
  return [listing.street, listing.district, listing.city].filter(Boolean).join(", ") || "—";
}

function PreviewMapSync({ center }: { center: [number, number] }) {
  const map = useMap();

  useEffect(() => {
    map.setView(center, map.getZoom(), { animate: true });
  }, [center, map]);

  return null;
}

export function ListingsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [form, setForm] = useState<FormState>(() => formFromParams(searchParams));
  const offset = useMemo(() => offsetFromParams(searchParams), [searchParams]);
  const sort = useMemo(() => sortFromParams(searchParams), [searchParams]);
  const pageSize = useMemo(() => pageSizeFromParams(searchParams), [searchParams]);
  const view = useMemo(() => viewFromParams(searchParams), [searchParams]);
  const [availableSources, setAvailableSources] = useState<string[]>([]);
  const [preview, setPreview] = useState<ListingOut | null>(null);
  const [previewImageIndex, setPreviewImageIndex] = useState(0);
  const [items, setItems] = useState<ListingOut[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const [prevSearchParams, setPrevSearchParams] = useState(searchParams);
  if (searchParams !== prevSearchParams) {
    setForm(formFromParams(searchParams));
    setPrevSearchParams(searchParams);
  }

  const load = useCallback(
    (current: FormState, currentOffset: number, currentSort: string, currentPageSize: number) => {
      startTransition(async () => {
        try {
          const res = await getListings(
            buildQuery(current, currentOffset, currentSort, currentPageSize),
          );
          setItems(res.items);
          setTotal(res.total);
        } catch (err) {
          setError(err instanceof Error ? err.message : "Błąd pobierania");
        }
      });
    },
    [startTransition],
  );

  useEffect(() => {
    load(formFromParams(searchParams), offset, sort, pageSize);
  }, [searchParams, load, offset, sort, pageSize]);

  useEffect(() => {
    void getSettings()
      .then((settings) => setAvailableSources(settings.sources))
      .catch(() => {});
  }, []);

  function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSearchParams(paramsFromState(form, 0, sort, pageSize, view));
  }

  function onSortChange(value: string) {
    setSearchParams(paramsFromState(form, 0, value, pageSize, view));
  }

  function onPageSizeChange(value: string) {
    const parsed = Number(value);
    const next = PAGE_SIZE_OPTIONS.includes(parsed) ? parsed : DEFAULT_PAGE_SIZE;
    setSearchParams(paramsFromState(form, 0, sort, next, view));
  }

  function onViewChange(nextView: View) {
    setSearchParams(paramsFromState(form, offset, sort, pageSize, nextView));
  }

  function update(field: keyof FormState, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  function toggleMulti(field: "districts" | "source_ids", value: string) {
    setForm((prev) => {
      const selected = prev[field];
      return {
        ...prev,
        [field]: selected.includes(value)
          ? selected.filter((item) => item !== value)
          : [...selected, value],
      };
    });
  }

  function setPreviewListing(listing: ListingOut) {
    setPreview(listing);
    setPreviewImageIndex(0);
  }

  function movePreviewImage(delta: number) {
    setPreviewImageIndex((current) => {
      const count = preview?.images.length ?? 0;
      if (count === 0) return 0;
      return (current + delta + count) % count;
    });
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const currentPage = Math.floor(offset / pageSize) + 1;
  const previewMapCenter: [number, number] | null =
    preview?.lat != null && preview.lon != null ? [preview.lat, preview.lon] : null;

  return (
    <section className="listings-page">
      <div className="listings-shell">
        <form className="filters filters--sticky" onSubmit={onSubmit}>
          <label htmlFor="f-city">
            Miasto
            <input
              id="f-city"
              value={form.city}
              onChange={(e) => update("city", e.target.value)}
              placeholder="np. Gdańsk"
            />
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
            <select
              id="f-market"
              value={form.market}
              onChange={(e) => update("market", e.target.value)}
            >
              <option value="">Wszystkie</option>
              <option value="primary">Pierwotny</option>
              <option value="secondary">Wtórny</option>
            </select>
          </label>

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
            Dzielnice
            <div id="f-districts" className="multi-select-list">
              {DISTRICTS.map((district) => (
                <label key={district} className="multi-select-option">
                  <input
                    type="checkbox"
                    checked={form.districts.includes(district)}
                    onChange={() => toggleMulti("districts", district)}
                  />
                  {district}
                </label>
              ))}
            </div>
          </label>

          {availableSources.length > 0 && (
            <label htmlFor="f-sources">
              Źródło oferty
              <div id="f-sources" className="multi-select-list multi-select-list--sources">
                {availableSources.map((source) => (
                  <label key={source} className="multi-select-option">
                    <input
                      type="checkbox"
                      checked={form.source_ids.includes(source)}
                      onChange={() => toggleMulti("source_ids", source)}
                    />
                    {source}
                  </label>
                ))}
              </div>
            </label>
          )}

          <label htmlFor="f-q">
            Zapytanie (NL)
            <input
              id="f-q"
              value={form.q}
              onChange={(e) => update("q", e.target.value)}
              placeholder="np. blisko morza z balkonem"
            />
          </label>

          <button type="submit" className="filters__submit">
            Szukaj
          </button>
        </form>

        <div className="listings-content">
          <div className="listings-toolbar">
            <p className="listings-page__total">
              Znaleziono: {total}
              {isPending && <span className="loading-dot"> •••</span>}
            </p>
            <div className="toolbar-right">
              <label htmlFor="sort-select" className="sort-label">
                Sortuj:
                <select
                  id="sort-select"
                  value={sort}
                  onChange={(e) => onSortChange(e.target.value)}
                >
                  {SORT_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
              <label htmlFor="page-size-select" className="sort-label">
                Na stronie:
                <select
                  id="page-size-select"
                  value={pageSize}
                  onChange={(e) => onPageSizeChange(e.target.value)}
                >
                  {PAGE_SIZE_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
              <div className="view-toggle" role="group" aria-label="Widok">
                <button
                  type="button"
                  className={view === "default" ? "active" : ""}
                  aria-pressed={view === "default"}
                  onClick={() => onViewChange("default")}
                >
                  Domyślny
                </button>
                <button
                  type="button"
                  className={view === "compact" ? "active" : ""}
                  aria-pressed={view === "compact"}
                  onClick={() => onViewChange("compact")}
                >
                  Kompaktowy
                </button>
                <button
                  type="button"
                  className={view === "list" ? "active" : ""}
                  aria-pressed={view === "list"}
                  onClick={() => onViewChange("list")}
                >
                  Lista
                </button>
              </div>
            </div>
          </div>

          {error && <p className="error">{error}</p>}

          {items.length === 0 && !isPending ? (
            <p className="empty-state">Brak ofert. Zmień filtry lub uruchom scraping.</p>
          ) : (
            <div className={`listings-grid listings-grid--${view}`}>
              {items.map((item) => (
                <ListingCard
                  key={item.id}
                  listing={item}
                  variant={view}
                  onPreview={setPreviewListing}
                />
              ))}
            </div>
          )}

          <div className="pagination">
            <button
              type="button"
              className="btn-ghost"
              disabled={offset === 0}
              onClick={() =>
                setSearchParams(
                  paramsFromState(form, Math.max(0, offset - pageSize), sort, pageSize, view),
                )
              }
            >
              Poprzednia
            </button>
            <span>
              {currentPage} / {totalPages}
            </span>
            <button
              type="button"
              className="btn-ghost"
              disabled={offset + pageSize >= total}
              onClick={() =>
                setSearchParams(paramsFromState(form, offset + pageSize, sort, pageSize, view))
              }
            >
              Następna
            </button>
          </div>
        </div>

        <aside className="listing-preview">
          {preview ? (
            <>
              <button
                type="button"
                className="btn-ghost listing-preview__close"
                onClick={() => setPreview(null)}
              >
                Zamknij
              </button>
              {preview.images.length > 0 && (
                <div className="listing-preview__gallery">
                  <img
                    src={preview.images[previewImageIndex] ?? preview.images[0]}
                    alt={`${preview.title} — zdjęcie ${previewImageIndex + 1}`}
                  />
                  {preview.images.length > 1 && (
                    <div className="listing-preview__gallery-controls">
                      <button
                        type="button"
                        className="btn-ghost btn-sm"
                        onClick={() => movePreviewImage(-1)}
                      >
                        ‹
                      </button>
                      <span>
                        {previewImageIndex + 1} / {preview.images.length}
                      </span>
                      <button
                        type="button"
                        className="btn-ghost btn-sm"
                        onClick={() => movePreviewImage(1)}
                      >
                        ›
                      </button>
                    </div>
                  )}
                </div>
              )}
              <div className="listing-preview__body">
                <div className="listing-preview__price">{formatPrice(preview.price)}</div>
                <h3>{preview.title}</h3>
                <dl className="listing-preview__details">
                  <div>
                    <dt>Adres</dt>
                    <dd>
                      {[preview.street, preview.district, preview.city]
                        .filter(Boolean)
                        .join(", ") || "—"}
                    </dd>
                  </div>
                  <div>
                    <dt>Źródło</dt>
                    <dd>{preview.source_id}</dd>
                  </div>
                  <div>
                    <dt>Rynek</dt>
                    <dd>{preview.market === "primary" ? "pierwotny" : (preview.market ?? "—")}</dd>
                  </div>
                  <div>
                    <dt>Cena/m²</dt>
                    <dd>
                      {preview.price_per_m2 == null ? "—" : formatPricePerM2(preview.price_per_m2)}
                    </dd>
                  </div>
                  <div>
                    <dt>Powierzchnia</dt>
                    <dd>{preview.area_m2 == null ? "—" : `${preview.area_m2} m²`}</dd>
                  </div>
                  <div>
                    <dt>Pokoje</dt>
                    <dd>{preview.rooms ?? "—"}</dd>
                  </div>
                  <div>
                    <dt>Piętro</dt>
                    <dd>{preview.floor ?? "—"}</dd>
                  </div>
                </dl>
                {previewMapCenter && (
                  <div className="listing-preview__map">
                    <MapContainer center={previewMapCenter} zoom={13} scrollWheelZoom={false}>
                      <PreviewMapSync center={previewMapCenter} />
                      <TileLayer
                        attribution="&copy; OpenStreetMap contributors &copy; CARTO"
                        url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
                      />
                      <Marker position={previewMapCenter}>
                        <Popup>{previewAddress(preview)}</Popup>
                      </Marker>
                    </MapContainer>
                  </div>
                )}
                <div className="listing-card__chips">
                  {preview.rooms != null && <span className="chip">{preview.rooms} pok.</span>}
                  {preview.area_m2 != null && <span className="chip">{preview.area_m2} m²</span>}
                  {preview.price_per_m2 != null && (
                    <span className="chip">{formatPricePerM2(preview.price_per_m2)}</span>
                  )}
                </div>
                {preview.description && (
                  <HtmlDescription
                    className="listing-preview__description rich-description"
                    html={preview.description}
                  />
                )}
                <a className="btn-link" href={`/listings/${preview.id}`}>
                  Otwórz szczegóły
                </a>
              </div>
            </>
          ) : (
            <div className="listing-preview__empty">
              Kliknij ofertę na liście, aby zobaczyć podgląd bez zmiany strony.
            </div>
          )}
        </aside>
      </div>
    </section>
  );
}
