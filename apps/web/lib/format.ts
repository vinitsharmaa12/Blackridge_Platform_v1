/** Display formatters — no metric math, presentation only. */

export function formatNull(
  value: number | string | null | undefined,
  fallback = "—",
): string {
  if (value == null || value === "") {
    return fallback;
  }
  return String(value);
}

export function formatNumber(
  value: number | null | undefined,
  options?: { decimals?: number; fallback?: string },
): string {
  const fallback = options?.fallback ?? "—";
  if (value == null || Number.isNaN(value)) {
    return fallback;
  }
  const decimals = options?.decimals ?? 2;
  return value.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: decimals,
  });
}

export function formatSignedChange(
  change: number | null | undefined,
): string | null {
  if (change == null || Number.isNaN(change)) {
    return null;
  }
  const sign = change > 0 ? "+" : "";
  return `${sign}${change.toFixed(2)}`;
}

export function formatSnapshotTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
