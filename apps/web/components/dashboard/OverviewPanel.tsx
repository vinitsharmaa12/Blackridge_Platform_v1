"use client";

import type { ReactNode } from "react";

import { ChartsPanel } from "@/components/dashboard/ChartsPanel";
import { SessionSnapshotsPanel } from "@/components/dashboard/SessionSnapshotsPanel";
import { SignalsRail } from "@/components/dashboard/SignalsRail";
import type {
  ChainRow,
  MetricsRow,
  SessionSnapshotsResponse,
  SignalCard,
} from "@/lib/api-types";

type OverviewPanelProps = {
  metricsSeries: MetricsRow[];
  metricsRow: MetricsRow;
  chain: ChainRow[];
  chainSection: ReactNode;
  overall: SignalCard;
  signals: SignalCard[];
  sessionSnapshots: SessionSnapshotsResponse | undefined;
  sessionSnapshotsLoading: boolean;
  sessionSnapshotsError: string | null;
  sessionDate: string | undefined;
  onSessionDateChange: (date: string | undefined) => void;
};

export function OverviewPanel({
  metricsSeries,
  metricsRow,
  chain,
  chainSection,
  overall,
  signals,
  sessionSnapshots,
  sessionSnapshotsLoading,
  sessionSnapshotsError,
  sessionDate,
  onSessionDateChange,
}: OverviewPanelProps) {
  return (
    <div className="flex h-full min-h-0 gap-2">
      <div className="min-h-0 min-w-0 flex-1 overflow-y-auto">
        <div className="space-y-3 pb-3">
          <SessionSnapshotsPanel
            data={sessionSnapshots}
            isLoading={sessionSnapshotsLoading}
            error={sessionSnapshotsError}
            sessionDate={sessionDate}
            onSessionDateChange={onSessionDateChange}
          />
          <ChartsPanel
            metricsSeries={metricsSeries}
            metricsRow={metricsRow}
            chain={chain}
            chainSection={chainSection}
          />
        </div>
      </div>
      <SignalsRail overall={overall} signals={signals} />
    </div>
  );
}
