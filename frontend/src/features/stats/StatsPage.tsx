import { useEffect, useState } from "react";

import { getStats } from "../../api/client";
import type { StatsBucketOut, StatsGroupOut, StatsOut } from "../../api/types";
import { formatNumber, formatPrice, formatPricePerM2 } from "../listings/format";

function percent(value: number, total: number): string {
  if (total === 0) return "0%";
  return `${Math.round((value / total) * 100)}%`;
}

function formatDecimal(value: number | null, suffix = ""): string {
  return value == null ? "—" : `${value.toFixed(1).replace(".0", "")}${suffix}`;
}

function GroupTable({ title, rows }: { title: string; rows: StatsGroupOut[] }) {
  return (
    <section className="stats-card stats-card--wide">
      <h3>{title}</h3>
      <div className="stats-table-wrap">
        <table className="stats-table">
          <thead>
            <tr>
              <th>Nazwa</th>
              <th>Oferty</th>
              <th>Śr. cena</th>
              <th>Śr. cena/m²</th>
              <th>Śr. metraż</th>
              <th>Mapa</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key}>
                <td>{row.key}</td>
                <td>{formatNumber(row.count)}</td>
                <td>{formatPrice(row.avg_price)}</td>
                <td>{formatPricePerM2(row.avg_price_per_m2)}</td>
                <td>{formatDecimal(row.avg_area_m2, " m²")}</td>
                <td>{percent(row.located_count, row.count)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function BucketChart({ title, rows }: { title: string; rows: StatsBucketOut[] }) {
  const max = Math.max(1, ...rows.map((row) => row.count));
  return (
    <section className="stats-card">
      <h3>{title}</h3>
      <div className="stats-bars">
        {rows.map((row) => (
          <div key={row.key} className="stats-bar">
            <div className="stats-bar__label">
              <span>{row.key}</span>
              <strong>{formatNumber(row.count)}</strong>
            </div>
            <div className="stats-bar__track">
              <span style={{ width: `${Math.max(4, (row.count / max) * 100)}%` }} />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export function StatsPage() {
  const [stats, setStats] = useState<StatsOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void getStats()
      .then(setStats)
      .catch((err) => setError(err instanceof Error ? err.message : "Błąd pobierania statystyk"));
  }, []);

  if (error) return <p className="error">{error}</p>;
  if (!stats) return <p className="loading">Ładowanie statystyk…</p>;

  const { overview } = stats;

  return (
    <section className="stats-page">
      <header className="stats-header">
        <div>
          <h2>Statystyki rynku</h2>
          <p>Przekrój aktywnych ofert według lokalizacji, źródeł, cen i kompletności danych.</p>
        </div>
        {overview.latest_seen && (
          <span>Ostatnia obserwacja: {overview.latest_seen.slice(0, 16).replace("T", " ")}</span>
        )}
      </header>

      <div className="stats-kpis">
        <div className="stats-kpi">
          <span>Aktywne oferty</span>
          <strong>{formatNumber(overview.active_count)}</strong>
          <small>łącznie w bazie: {formatNumber(overview.total_count)}</small>
        </div>
        <div className="stats-kpi">
          <span>Średnia cena</span>
          <strong>{formatPrice(overview.avg_price)}</strong>
          <small>
            min/max: {formatPrice(overview.min_price)} / {formatPrice(overview.max_price)}
          </small>
        </div>
        <div className="stats-kpi">
          <span>Średnia cena/m²</span>
          <strong>{formatPricePerM2(overview.avg_price_per_m2)}</strong>
          <small>wycenione: {percent(overview.priced_count, overview.active_count)}</small>
        </div>
        <div className="stats-kpi">
          <span>Kompletność mapy</span>
          <strong>{percent(overview.located_count, overview.active_count)}</strong>
          <small>{formatNumber(overview.located_count)} ofert z koordynatami</small>
        </div>
        <div className="stats-kpi">
          <span>Średni metraż</span>
          <strong>{formatDecimal(overview.avg_area_m2, " m²")}</strong>
          <small>pokoje: {formatDecimal(overview.avg_rooms)}</small>
        </div>
        <div className="stats-kpi">
          <span>Jakość treści</span>
          <strong>{percent(overview.with_description_count, overview.active_count)}</strong>
          <small>zdjęcia: {percent(overview.with_images_count, overview.active_count)}</small>
        </div>
      </div>

      <div className="stats-grid">
        <GroupTable title="Dzielnice" rows={stats.by_district} />
        <GroupTable title="Źródła" rows={stats.by_source} />
        <GroupTable title="Miasta" rows={stats.by_city} />
        <GroupTable title="Rynek" rows={stats.by_market} />
        <BucketChart title="Rozkład pokoi" rows={stats.by_rooms} />
        <BucketChart title="Koszyki cenowe" rows={stats.price_buckets} />
      </div>
    </section>
  );
}
