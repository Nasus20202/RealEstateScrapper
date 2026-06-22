// frontend/src/features/listings/ListingCard.tsx
import { Link } from "react-router-dom";

import type { ListingOut } from "../../api/types";

function formatPrice(value: number | null): string {
  return value == null ? "—" : `${value.toLocaleString("pl-PL")} zł`;
}

function locationLine(listing: ListingOut): string {
  return [listing.district, listing.city].filter(Boolean).join(", ") || "—";
}

function BuildingIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="36"
      height="36"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <polyline points="9 22 9 12 15 12 15 22" />
    </svg>
  );
}

export function ListingCard({
  listing,
  onPreview,
}: {
  listing: ListingOut;
  onPreview?: (listing: ListingOut) => void;
}) {
  const cover = listing.images[0];

  return (
    <article
      className="listing-card"
      onClick={() => onPreview?.(listing)}
      role={onPreview ? "button" : undefined}
      tabIndex={onPreview ? 0 : undefined}
      onKeyDown={(event) => {
        if (onPreview && (event.key === "Enter" || event.key === " ")) {
          event.preventDefault();
          onPreview(listing);
        }
      }}
    >
      <div className="listing-card__media">
        {cover ? (
          <img src={cover} alt={listing.title} loading="lazy" />
        ) : (
          <div className="listing-card__media-placeholder">
            <BuildingIcon />
            <span>brak zdjęcia</span>
          </div>
        )}
      </div>

      <div className="listing-card__body">
        <div className="listing-card__badges">
          <span className="badge badge--source" data-source={listing.source_id}>
            {listing.source_id}
          </span>
          {listing.market && (
            <span className={`badge badge--market badge--market-${listing.market}`}>
              {listing.market === "primary" ? "nowe" : "wtórny"}
            </span>
          )}
        </div>

        <div className="listing-card__price-row">
          <span className="listing-card__price">{formatPrice(listing.price)}</span>
          <span className="listing-card__ppm">
            {listing.price_per_m2 != null
              ? `${listing.price_per_m2.toLocaleString("pl-PL")} zł/m²`
              : ""}
          </span>
        </div>

        <h3 className="listing-card__title">
          <Link to={`/listings/${listing.id}`} onClick={(event) => event.stopPropagation()}>
            {listing.title}
          </Link>
        </h3>

        <div className="listing-card__location">
          <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
          >
            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
            <circle cx="12" cy="10" r="3" />
          </svg>
          {locationLine(listing)}
        </div>

        <div className="listing-card__chips">
          {listing.rooms != null && <span className="chip">{listing.rooms} pok.</span>}
          {listing.area_m2 != null && <span className="chip">{listing.area_m2} m²</span>}
          {listing.floor != null && <span className="chip">{listing.floor} p.</span>}
        </div>

        {listing.score != null && (
          <p className="listing-card__score">
            <strong>Ocena LLM: {listing.score}</strong>
            {listing.reason ? ` — ${listing.reason}` : ""}
          </p>
        )}
      </div>
    </article>
  );
}
