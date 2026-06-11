"use client";

import type { ReactNode } from "react";

import { ChartsPanel } from "@/components/dashboard/ChartsPanel";
import { SignalsRail } from "@/components/dashboard/SignalsRail";
import type { ChainRow, MetricsRow, SignalCard } from "@/lib/api-types";

type OverviewPanelProps = {
  metricsSeries: MetricsRow[];
  metricsRow: MetricsRow;
  chain: ChainRow[];
  chainSection: ReactNode;
  overall: SignalCard;
  signals: SignalCard[];
};

export function OverviewPanel({
  metricsSeries,
  metricsRow,
  chain,
  chainSection,
  overall,
  signals,
}: OverviewPanelProps) {
  return (
    <div className="flex h-full min-h-0 gap-2">
      <div className="min-h-0 min-w-0 flex-1 overflow-y-auto">
        <ChartsPanel
          metricsSeries={metricsSeries}
          metricsRow={metricsRow}
          chain={chain}
          chainSection={chainSection}
        />
      </div>
      <SignalsRail overall={overall} signals={signals} />
    </div>
  );
}
