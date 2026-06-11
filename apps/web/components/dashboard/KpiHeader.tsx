import type { ReactNode } from "react";

import { Card, CardContent } from "@/components/ui/card";
import type { MetricsRow } from "@/lib/api-types";
import { formatNumber, formatSignedChange } from "@/lib/format";

type KpiHeaderProps = {
  metrics: MetricsRow;
  dayChange: number | null;
  variant?: "strip" | "grid";
};

type KpiItemProps = {
  label: string;
  value: string;
  hint?: string | null;
};

function KpiItem({ label, value, hint }: KpiItemProps) {
  return (
    <Card className="shadow-none">
      <CardContent className="flex flex-col gap-0.5 pt-4">
        <span className="text-xs text-muted-foreground">{label}</span>
        <span className="font-mono text-lg tabular-nums">{value}</span>
        {hint ? (
          <span className="text-xs text-muted-foreground">{hint}</span>
        ) : null}
      </CardContent>
    </Card>
  );
}

type StripItemProps = {
  label: string;
  value: string;
  hint?: string | null;
  children?: ReactNode;
};

function StripItem({ label, value, hint, children }: StripItemProps) {
  return (
    <div className="flex min-w-0 flex-1 flex-col gap-0.5 px-3 first:pl-0 last:pr-0">
      <span className="truncate text-[10px] text-muted-foreground">{label}</span>
      {children ?? (
        <span className="truncate font-mono text-sm tabular-nums">{value}</span>
      )}
      {hint ? (
        <span className="truncate text-[10px] text-muted-foreground">{hint}</span>
      ) : null}
    </div>
  );
}

function sentimentBarWidth(score: number | null | undefined): number {
  if (score == null) {
    return 0;
  }
  return Math.min(Math.abs(score), 100);
}

function KpiStrip({ metrics, dayChange }: Omit<KpiHeaderProps, "variant">) {
  const changeText = formatSignedChange(dayChange);
  const underlyingHint =
    changeText != null ? `${changeText} today` : undefined;

  const sentimentScore = metrics.sentiment_score;
  const barWidth = sentimentBarWidth(sentimentScore);

  return (
    <div className="flex min-w-0 flex-1 divide-x divide-border overflow-x-auto">
      <StripItem
        label="Underlying"
        value={formatNumber(metrics.underlying, { decimals: 2 })}
        hint={underlyingHint}
      />
      <StripItem label="Sentiment" value="">
        <span className="truncate text-sm">
          {metrics.sentiment_label ?? "—"}
          {sentimentScore != null ? (
            <span className="ml-1 font-mono text-xs text-muted-foreground">
              ({sentimentScore})
            </span>
          ) : null}
        </span>
        <div className="h-1 w-full rounded-full bg-muted">
          <div
            className={`h-full rounded-full ${
              sentimentScore != null && sentimentScore < 0
                ? "bg-destructive"
                : "bg-foreground/70"
            }`}
            style={{ width: `${barWidth}%` }}
          />
        </div>
      </StripItem>
      <StripItem
        label="PCR (OI)"
        value={formatNumber(metrics.pcr_oi, { decimals: 2 })}
      />
      <StripItem
        label="PCR (Vol)"
        value={formatNumber(metrics.pcr_volume, { decimals: 2 })}
      />
      <StripItem
        label="Max pain"
        value={formatNumber(metrics.max_pain, { decimals: 0 })}
      />
      <StripItem
        label="Expected move"
        value={formatNumber(metrics.expected_move, { decimals: 0 })}
        hint={metrics.dte != null ? `DTE ${metrics.dte}` : undefined}
      />
    </div>
  );
}

function KpiGrid({ metrics, dayChange }: Omit<KpiHeaderProps, "variant">) {
  const changeText = formatSignedChange(dayChange);
  const underlyingHint =
    changeText != null ? `${changeText} today` : undefined;

  const sentimentScore = metrics.sentiment_score;
  const barWidth = sentimentBarWidth(sentimentScore);

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
      <KpiItem
        label="Underlying"
        value={formatNumber(metrics.underlying, { decimals: 2 })}
        hint={underlyingHint}
      />
      <Card className="shadow-none">
        <CardContent className="flex flex-col gap-2 pt-4">
          <span className="text-xs text-muted-foreground">Sentiment</span>
          <span className="text-sm">
            {metrics.sentiment_label ?? "—"}
            {sentimentScore != null ? (
              <span className="ml-1 font-mono text-muted-foreground">
                ({sentimentScore})
              </span>
            ) : null}
          </span>
          <div className="h-1.5 w-full rounded-full bg-muted">
            <div
              className={`h-full rounded-full ${
                sentimentScore != null && sentimentScore < 0
                  ? "bg-destructive"
                  : "bg-foreground/70"
              }`}
              style={{ width: `${barWidth}%` }}
            />
          </div>
        </CardContent>
      </Card>
      <KpiItem
        label="PCR (OI)"
        value={formatNumber(metrics.pcr_oi, { decimals: 2 })}
      />
      <KpiItem
        label="PCR (Vol)"
        value={formatNumber(metrics.pcr_volume, { decimals: 2 })}
      />
      <KpiItem
        label="Max pain"
        value={formatNumber(metrics.max_pain, { decimals: 0 })}
      />
      <KpiItem
        label="Expected move"
        value={formatNumber(metrics.expected_move, { decimals: 0 })}
        hint={metrics.dte != null ? `DTE ${metrics.dte}` : undefined}
      />
    </div>
  );
}

export function KpiHeader({
  metrics,
  dayChange,
  variant = "strip",
}: KpiHeaderProps) {
  if (variant === "grid") {
    return <KpiGrid metrics={metrics} dayChange={dayChange} />;
  }
  return <KpiStrip metrics={metrics} dayChange={dayChange} />;
}
