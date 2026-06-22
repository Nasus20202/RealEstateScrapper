// frontend/src/features/listings/ListingCard.tsx
import { Link } from "react-router-dom";

import type { ListingOut } from "../../api/types";
import { formatPrice, formatPricePerM2 } from "./format";

type ListingCardVariant = "default" | "compact" | "list";

function locationLine(listing: ListingOut): string {
  return [listing.street, listing.district, listing.city].filter(Boolean).join(", ") || "—";
}

function textFromHtml(html: string): string {
  return html
    .replace(/<[^>]*>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
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
  variant = "default",
}: {
  listing: ListingOut;
  onPreview?: (listing: ListingOut) => void;
  variant?: ListingCardVariant;
}) {
  const cover = listing.images[0];
  const detailUrl = `/listings/${listing.id}`;
  const isList = variant === "list";
  const description = listing.description ? textFromHtml(listing.description) : "";

  function openDetail(target: "_self" | "_blank") {
    if (target === "_self") {
      window.location.href = detailUrl;
      return;
    }
    window.open(detailUrl, target, target === "_blank" ? "noopener" : undefined);
  }

  return (
    <article
      className={`listing-card listing-card--${variant}`}
      onClick={() => onPreview?.(listing)}
      onDoubleClick={(event) => {
        event.preventDefault();
        openDetail("_self");
      }}
      onMouseDown={(event) => {
        if (event.button === 1) {
          event.preventDefault();
          event.stopPropagation();
          openDetail("_blank");
        }
      }}
      onAuxClick={(event) => {
        if (event.button === 1) {
          event.preventDefault();
          event.stopPropagation();
        }
      }}
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
            {listing.price_per_m2 != null ? formatPricePerM2(listing.price_per_m2) : ""}
          </span>
        </div>

        <h3 className="listing-card__title">{listing.title}</h3>

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
          {listing.total_floors != null && (
            <span className="chip">z {listing.total_floors} pięter</span>
          )}
        </div>

        {isList && (
          <>
            <dl className="listing-card__details">
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
                <dt>Rynek</dt>
                <dd>{listing.market === "primary" ? "pierwotny" : (listing.market ?? "—")}</dd>
              </div>
            </dl>
            <p className="listing-card__description">{description || "Brak opisu w ogłoszeniu."}</p>
          </>
        )}

        {listing.score != null && (
          <p className="listing-card__score">
            <strong>Ocena LLM: {listing.score}</strong>
            {listing.reason ? ` — ${listing.reason}` : ""}
          </p>
        )}

        <Link
          className="listing-card__details-link"
          to={detailUrl}
          onClick={(event) => event.stopPropagation()}
        >
          Szczegóły
        </Link>
      </div>
    </article>
  );
}
