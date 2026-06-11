import { CHART_HEIGHT_COMPACT } from "@/lib/chart-constants";

export function ChartSkeleton({
  height = CHART_HEIGHT_COMPACT,
}: {
  height?: number;
}) {
  return (
    <div
      className="w-full animate-pulse rounded-md bg-muted"
      style={{ height }}
      aria-hidden
    />
  );
}
