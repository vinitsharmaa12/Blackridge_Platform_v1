"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useGenerateInsight, useInsights } from "@/hooks/useInsights";
import type { Insight } from "@/lib/api-types";
import { formatSnapshotTime } from "@/lib/format";

function InsightCard({ insight }: { insight: Insight }) {
  return (
    <Card size="sm" className="shadow-none">
      <CardContent className="flex flex-col gap-1 pt-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <p className="text-xs font-medium">{insight.title}</p>
          <time className="text-[10px] text-muted-foreground">
            {formatSnapshotTime(insight.time)}
          </time>
        </div>
        <p className="text-xs leading-snug text-foreground/90">
          {insight.narrative}
        </p>
        <div className="flex flex-wrap gap-2 text-[10px] text-muted-foreground">
          {insight.sentiment_label ? (
            <span>Sentiment: {insight.sentiment_label}</span>
          ) : null}
          {insight.confidence != null ? (
            <span>Confidence: {insight.confidence.toFixed(2)}</span>
          ) : null}
          {insight.user_id ? <span>Personal</span> : <span>System</span>}
        </div>
      </CardContent>
    </Card>
  );
}

type InsightsPanelProps = {
  symbol: string;
};

export function InsightsPanel({ symbol }: InsightsPanelProps) {
  const insightsQuery = useInsights(symbol);
  const generateMutation = useGenerateInsight(symbol);

  const insights = insightsQuery.data ?? [];

  return (
    <section className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-medium">AI insights</p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-7 shrink-0 text-xs"
          disabled={generateMutation.isPending}
          onClick={() => generateMutation.mutate()}
        >
          {generateMutation.isPending ? "Queuing…" : "Generate"}
        </Button>
      </div>

      {generateMutation.isSuccess ? (
        <p className="text-[10px] text-muted-foreground">
          Queued job {generateMutation.data.job_id} ({generateMutation.data.status})
        </p>
      ) : null}
      {generateMutation.isError ? (
        <p className="text-[10px] text-destructive">
          Failed to queue insight generation.
        </p>
      ) : null}
      {insightsQuery.isLoading ? (
        <p className="text-xs text-muted-foreground">Loading insights…</p>
      ) : null}
      {insightsQuery.isError ? (
        <p className="text-xs text-destructive">Could not load insights.</p>
      ) : null}
      {!insightsQuery.isLoading && insights.length === 0 ? (
        <p className="text-xs text-muted-foreground">No insights yet.</p>
      ) : null}
      <div className="flex flex-col gap-1.5">
        {insights.map((insight) => (
          <InsightCard key={insight.id} insight={insight} />
        ))}
      </div>
    </section>
  );
}
