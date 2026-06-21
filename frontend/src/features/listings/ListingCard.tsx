// frontend/src/features/listings/ListingCard.tsx
import { Link } from "react-router-dom";

import type { ListingOut } from "../../api/types";

function formatPrice(value: number | null): string {
  return value == null ? "—" : `${value.toLocaleString("pl-PL")} zł`;
}

export function ListingCard({ listing }: { listing: ListingOut }) {
  return (
    <article className="listing-card">
      <h3 className="listing-card__title">
        <Link to={`/listings/${listing.id}`}>{listing.title}</Link>
      </h3>
      <span className="badge badge--source">{listing.source_id}</span>
      <dl className="listing-card__meta">
        <div>
          <dt>Cena</dt>
          <dd>{formatPrice(listing.price)}</dd>
        </div>
        <div>
          <dt>Cena/m²</dt>
          <dd>
            {listing.price_per_m2 == null
              ? "—"
              : `${listing.price_per_m2.toLocaleString("pl-PL")} zł/m²`}
          </dd>
        </div>
        <div>
          <dt>Pokoje</dt>
          <dd>{listing.rooms ?? "—"}</dd>
        </div>
        <div>
          <dt>Dzielnica</dt>
          <dd>{listing.district ?? "—"}</dd>
        </div>
      </dl>
      {listing.score != null && (
        <p className="listing-card__score">
          <strong>Ocena LLM: {listing.score}</strong>
          {listing.reason ? ` — ${listing.reason}` : ""}
        </p>
      )}
    </article>
  );
}
