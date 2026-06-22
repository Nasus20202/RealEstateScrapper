// frontend/src/features/listings/PriceSparkline.tsx
import type { PriceHistoryEntry } from "../../api/types";

export function PriceSparkline({ history }: { history: PriceHistoryEntry[] }) {
  if (history.length < 2) {
    return (
      <table className="price-history">
        <thead>
          <tr>
            <th>Data</th>
            <th>Cena</th>
          </tr>
        </thead>
        <tbody>
          {history.map((entry) => (
            <tr key={entry.observed_at}>
              <td>{entry.observed_at.slice(0, 10)}</td>
              <td>{entry.price.toLocaleString("pl-PL")} zł</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  const width = 240;
  const height = 60;
  const prices = history.map((h) => h.price);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const span = max - min || 1;
  const step = history.length > 1 ? width / (history.length - 1) : width;
  const points = history
    .map((entry, index) => {
      const x = index * step;
      const y = height - ((entry.price - min) / span) * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <svg
      className="price-sparkline"
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={`Historia cen: od ${min.toLocaleString("pl-PL")} do ${max.toLocaleString("pl-PL")} zł`}
    >
      <polyline fill="none" stroke="currentColor" strokeWidth="2" points={points} />
    </svg>
  );
}
