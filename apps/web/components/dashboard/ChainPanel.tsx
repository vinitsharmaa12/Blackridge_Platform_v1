import { ChartSkeleton } from "@/components/dashboard/charts/ChartSkeleton";
import { OptionChainTable } from "@/components/dashboard/OptionChainTable";
import { SectionError } from "@/components/dashboard/SectionError";
import type { ChainRow } from "@/lib/api-types";

type ChainPanelProps = {
  chain: ChainRow[];
  atmStrike: number | null | undefined;
  loading: boolean;
  errorMessage: string | null;
  onRetry: () => void;
};

export function ChainPanel({
  chain,
  atmStrike,
  loading,
  errorMessage,
  onRetry,
}: ChainPanelProps) {
  if (loading) {
    return <ChartSkeleton />;
  }

  if (errorMessage) {
    return <SectionError message={errorMessage} onRetry={onRetry} />;
  }

  return <OptionChainTable chain={chain} atmStrike={atmStrike} />;
}
