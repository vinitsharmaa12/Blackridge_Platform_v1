"use client";

import type { ChainRow } from "@/lib/api-types";
import { oiHeatAlpha } from "@/lib/chart-utils";
import { formatNumber } from "@/lib/format";

type OptionChainTableProps = {
  chain: ChainRow[];
  atmStrike: number | null | undefined;
};

function OiCell({
  value,
  max,
}: {
  value: number | null | undefined;
  max: number;
}) {
  const n = value ?? 0;
  const alpha = oiHeatAlpha(n, max);
  return (
    <td
      className="px-2 py-1 font-mono tabular-nums text-right text-xs"
      style={
        alpha > 0
          ? { backgroundColor: `rgba(0, 0, 0, ${alpha})` }
          : undefined
      }
    >
      {formatNumber(n, { decimals: 0 })}
    </td>
  );
}

export function OptionChainTable({ chain, atmStrike }: OptionChainTableProps) {
  const rows = [...chain].sort((a, b) => a.strike - b.strike);

  if (!rows.length) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No option chain rows for this snapshot.
      </p>
    );
  }

  const maxCeOi = Math.max(...rows.map((r) => r.ce_oi ?? 0), 0);
  const maxPeOi = Math.max(...rows.map((r) => r.pe_oi ?? 0), 0);

  return (
    <div className="overflow-auto rounded-md border border-border">
      <table className="w-full min-w-[640px] border-collapse text-left">
        <thead className="sticky top-0 z-10 bg-muted/80 text-xs text-muted-foreground">
          <tr className="border-b border-border">
            <th className="px-2 py-2">Strike</th>
            <th className="px-2 py-2 text-right">CE OI</th>
            <th className="px-2 py-2 text-right">CE ΔOI</th>
            <th className="px-2 py-2 text-right">CE IV</th>
            <th className="px-2 py-2 text-right">CE LTP</th>
            <th className="px-2 py-2 text-right">PE OI</th>
            <th className="px-2 py-2 text-right">PE ΔOI</th>
            <th className="px-2 py-2 text-right">PE IV</th>
            <th className="px-2 py-2 text-right">PE LTP</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const isAtm =
              atmStrike != null && Math.abs(row.strike - atmStrike) < 0.01;
            return (
              <tr
                key={row.strike}
                className={`border-b border-border/60 text-sm ${
                  isAtm ? "bg-muted/50 font-medium" : ""
                }`}
              >
                <td className="px-2 py-1 font-mono tabular-nums">
                  {formatNumber(row.strike, { decimals: 0 })}
                </td>
                <OiCell value={row.ce_oi} max={maxCeOi} />
                <td className="px-2 py-1 text-right font-mono text-xs tabular-nums">
                  {formatNumber(row.ce_oi_change, { decimals: 0 })}
                </td>
                <td className="px-2 py-1 text-right font-mono text-xs tabular-nums">
                  {formatNumber(row.ce_iv, { decimals: 2 })}
                </td>
                <td className="px-2 py-1 text-right font-mono text-xs tabular-nums">
                  {formatNumber(row.ce_ltp, { decimals: 2 })}
                </td>
                <OiCell value={row.pe_oi} max={maxPeOi} />
                <td className="px-2 py-1 text-right font-mono text-xs tabular-nums">
                  {formatNumber(row.pe_oi_change, { decimals: 0 })}
                </td>
                <td className="px-2 py-1 text-right font-mono text-xs tabular-nums">
                  {formatNumber(row.pe_iv, { decimals: 2 })}
                </td>
                <td className="px-2 py-1 text-right font-mono text-xs tabular-nums">
                  {formatNumber(row.pe_ltp, { decimals: 2 })}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
