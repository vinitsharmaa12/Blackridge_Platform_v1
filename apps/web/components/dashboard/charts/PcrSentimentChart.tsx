"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { MetricsRow } from "@/lib/api-types";
import { metricsTrendPoints } from "@/lib/chart-utils";
import { formatNumber } from "@/lib/format";

type PcrSentimentChartProps = {
  series: MetricsRow[];
};

export function PcrSentimentChart({ series }: PcrSentimentChartProps) {
  const data = metricsTrendPoints(series);

  if (!data.length) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No trend data in range.
      </p>
    );
  }

  return (
    <div className="h-full w-full">
      <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
        <XAxis dataKey="label" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
        <YAxis
          yAxisId="pcr"
          tick={{ fontSize: 11 }}
          width={40}
          domain={["auto", "auto"]}
        />
        <YAxis
          yAxisId="sentiment"
          orientation="right"
          tick={{ fontSize: 11 }}
          width={40}
          domain={[-100, 100]}
        />
        <Tooltip
          formatter={(value) =>
            typeof value === "number"
              ? formatNumber(value, { decimals: 2 })
              : "—"
          }
        />
        <Legend />
        <Line
          yAxisId="pcr"
          type="monotone"
          dataKey="pcr_oi"
          name="PCR (OI)"
          stroke="#404040"
          dot={false}
          strokeWidth={2}
          connectNulls
        />
        <Line
          yAxisId="sentiment"
          type="monotone"
          dataKey="sentiment_score"
          name="Sentiment"
          stroke="#737373"
          dot={false}
          strokeWidth={2}
          connectNulls
        />
      </LineChart>
    </ResponsiveContainer>
    </div>
  );
}

export function PcrSentimentChartLoader(props: PcrSentimentChartProps) {
  return <PcrSentimentChart {...props} />;
}
