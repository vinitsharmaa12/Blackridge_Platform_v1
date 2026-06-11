"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
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

type IvSkewChartProps = {
  chain: ChainRow[];
  atmStrike: number | null | undefined;
};

export function IvSkewChart({ chain, atmStrike }: IvSkewChartProps) {
  const subset = strikesNearAtm(chain, atmStrike);
  const data = subset
    .map((row) => ({
      strike: row.strike,
      ce_iv: row.ce_iv ?? null,
      pe_iv: row.pe_iv ?? null,
    }))
    .filter((row) => row.ce_iv != null || row.pe_iv != null);

  if (!data.length) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No IV data in chain.
      </p>
    );
  }

  return (
    <div className="h-full w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
          <XAxis
            dataKey="strike"
            tick={{ fontSize: 11 }}
            interval="preserveStartEnd"
          />
          <YAxis tick={{ fontSize: 11 }} width={40} />
          <Tooltip
            formatter={(value) =>
              typeof value === "number"
                ? formatNumber(value, { decimals: 2 })
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
          <Line
            type="monotone"
            dataKey="ce_iv"
            name="CE IV"
            stroke="#404040"
            dot={false}
            strokeWidth={2}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="pe_iv"
            name="PE IV"
            stroke="#a3a3a3"
            dot={false}
            strokeWidth={2}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function IvSkewChartLoader(props: IvSkewChartProps) {
  if (!props.chain.length) {
    return <ChartSkeleton />;
  }
  return <IvSkewChart {...props} />;
}
