export function formatNumber(value: number): string {
  return Math.round(value)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, " ");
}

export function formatPrice(value: number | null): string {
  return value == null ? "—" : `${formatNumber(value)} zł`;
}

export function formatPricePerM2(value: number | null): string {
  return value == null ? "—" : `${formatNumber(value)} zł/m²`;
}
