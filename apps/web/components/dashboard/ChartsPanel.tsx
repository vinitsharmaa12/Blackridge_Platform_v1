"use client";

import type { ReactNode } from "react";

import { ChartSection } from "@/components/dashboard/ChartSection";
import { IvSkewChartLoader } from "@/components/dashboard/charts/IvSkewChart";
import { OiByStrikeChartLoader } from "@/components/dashboard/charts/OiByStrikeChart";
import { PcrSentimentChartLoader } from "@/components/dashboard/charts/PcrSentimentChart";
import { PriceLevelsChartLoader } from "@/components/dashboard/charts/PriceLevelsChart";
import type { ChainRow, MetricsRow } from "@/lib/api-types";
import { formatNumber } from "@/lib/format";

type ChartsPanelProps = {
  metricsSeries: MetricsRow[];
  metricsRow: MetricsRow;
  chain: ChainRow[];
  chainSection: ReactNode;
};

function ivMeta(metricsRow: MetricsRow): string | undefined {
  const { atm_iv: atmIv, iv_skew: ivSkew } = metricsRow;
  if (atmIv != null && ivSkew != null) {
    return `ATM IV ${formatNumber(atmIv, { decimals: 2 })} · skew ${formatNumber(ivSkew, { decimals: 2 })}`;
  }
  return undefined;
}

export function ChartsPanel({
  metricsSeries,
  metricsRow,
  chain,
  chainSection,
}: ChartsPanelProps) {
  return (
    <div className="grid min-h-0 grid-cols-1 grid-rows-[minmax(150px,1fr)_minmax(160px,1fr)_minmax(160px,1fr)_minmax(180px,1fr)] gap-2 lg:grid-cols-2 lg:grid-rows-[minmax(150px,1fr)_minmax(150px,1fr)_minmax(180px,1fr)]">
      <ChartSection title="Price & levels" compact className="lg:col-span-2">
        <div
          className="h-full min-h-[150px]"
          aria-label="Underlying price chart with support and resistance levels"
        >
          <PriceLevelsChartLoader series={metricsSeries} levels={metricsRow} />
        </div>
      </ChartSection>

      <ChartSection title="OI by strike" compact>
        <div
          className="h-full min-h-[160px]"
          aria-label="Open interest by strike chart"
        >
          {chainSection ?? (
            <OiByStrikeChartLoader chain={chain} atmStrike={metricsRow.atm_strike} />
          )}
        </div>
      </ChartSection>

      <ChartSection title="PCR & sentiment" compact>
        <div
          className="h-full min-h-[160px]"
          aria-label="PCR and sentiment trend chart"
        >
          <PcrSentimentChartLoader series={metricsSeries} />
        </div>
      </ChartSection>

      <ChartSection
        title="IV by strike"
        compact
        className="lg:col-span-2"
        meta={ivMeta(metricsRow)}
      >
        <div
          className="h-full min-h-[180px]"
          aria-label="Implied volatility by strike chart"
        >
          {chainSection ?? (
            <IvSkewChartLoader chain={chain} atmStrike={metricsRow.atm_strike} />
          )}
        </div>
      </ChartSection>
    </div>
  );
}
