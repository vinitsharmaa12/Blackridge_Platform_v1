import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export function DashboardSkeleton() {
  return (
    <div className="flex flex-col gap-4 p-6">
      <div className="h-8 w-48 animate-pulse rounded bg-muted" />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="h-20 animate-pulse rounded-lg bg-muted" />
        ))}
      </div>
      <div className="h-48 animate-pulse rounded-lg bg-muted" />
      <div className="grid gap-3 lg:grid-cols-2">
        <div className="h-64 animate-pulse rounded-lg bg-muted lg:col-span-2" />
        <div className="h-64 animate-pulse rounded-lg bg-muted" />
        <div className="h-64 animate-pulse rounded-lg bg-muted" />
        <div className="h-64 animate-pulse rounded-lg bg-muted lg:col-span-2" />
      </div>
    </div>
  );
}

export function DashboardError({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="p-6">
      <Card>
        <CardContent className="flex flex-col gap-3 pt-6">
          <p className="text-sm text-destructive">{message}</p>
          {onRetry ? (
            <Button type="button" variant="outline" size="sm" onClick={onRetry}>
              Retry
            </Button>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

export function DashboardEmpty({ symbol }: { symbol: string }) {
  return (
    <div className="p-6">
      <Card>
        <CardContent className="pt-6 text-sm text-muted-foreground">
          No market data for {symbol}. The session may be closed or ingestion has
          not run yet.
        </CardContent>
      </Card>
    </div>
  );
}
