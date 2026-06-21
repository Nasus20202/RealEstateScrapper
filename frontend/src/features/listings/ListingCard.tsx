// frontend/src/features/listings/ListingCard.tsx
import { Link } from "react-router-dom";

import type { ListingOut } from "../../api/types";

function formatPrice(value: number | null): string {
  return value == null ? "—" : `${value.toLocaleString("pl-PL")} zł`;
}

function locationLine(listing: ListingOut): string {
  return [listing.district, listing.city].filter(Boolean).join(", ") || "—";
}

export function ListingCard({ listing }: { listing: ListingOut }) {
  const cover = listing.images[0];
  return (
    <article className="listing-card">
      <div className="listing-card__media">
        {cover ? (
          <img src={cover} alt={listing.title} loading="lazy" />
        ) : (
          <div className="listing-card__media-placeholder">brak zdjęcia</div>
        )}
        <span className="badge badge--source">{listing.source_id}</span>
      </div>

      <div className="listing-card__body">
        <div>
          <div className="listing-card__price">{formatPrice(listing.price)}</div>
          <div className="listing-card__ppm">
            {listing.price_per_m2 == null
              ? "cena/m² —"
              : `${listing.price_per_m2.toLocaleString("pl-PL")} zł/m²`}
          </div>
        </div>

        <h3 className="listing-card__title">
          <Link to={`/listings/${listing.id}`}>{listing.title}</Link>
        </h3>

        <div className="listing-card__location">{locationLine(listing)}</div>

        <div className="listing-card__chips">
          {listing.rooms != null && <span className="chip">{listing.rooms} pok.</span>}
          {listing.area_m2 != null && <span className="chip">{listing.area_m2} m²</span>}
          {listing.floor != null && <span className="chip">piętro {listing.floor}</span>}
          {listing.market && <span className="chip">{listing.market}</span>}
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
