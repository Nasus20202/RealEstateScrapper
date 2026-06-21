// frontend/src/features/listings/ListingDetailPage.tsx
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  addFavorite,
  ApiError,
  getFavorites,
  getListing,
  removeFavorite,
} from "../../api/client";
import type { ListingDetailOut } from "../../api/types";
import { PriceSparkline } from "./PriceSparkline";

export function ListingDetailPage() {
  const { id } = useParams<{ id: string }>();
  const listingId = Number(id);
  const [listing, setListing] = useState<ListingDetailOut | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [isFavorite, setIsFavorite] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setNotFound(false);
    try {
      const [detail, favorites] = await Promise.all([
        getListing(listingId),
        getFavorites(),
      ]);
      setListing(detail);
      setIsFavorite(favorites.some((f) => f.listing_id === listingId));
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setNotFound(true);
      } else {
        throw err;
      }
    }
  }, [listingId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function toggleFavorite() {
    setBusy(true);
    try {
      if (isFavorite) {
        await removeFavorite(listingId);
        setIsFavorite(false);
      } else {
        await addFavorite(listingId);
        setIsFavorite(true);
      }
    } finally {
      setBusy(false);
    }
  }

  if (notFound) {
    return <p className="error">Nie znaleziono oferty.</p>;
  }
  if (!listing) {
    return <p className="loading">Ładowanie…</p>;
  }

  return (
    <article className="listing-detail">
      <header className="listing-detail__header">
        <h2>{listing.title}</h2>
        <button type="button" disabled={busy} onClick={() => void toggleFavorite()}>
          {isFavorite ? "Usuń z ulubionych" : "Dodaj do ulubionych"}
        </button>
      </header>

      <dl className="listing-detail__fields">
        <div>
          <dt>Cena</dt>
          <dd>{listing.price == null ? "—" : `${listing.price.toLocaleString("pl-PL")} zł`}</dd>
        </div>
        <div>
          <dt>Cena/m²</dt>
          <dd>{listing.price_per_m2 == null ? "—" : `${listing.price_per_m2.toLocaleString("pl-PL")} zł/m²`}</dd>
        </div>
        <div>
          <dt>Powierzchnia</dt>
          <dd>{listing.area_m2 == null ? "—" : `${listing.area_m2} m²`}</dd>
        </div>
        <div>
          <dt>Pokoje</dt>
          <dd>{listing.rooms ?? "—"}</dd>
        </div>
        <div>
          <dt>Piętro</dt>
          <dd>
            {listing.floor ?? "—"}
            {listing.total_floors != null ? ` / ${listing.total_floors}` : ""}
          </dd>
        </div>
        <div>
          <dt>Lokalizacja</dt>
          <dd>
            {[listing.city, listing.district, listing.street]
              .filter(Boolean)
              .join(", ") || "—"}
          </dd>
        </div>
        <div>
          <dt>Rynek</dt>
          <dd>{listing.market ?? "—"}</dd>
        </div>
        <div>
          <dt>Źródło</dt>
          <dd>
            <a href={listing.url} target="_blank" rel="noreferrer">
              {listing.source_id}
            </a>
          </dd>
        </div>
      </dl>

      {listing.images.length > 0 && (
        <div className="listing-detail__gallery">
          {listing.images.map((src, index) => (
            <img key={src} src={src} alt={`${listing.title} — zdjęcie ${index + 1}`} />
          ))}
        </div>
      )}

      <section className="listing-detail__history">
        <h3>Historia cen</h3>
        {listing.price_history.length === 0 ? (
          <p>Brak historii cen.</p>
        ) : (
          <PriceSparkline history={listing.price_history} />
        )}
      </section>

      {listing.summary && (
        <section className="listing-detail__summary">
          <h3>Podsumowanie LLM</h3>
          <p>{listing.summary}</p>
        </section>
      )}

      {listing.features && Object.keys(listing.features).length > 0 && (
        <section className="listing-detail__features">
          <h3>Cechy</h3>
          <ul>
            {Object.entries(listing.features).map(([key, value]) => (
              <li key={key}>
                {key}: {String(value)}
              </li>
            ))}
          </ul>
        </section>
      )}

      {listing.duplicate_listing_ids.length > 0 && (
        <section className="listing-detail__duplicates">
          <h3>Duplikaty</h3>
          <ul>
            {listing.duplicate_listing_ids.map((dupId) => (
              <li key={dupId}>
                <Link to={`/listings/${dupId}`}>{dupId}</Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </article>
  );
}
