"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { ChainRow } from "@/lib/api-types";
import { strikesNearAtm } from "@/lib/chart-utils";
import { formatNumber } from "@/lib/format";

import { ChartSkeleton } from "./ChartSkeleton";

type OiByStrikeChartProps = {
  chain: ChainRow[];
  atmStrike: number | null | undefined;
};

export function OiByStrikeChart({ chain, atmStrike }: OiByStrikeChartProps) {
  const subset = strikesNearAtm(chain, atmStrike);
  const data = subset.map((row) => ({
    strike: row.strike,
    ce_oi: row.ce_oi ?? 0,
    pe_oi: row.pe_oi ?? 0,
  }));

  if (!data.length) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No chain OI data.
      </p>
    );
  }

  return (
    <div className="h-full w-full">
      <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
        <XAxis
          dataKey="strike"
          tick={{ fontSize: 11 }}
          interval="preserveStartEnd"
        />
        <YAxis tick={{ fontSize: 11 }} width={48} />
        <Tooltip
          formatter={(value) =>
            typeof value === "number"
              ? formatNumber(value, { decimals: 0 })
              : "—"
          }
        />
        <Legend />
        {atmStrike != null ? (
          <ReferenceLine
            x={atmStrike}
            stroke="#737373"
            strokeDasharray="4 4"
            label={{ value: "ATM", position: "top", fontSize: 11 }}
          />
        ) : null}
        <Bar dataKey="ce_oi" name="CE OI" fill="#404040" maxBarSize={12} />
        <Bar dataKey="pe_oi" name="PE OI" fill="#a3a3a3" maxBarSize={12} />
      </BarChart>
    </ResponsiveContainer>
    </div>
  );
}

export function OiByStrikeChartLoader(props: OiByStrikeChartProps) {
  if (!props.chain.length) {
    return <ChartSkeleton />;
  }
  return <OiByStrikeChart {...props} />;
}
