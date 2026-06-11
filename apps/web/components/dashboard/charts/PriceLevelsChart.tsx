"use client";

import { useMemo } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { MetricsRow } from "@/lib/api-types";
import { formatNumber, formatSnapshotTime } from "@/lib/format";

import { ChartSkeleton } from "./ChartSkeleton";

type LevelLine = {
  price: number;
  title: string;
  color: string;
};

type PriceLevelsChartProps = {
  series: MetricsRow[];
  levels: MetricsRow;
};

function levelLines(levels: MetricsRow): LevelLine[] {
  const items: LevelLine[] = [];
  if (levels.immediate_support != null) {
    items.push({
      price: levels.immediate_support,
      title: "Imm sup",
      color: "#16a34a",
    });
  }
  if (levels.major_support != null) {
    items.push({
      price: levels.major_support,
      title: "Maj sup",
      color: "#15803d",
    });
  }
  if (levels.immediate_resistance != null) {
    items.push({
      price: levels.immediate_resistance,
      title: "Imm res",
      color: "#dc2626",
    });
  }
  if (levels.major_resistance != null) {
    items.push({
      price: levels.major_resistance,
      title: "Maj res",
      color: "#b91c1c",
    });
  }
  return items;
}

function yDomain(
  prices: number[],
  levelPrices: number[],
): [number, number] | ["auto", "auto"] {
  const all = [...prices, ...levelPrices];
  if (!all.length) {
    return ["auto", "auto"];
  }
  const min = Math.min(...all);
  const max = Math.max(...all);
  const pad = Math.max((max - min) * 0.08, 10);
  return [min - pad, max + pad];
}

export function PriceLevelsChart({ series, levels }: PriceLevelsChartProps) {
  const data = useMemo(
    () =>
      series
        .filter((row) => row.underlying != null)
        .map((row) => ({
          label: formatSnapshotTime(row.time),
          underlying: row.underlying as number,
        })),
    [series],
  );

  const lines = useMemo(() => levelLines(levels), [levels]);

  const domain = useMemo(
    () =>
      yDomain(
        data.map((d) => d.underlying),
        lines.map((l) => l.price),
      ),
    [data, lines],
  );

  if (!data.length) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No underlying prices in this session.
      </p>
    );
  }

  return (
    <div className="h-full w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 56, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 10 }}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fontSize: 11 }}
            width={48}
            domain={domain}
            tickFormatter={(v) => formatNumber(v, { decimals: 0 })}
          />
          <Tooltip
            formatter={(value) =>
              typeof value === "number"
                ? formatNumber(value, { decimals: 2 })
                : "—"
            }
          />
          {lines.map((level) => (
            <ReferenceLine
              key={level.title}
              y={level.price}
              stroke={level.color}
              strokeDasharray="4 4"
              label={{
                value: level.title,
                position: "right",
                fontSize: 10,
                fill: level.color,
              }}
            />
          ))}
          <Line
            type="monotone"
            dataKey="underlying"
            name="Underlying"
            stroke="#171717"
            dot={false}
            strokeWidth={2}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function PriceLevelsChartLoader(props: PriceLevelsChartProps) {
  if (!props.series.length) {
    return <ChartSkeleton />;
  }
  return <PriceLevelsChart {...props} />;
}
