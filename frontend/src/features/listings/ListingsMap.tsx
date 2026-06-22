// frontend/src/features/listings/ListingsMap.tsx
import { CircleMarker, MapContainer, Popup, TileLayer, Tooltip } from "react-leaflet";
import { Link } from "react-router-dom";

import type { ListingOut } from "../../api/types";

const TRICITY_CENTER: [number, number] = [54.44, 18.57];

function formatPrice(value: number | null): string {
  return value == null ? "—" : `${value.toLocaleString("pl-PL")} zł`;
}


function formatPriceShort(value: number | null): string {
  if (value == null) return "—";
  return `${Math.round(value / 1000).toLocaleString("pl-PL")}K`;
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


interface ListingCluster {
  id: string;
  center: [number, number];
  listings: Array<ListingOut & { lat: number; lon: number }>;
}


function clusterListings(
  listings: Array<ListingOut & { lat: number; lon: number }>,
): ListingCluster[] {
  const buckets = new Map<string, Array<ListingOut & { lat: number; lon: number }>>();
  for (const listing of listings) {
    const key = `${Math.round(listing.lat * 200)}:${Math.round(listing.lon * 200)}`;
    buckets.set(key, [...(buckets.get(key) ?? []), listing]);
  }
  return Array.from(buckets.entries()).map(([id, group]) => ({
    id,
    center: averageCenter(group.map((listing) => [listing.lat, listing.lon])),
    listings: group,
  }));
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
  const clusters = clusterListings(located);

  return (
    <div className="listings-map" data-testid="listings-map">
      <MapContainer center={center} zoom={11} scrollWheelZoom>
        <TileLayer
          attribution='&copy; OpenStreetMap contributors &copy; CARTO'
          url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
        />
        {clusters.map((cluster) => {
          const primary = cluster.listings[0];
          const isCluster = cluster.listings.length > 1;
          return (
          <CircleMarker
            key={cluster.id}
            center={cluster.center}
            radius={isCluster ? 12 : 8}
            pathOptions={{
              color: "#0f766e",
              fillColor: isCluster ? "#f59e0b" : "#14b8a6",
              fillOpacity: 0.9,
              weight: 2,
            }}
          >
            <Tooltip permanent direction="top" offset={[0, -8]} opacity={0.95} className="map-price-label">
              {isCluster ? `${cluster.listings.length} ofert` : formatPriceShort(primary.price)}
            </Tooltip>
            <Popup>
              <div className="map-popup">
                {isCluster ? (
                  <>
                    <div className="map-popup__price">{cluster.listings.length} ofert w okolicy</div>
                    <div className="map-popup__list">
                      {cluster.listings.slice(0, 8).map((listing) => (
                        <Link key={listing.id} to={`/listings/${listing.id}`}>
                          {formatPriceShort(listing.price)} · {listing.title}
                        </Link>
                      ))}
                    </div>
                  </>
                ) : (
                  <>
                    {primary.images[0] && <img className="map-popup__image" src={primary.images[0]} alt="" />}
                    <div className="map-popup__price">{formatPrice(primary.price)}</div>
                    {primary.price_per_m2 != null && (
                      <div className="map-popup__muted">{primary.price_per_m2.toLocaleString("pl-PL")} zł/m²</div>
                    )}
                    {facts(primary) && <div className="map-popup__facts">{facts(primary)}</div>}
                    <Link className="map-popup__title" to={`/listings/${primary.id}`}>
                      {primary.title}
                    </Link>
                    <div className="map-popup__muted">{[primary.street, primary.district, primary.city].filter(Boolean).join(", ") || "—"}</div>
                    <Link className="map-popup__button" to={`/listings/${primary.id}`}>Szczegóły</Link>
                  </>
                )}
              </div>
            </Popup>
          </CircleMarker>
        );
        })}
      </MapContainer>
    </div>
  );
}
