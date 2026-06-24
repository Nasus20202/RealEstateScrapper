// frontend/src/features/listings/ListingsMap.tsx
import { useEffect, useMemo, useState } from "react";
import L from "leaflet";
import "leaflet.heat";
import { CircleMarker, MapContainer, Popup, TileLayer, Tooltip } from "react-leaflet";
import { useMap, useMapEvents } from "react-leaflet";
import { Link } from "react-router-dom";

import type { ListingOut, MapHexOut } from "../../api/types";
import { formatNumber } from "./format";

const TRICITY_CENTER: [number, number] = [54.44, 18.57];

export type MapMetric = "price" | "count" | "heat_price" | "heat_count";
export interface MapViewport {
  north: number;
  south: number;
  east: number;
  west: number;
  zoom: number;
}

function numeric(value: number | string | null | undefined): number | null {
  if (value == null || value === "") return null;
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatPrice(value: number | string | null): string {
  const parsed = numeric(value);
  return parsed == null ? "—" : `${formatNumber(parsed)} zł`;
}

function formatPriceShort(value: number | string | null): string {
  const parsed = numeric(value);
  if (parsed == null) return "—";
  return `${formatNumber(Math.round(parsed / 1000))}K`;
}

function formatPricePerM2Short(value: number | string | null): string {
  const parsed = numeric(value);
  if (parsed == null) return "—";
  return `${formatNumber(parsed)} zł/m²`;
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
  ]
    .filter(Boolean)
    .join(" · ");
}

interface ListingCluster {
  id: string;
  center: [number, number];
  listings: Array<ListingOut & { lat: number; lon: number }>;
}

type HeatPoint = [number, number, number];

function clusterListings(
  listings: Array<ListingOut & { lat: number; lon: number }>,
  zoom: number,
): ListingCluster[] {
  const buckets = new Map<string, Array<ListingOut & { lat: number; lon: number }>>();
  if (zoom >= 16) {
    return listings.map((listing) => ({
      id: String(listing.id),
      center: [listing.lat, listing.lon],
      listings: [listing],
    }));
  }
  const precision = Math.max(120, 65 * 2 ** Math.max(0, zoom - 8));
  for (const listing of listings) {
    const key = `${Math.round(listing.lat * precision)}:${Math.round(listing.lon * precision)}`;
    buckets.set(key, [...(buckets.get(key) ?? []), listing]);
  }
  return Array.from(buckets.entries()).map(([id, group]) => ({
    id,
    center: averageCenter(group.map((listing) => [listing.lat, listing.lon])),
    listings: group,
  }));
}

function ZoomWatcher({ onZoom }: { onZoom: (zoom: number) => void }) {
  useMapEvents({
    zoomend: (event) => onZoom(event.target.getZoom()),
  });
  return null;
}

function ViewportWatcher({ onViewport }: { onViewport?: (viewport: MapViewport) => void }) {
  const map = useMapEvents({
    moveend: (event) => emit(event.target),
    zoomend: (event) => emit(event.target),
  });

  function emit(currentMap = map) {
    if (!onViewport) return;
    const bounds = currentMap.getBounds();
    onViewport({
      north: bounds.getNorth(),
      south: bounds.getSouth(),
      east: bounds.getEast(),
      west: bounds.getWest(),
      zoom: currentMap.getZoom(),
    });
  }

  useEffect(() => emit(map));

  return null;
}

function clusterAveragePrice(cluster: ListingCluster): number | null {
  const prices = cluster.listings
    .map((listing) => numeric(listing.price))
    .filter((price): price is number => price != null);
  if (prices.length === 0) return null;
  return prices.reduce((sum, price) => sum + price, 0) / prices.length;
}

function clusterAveragePricePerM2(cluster: ListingCluster): number | null {
  const prices = cluster.listings
    .map((listing) => numeric(listing.price_per_m2))
    .filter((price): price is number => price != null);
  if (prices.length === 0) return null;
  return prices.reduce((sum, price) => sum + price, 0) / prices.length;
}

function markerStyle(cluster: ListingCluster, metric: MapMetric) {
  const avgPrice = clusterAveragePrice(cluster);
  if (metric === "heat_count") {
    const intensity = Math.min(1, cluster.listings.length / 20);
    return {
      radius: 10 + intensity * 24,
      fillColor: intensity > 0.66 ? "#ef4444" : intensity > 0.33 ? "#f59e0b" : "#22c55e",
      fillOpacity: 0.35 + intensity * 0.45,
    };
  }
  if (metric === "heat_price") {
    const avgPricePerM2 = clusterAveragePricePerM2(cluster);
    const trendValue = avgPricePerM2 ?? (avgPrice == null ? null : avgPrice / 80);
    const intensity =
      trendValue == null ? 0.2 : Math.min(1, Math.max(0, (trendValue - 7_000) / 12_000));
    return {
      radius: 16 + intensity * 24,
      fillColor: intensity > 0.66 ? "#dc2626" : intensity > 0.33 ? "#f97316" : "#14b8a6",
      fillOpacity: 0.35 + intensity * 0.45,
    };
  }
  return {
    radius: cluster.listings.length > 1 ? 12 : 8,
    fillColor: cluster.listings.length > 1 ? "#f59e0b" : "#14b8a6",
    fillOpacity: 0.9,
  };
}

function clusterLabel(cluster: ListingCluster, metric: MapMetric): string {
  if (metric === "count" || metric === "heat_count") return `${cluster.listings.length}`;
  if (metric === "heat_price") return formatPricePerM2Short(clusterAveragePricePerM2(cluster));
  const avgPrice = clusterAveragePrice(cluster);
  if (cluster.listings.length > 1)
    return `${formatPriceShort(avgPrice)} · ${cluster.listings.length}`;
  return formatPriceShort(cluster.listings[0].price);
}

function heatIntensity(hex: MapHexOut, metric: MapMetric): number {
  if (metric === "heat_count") return Math.min(1, hex.count / 16);
  const value = numeric(hex.avg_price_per_m2);
  return value == null ? 0.2 : Math.min(1, Math.max(0.08, (value - 7_000) / 12_000));
}

function listingHeatIntensity(listing: ListingOut, metric: MapMetric): number {
  if (metric === "heat_count") return 0.75;
  const pricePerM2 = numeric(listing.price_per_m2);
  const price = numeric(listing.price);
  const area = numeric(listing.area_m2);
  const value = pricePerM2 ?? (price != null && area != null && area > 0 ? price / area : null);
  return value == null ? 0.25 : Math.min(1, Math.max(0.12, (value - 7_000) / 12_000));
}

function hexCenter(hex: MapHexOut): [number, number] {
  const points = hex.geometry.coordinates[0];
  const sum = points.reduce<[number, number]>(
    (acc, [lon, lat]) => [acc[0] + lat, acc[1] + lon],
    [0, 0],
  );
  return [sum[0] / points.length, sum[1] / points.length];
}

function HeatLayer({ points, metric }: { points: HeatPoint[]; metric: MapMetric }) {
  const map = useMap();

  useEffect(() => {
    const layer = L.heatLayer(points, {
      radius: metric === "heat_count" ? 34 : 42,
      blur: metric === "heat_count" ? 26 : 32,
      maxZoom: 17,
      minOpacity: 0.22,
      gradient:
        metric === "heat_count"
          ? { 0.25: "#22c55e", 0.55: "#f59e0b", 1: "#dc2626" }
          : { 0.2: "#14b8a6", 0.55: "#f97316", 1: "#dc2626" },
    });
    layer.addTo(map);
    return () => {
      layer.remove();
    };
  }, [map, metric, points]);

  return null;
}

export function ListingsMap({
  listings,
  metric = "price",
  hexes = [],
  onViewport,
}: {
  listings: ListingOut[];
  metric?: MapMetric;
  hexes?: MapHexOut[];
  onViewport?: (viewport: MapViewport) => void;
}) {
  const [zoom, setZoom] = useState(11);
  const located = useMemo(
    () =>
      listings.filter(
        (l): l is ListingOut & { lat: number; lon: number } => l.lat != null && l.lon != null,
      ),
    [listings],
  );
  const center = useMemo(() => {
    if (located.length > 0) return averageCenter(located.map((l) => [l.lat, l.lon]));
    if (hexes.length > 0) return averageCenter(hexes.map(hexCenter));
    return TRICITY_CENTER;
  }, [hexes, located]);
  const clusters = useMemo(() => clusterListings(located, zoom), [located, zoom]);
  const isHeat = metric === "heat_price" || metric === "heat_count";
  const heatPoints: HeatPoint[] = useMemo(
    () =>
      hexes.length
        ? hexes.map((hex) => {
            const [lat, lon] = hexCenter(hex);
            return [lat, lon, heatIntensity(hex, metric)];
          })
        : located.map((listing) => [
            listing.lat,
            listing.lon,
            listingHeatIntensity(listing, metric),
          ]),
    [hexes, located, metric],
  );

  if (located.length === 0 && hexes.length === 0) {
    return (
      <div className="map-empty">
        Brak ofert ze współrzędnymi do pokazania na mapie. Uruchom scraping z włączonym
        geokodowaniem (GEOCODING_ENABLED), aby zobaczyć pinezki.
      </div>
    );
  }

  return (
    <div className="listings-map" data-testid="listings-map">
      <MapContainer center={center} zoom={11} scrollWheelZoom>
        <ZoomWatcher onZoom={setZoom} />
        <ViewportWatcher onViewport={onViewport} />
        <TileLayer
          attribution="&copy; OpenStreetMap contributors &copy; CARTO"
          url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
        />
        {isHeat && heatPoints.length > 0 && <HeatLayer points={heatPoints} metric={metric} />}
        {isHeat && hexes.length > 0
          ? hexes.map((hex) => {
              const center = hexCenter(hex);
              return (
                <CircleMarker
                  key={hex.id}
                  center={center}
                  radius={4}
                  pathOptions={{
                    color: "transparent",
                    fillColor: "transparent",
                    fillOpacity: 0,
                    opacity: 0,
                    weight: 0,
                  }}
                >
                  <Tooltip sticky>
                    {metric === "heat_price"
                      ? `${formatPricePerM2Short(hex.avg_price_per_m2)} · ${hex.count} ofert`
                      : `${hex.count} ofert`}
                  </Tooltip>
                  <Popup>
                    <div className="map-popup">
                      <div className="map-popup__price">
                        {metric === "heat_price"
                          ? formatPricePerM2Short(hex.avg_price_per_m2)
                          : `${hex.count} ofert`}
                      </div>
                      <div className="map-popup__muted">
                        {hex.avg_price == null
                          ? ""
                          : `średnia cena ${formatPriceShort(hex.avg_price)}`}
                      </div>
                    </div>
                  </Popup>
                </CircleMarker>
              );
            })
          : null}
        {!isHeat &&
          clusters.map((cluster) => {
            const primary = cluster.listings[0];
            const isCluster = cluster.listings.length > 1;
            const style = markerStyle(cluster, metric);
            return (
              <CircleMarker
                key={cluster.id}
                center={cluster.center}
                radius={style.radius}
                pathOptions={{
                  color: "#0f766e",
                  fillColor: style.fillColor,
                  fillOpacity: style.fillOpacity,
                  weight: 2,
                }}
              >
                <Tooltip
                  permanent
                  direction="top"
                  offset={[0, -8]}
                  opacity={0.95}
                  className="map-price-label"
                >
                  {clusterLabel(cluster, metric)}
                </Tooltip>
                <Popup>
                  <div className="map-popup">
                    {isCluster ? (
                      <>
                        <div className="map-popup__price">
                          {cluster.listings.length} ofert w okolicy
                        </div>
                        <div className="map-popup__list">
                          {(clusterAveragePrice(cluster) != null ||
                            clusterAveragePricePerM2(cluster) != null) && (
                            <div className="map-popup__muted">
                              {[
                                clusterAveragePrice(cluster) == null
                                  ? null
                                  : `średnia cena ${formatPriceShort(clusterAveragePrice(cluster))}`,
                                clusterAveragePricePerM2(cluster) == null
                                  ? null
                                  : `średnio ${formatPricePerM2Short(clusterAveragePricePerM2(cluster))}`,
                              ]
                                .filter(Boolean)
                                .join(" · ")}
                            </div>
                          )}
                          {cluster.listings.slice(0, 8).map((listing) => (
                            <Link key={listing.id} to={`/listings/${listing.id}`}>
                              {formatPriceShort(listing.price)} · {listing.title}
                            </Link>
                          ))}
                        </div>
                      </>
                    ) : (
                      <>
                        {primary.images[0] && (
                          <img className="map-popup__image" src={primary.images[0]} alt="" />
                        )}
                        <div className="map-popup__price">{formatPrice(primary.price)}</div>
                        {primary.price_per_m2 != null && (
                          <div className="map-popup__muted">
                            {formatNumber(primary.price_per_m2)} zł/m²
                          </div>
                        )}
                        {facts(primary) && <div className="map-popup__facts">{facts(primary)}</div>}
                        <Link className="map-popup__title" to={`/listings/${primary.id}`}>
                          {primary.title}
                        </Link>
                        <div className="map-popup__muted">
                          {[primary.street, primary.district, primary.city]
                            .filter(Boolean)
                            .join(", ") || "—"}
                        </div>
                        <Link className="map-popup__button" to={`/listings/${primary.id}`}>
                          Szczegóły
                        </Link>
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
