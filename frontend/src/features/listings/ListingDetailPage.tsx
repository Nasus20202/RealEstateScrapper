// frontend/src/features/listings/ListingDetailPage.tsx
import { useEffect, useState, useTransition } from "react";
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import { Link, useParams } from "react-router-dom";

import { addFavorite, ApiError, getFavorites, getListing, removeFavorite } from "../../api/client";
import type { ListingDetailOut } from "../../api/types";
import { formatPrice, formatPricePerM2 } from "./format";
import { HtmlDescription } from "./html";
import { PriceSparkline } from "./PriceSparkline";

function addressLine(listing: ListingDetailOut): string {
  return [listing.street, listing.district, listing.city].filter(Boolean).join(", ") || "—";
}

function openStreetMapUrl(listing: ListingDetailOut): string {
  if (listing.lat != null && listing.lon != null) {
    return `https://www.openstreetmap.org/?mlat=${listing.lat}&mlon=${listing.lon}#map=17/${listing.lat}/${listing.lon}`;
  }
  return `https://www.openstreetmap.org/search?query=${encodeURIComponent(addressLine(listing))}`;
}

export function ListingDetailPage() {
  const { id } = useParams<{ id: string }>();
  const listingId = Number(id);
  const [listing, setListing] = useState<ListingDetailOut | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [isFavorite, setIsFavorite] = useState(false);
  const [busy, setBusy] = useState(false);
  const [selectedImage, setSelectedImage] = useState<number | null>(null);
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    startTransition(async () => {
      try {
        const [detail, favorites] = await Promise.all([getListing(listingId), getFavorites()]);
        setListing(detail);
        setIsFavorite(favorites.some((f) => f.listing_id === listingId));
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          setNotFound(true);
        } else {
          throw err;
        }
      }
    });
  }, [listingId]);

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

  if (isPending) {
    return <p className="loading">Ładowanie…</p>;
  }
  if (notFound) {
    return <p className="error">Nie znaleziono oferty.</p>;
  }
  if (!listing) {
    return <p className="loading">Ładowanie…</p>;
  }

  const mapPosition: [number, number] | null =
    listing.lat != null && listing.lon != null ? [listing.lat, listing.lon] : null;
  const images = listing.images;
  const currentImage = selectedImage == null ? null : images[selectedImage];

  function moveImage(delta: number) {
    setSelectedImage((current) => {
      if (current == null || images.length === 0) return current;
      return (current + delta + images.length) % images.length;
    });
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
          <dd>{formatPrice(listing.price)}</dd>
        </div>
        <div>
          <dt>Cena/m²</dt>
          <dd>{formatPricePerM2(listing.price_per_m2)}</dd>
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
          <dd>{addressLine(listing)}</dd>
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
            <button
              key={src}
              type="button"
              className="gallery-thumb"
              onClick={() => setSelectedImage(index)}
              aria-label={`Powiększ zdjęcie ${index + 1}`}
            >
              <img src={src} alt={`${listing.title} — zdjęcie ${index + 1}`} />
            </button>
          ))}
        </div>
      )}

      {mapPosition && (
        <section className="listing-detail__map-section">
          <h3>Mapa miejsca</h3>
          <div className="listing-detail__map">
            <MapContainer center={mapPosition} zoom={16} scrollWheelZoom>
              <TileLayer
                attribution="&copy; OpenStreetMap contributors &copy; CARTO"
                url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
              />
              <Marker position={mapPosition}>
                <Popup>{addressLine(listing)}</Popup>
              </Marker>
            </MapContainer>
          </div>
          <a href={openStreetMapUrl(listing)} target="_blank" rel="noreferrer">
            Otwórz w OpenStreetMap
          </a>
        </section>
      )}

      {currentImage && selectedImage != null && (
        <div
          className="listing-detail__lightbox"
          role="dialog"
          aria-modal="true"
          aria-label="Galeria zdjęć"
        >
          <button
            type="button"
            className="lightbox-close"
            onClick={() => setSelectedImage(null)}
            aria-label="Zamknij galerię"
          >
            ×
          </button>
          <button
            type="button"
            className="lightbox-nav lightbox-nav--prev"
            onClick={() => moveImage(-1)}
            aria-label="Poprzednie zdjęcie"
          >
            ‹
          </button>
          <img
            src={currentImage}
            alt={`${listing.title} — zdjęcie ${selectedImage + 1} z ${images.length}`}
          />
          <button
            type="button"
            className="lightbox-nav lightbox-nav--next"
            onClick={() => moveImage(1)}
            aria-label="Następne zdjęcie"
          >
            ›
          </button>
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

      {listing.description && (
        <section className="listing-detail__description">
          <h3>Opis</h3>
          <HtmlDescription className="rich-description" html={listing.description} />
        </section>
      )}

      {Object.keys(listing.attributes).length > 0 && (
        <section className="listing-detail__attributes">
          <h3>Tagi i cechy z ogłoszenia</h3>
          <div className="attribute-list">
            {Object.entries(listing.attributes).map(([key, value]) => (
              <span key={key} className="attribute-chip">
                {key}: {Array.isArray(value) ? value.join(", ") : String(value)}
              </span>
            ))}
          </div>
        </section>
      )}

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
