// frontend/src/features/listings/ListingsMap.tsx
import { CircleMarker, MapContainer, Popup, TileLayer, Tooltip } from "react-leaflet";
import { Link } from "react-router-dom";

import type { ListingOut } from "../../api/types";

const TRICITY_CENTER: [number, number] = [54.44, 18.57];

function formatPrice(value: number | null): string {
  return value == null ? "—" : `${value.toLocaleString("pl-PL")} zł`;
}

function averageCenter(points: [number, number][]): [number, number] {
  if (points.length === 0) return TRICITY_CENTER;
  const sum = points.reduce<[number, number]>(
    (acc, [lat, lon]) => [acc[0] + lat, acc[1] + lon],
    [0, 0],
  );
  return [sum[0] / points.length, sum[1] / points.length];
}


function facts(listing: ListingOut): string {
  return [
    listing.rooms != null ? `${listing.rooms} pok.` : null,
    listing.area_m2 != null ? `${listing.area_m2} m²` : null,
  ].filter(Boolean).join(" · ");
}

export function ListingsMap({ listings }: { listings: ListingOut[] }) {
  const located = listings.filter(
    (l): l is ListingOut & { lat: number; lon: number } =>
      l.lat != null && l.lon != null,
  );

  if (located.length === 0) {
    return (
      <div className="map-empty">
        Brak ofert ze współrzędnymi do pokazania na mapie. Uruchom scraping z
        włączonym geokodowaniem (GEOCODING_ENABLED), aby zobaczyć pinezki.
      </div>
    );
  }

  const center = averageCenter(located.map((l) => [l.lat, l.lon]));

  return (
    <div className="listings-map" data-testid="listings-map">
      <MapContainer center={center} zoom={11} scrollWheelZoom>
        <TileLayer
          attribution='&copy; OpenStreetMap contributors &copy; CARTO'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />
        {located.map((l) => (
          <CircleMarker
            key={l.id}
            center={[l.lat, l.lon]}
            radius={8}
            pathOptions={{
              color: "#2dd4bf",
              fillColor: "#2dd4bf",
              fillOpacity: 0.75,
              weight: 2,
            }}
          >
            <Tooltip permanent direction="top" offset={[0, -8]} opacity={0.95} className="map-price-label">
              {formatPrice(l.price)}
            </Tooltip>
            <Popup>
              <div className="map-popup">
                {l.images[0] && <img className="map-popup__image" src={l.images[0]} alt="" />}
                <div className="map-popup__price">{formatPrice(l.price)}</div>
                {l.price_per_m2 != null && (
                  <div className="map-popup__muted">{l.price_per_m2.toLocaleString("pl-PL")} zł/m²</div>
                )}
                {facts(l) && <div className="map-popup__facts">{facts(l)}</div>}
                <Link className="map-popup__title" to={`/listings/${l.id}`}>
                  {l.title}
                </Link>
                <div className="map-popup__muted">{[l.street, l.district, l.city].filter(Boolean).join(", ") || "—"}</div>
                <Link className="map-popup__button" to={`/listings/${l.id}`}>Szczegóły</Link>
              </div>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
}
