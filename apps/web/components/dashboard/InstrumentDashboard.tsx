"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";

import { ChainPanel } from "@/components/dashboard/ChainPanel";
import {
  DashboardTabs,
  type DashboardTab,
} from "@/components/dashboard/DashboardTabs";
import { OverviewPanel } from "@/components/dashboard/OverviewPanel";
import {
  DashboardEmpty,
  DashboardError,
  DashboardSkeleton,
} from "@/components/dashboard/DashboardStates";
import { ErrorToast } from "@/components/dashboard/ErrorToast";
import { InsightsPanel } from "@/components/dashboard/InsightsPanel";
import { KpiHeader } from "@/components/dashboard/KpiHeader";
import { SectionError } from "@/components/dashboard/SectionError";
import { useDashboardHeaderControls } from "@/components/providers/DashboardHeaderProvider";
import { ChartSkeleton } from "@/components/dashboard/charts/ChartSkeleton";
import {
  metricsAtTime,
  useChain,
  useLatest,
  useMetricsSeries,
  useSessionSnapshots,
  useSignals,
} from "@/hooks/useDashboard";
import { useLiveMetrics } from "@/hooks/useLiveMetrics";
import { formatApiError } from "@/lib/errors";
import {
  clampRange,
  defaultTimeRange,
  deriveSessionBounds,
  EMPTY_TIME_RANGE,
  sessionDateFromIso,
  filterMetricsByRange,
  resolveEndAt,
  snapshotTimesFromSeries,
  type TimeRangeSelection,
} from "@/lib/time-range";

type InstrumentDashboardProps = {
  symbol: string;
};

export function InstrumentDashboard({ symbol }: InstrumentDashboardProps) {
  const [timeRange, setTimeRange] = useState<TimeRangeSelection>(EMPTY_TIME_RANGE);
  const [liveEnabled, setLiveEnabled] = useState(false);
  const [dismissedToast, setDismissedToast] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<DashboardTab>("overview");
  const [sessionDateOverride, setSessionDateOverride] = useState<
    string | undefined
  >(undefined);
  const queryClient = useQueryClient();

  const refreshDashboard = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["latest", symbol] });
    queryClient.invalidateQueries({ queryKey: ["metrics", symbol] });
    queryClient.invalidateQueries({ queryKey: ["signals", symbol] });
    queryClient.invalidateQueries({ queryKey: ["chain", symbol] });
    queryClient.invalidateQueries({ queryKey: ["session-snapshots", symbol] });
  }, [queryClient, symbol]);

  const liveStatus = useLiveMetrics(symbol, liveEnabled, () => {
    refreshDashboard();
  });

  useEffect(() => {
    if (!liveEnabled || liveStatus === "live" || liveStatus === "off") {
      return undefined;
    }
    const id = setInterval(() => refreshDashboard(), 5_000);
    return () => clearInterval(id);
  }, [liveEnabled, liveStatus, refreshDashboard]);

  const latestQuery = useLatest(symbol);
  const metricsQuery = useMetricsSeries(symbol);
  const metricsSeries = useMemo(
    () => metricsQuery.data ?? [],
    [metricsQuery.data],
  );

  const sessionBounds = useMemo(
    () => deriveSessionBounds(metricsQuery.data),
    [metricsQuery.data],
  );

  const defaultSessionDate = useMemo(
    () =>
      sessionBounds?.to ? sessionDateFromIso(sessionBounds.to) : undefined,
    [sessionBounds],
  );

  const effectiveSessionDate = sessionDateOverride ?? defaultSessionDate;
  const sessionSnapshotsQuery = useSessionSnapshots(symbol, effectiveSessionDate);

  const snapshotTimes = useMemo(
    () => snapshotTimesFromSeries(metricsQuery.data),
    [metricsQuery.data],
  );

  const resolvedTimeRange = useMemo(() => {
    if (!sessionBounds) {
      return timeRange;
    }
    if (!timeRange.from && !timeRange.to) {
      return defaultTimeRange(sessionBounds);
    }
    if (timeRange.mode === "current") {
      return timeRange;
    }
    const clamped = clampRange(timeRange.from, timeRange.to, sessionBounds);
    const next = { ...timeRange, from: clamped.from, to: clamped.to };
    if (liveEnabled) {
      return { ...next, to: sessionBounds.to };
    }
    return next;
  }, [timeRange, sessionBounds, liveEnabled]);

  const endAt = useMemo(
    () => resolveEndAt(resolvedTimeRange, sessionBounds),
    [resolvedTimeRange, sessionBounds],
  );

  const signalsQuery = useSignals(symbol, endAt);
  const chainQuery = useChain(symbol, endAt);

  const effectiveRange = useMemo(() => {
    if (!sessionBounds) {
      return { from: resolvedTimeRange.from, to: resolvedTimeRange.to };
    }
    if (resolvedTimeRange.mode === "current") {
      return { from: sessionBounds.to, to: sessionBounds.to };
    }
    return clampRange(
      resolvedTimeRange.from,
      resolvedTimeRange.to,
      sessionBounds,
    );
  }, [resolvedTimeRange, sessionBounds]);

  const filteredSeries = useMemo(
    () =>
      filterMetricsByRange(
        metricsSeries,
        effectiveRange.from,
        effectiveRange.to,
      ),
    [metricsSeries, effectiveRange.from, effectiveRange.to],
  );

  const metricsRow = useMemo(() => {
    if (resolvedTimeRange.mode === "current") {
      return latestQuery.data?.metrics;
    }
    const fromSeries = metricsAtTime(metricsQuery.data, effectiveRange.to);
    return fromSeries ?? latestQuery.data?.metrics;
  }, [resolvedTimeRange.mode, latestQuery.data, metricsQuery.data, effectiveRange.to]);

  const onLiveToggle = useCallback(() => {
    setLiveEnabled((v) => !v);
  }, []);

  const onTimeRangeChange = useCallback((range: TimeRangeSelection) => {
    setTimeRange(range);
  }, []);

  const headerControls = useMemo(
    () => ({
      liveEnabled,
      liveStatus,
      onLiveToggle,
      timeRange: resolvedTimeRange,
      snapshotTimes,
      onTimeRangeChange,
      timeRangeDisabled: snapshotTimes.length === 0,
    }),
    [
      liveEnabled,
      liveStatus,
      onLiveToggle,
      resolvedTimeRange,
      snapshotTimes,
      onTimeRangeChange,
    ],
  );

  useDashboardHeaderControls(headerControls);

  const dayOpen = metricsSeries[0]?.underlying ?? null;
  const dayChange =
    metricsRow?.underlying != null && dayOpen != null
      ? metricsRow.underlying - dayOpen
      : null;

  const isLoading =
    latestQuery.isLoading || metricsQuery.isLoading || signalsQuery.isLoading;

  const criticalError =
    latestQuery.error ?? metricsQuery.error ?? signalsQuery.error ?? null;

  const retryAll = () => {
    latestQuery.refetch();
    metricsQuery.refetch();
    signalsQuery.refetch();
    chainQuery.refetch();
  };

  const backgroundError =
    latestQuery.isError && !latestQuery.isLoading
      ? latestQuery.error
      : metricsQuery.isError && !metricsQuery.isLoading
        ? metricsQuery.error
        : signalsQuery.isError && !signalsQuery.isLoading
          ? signalsQuery.error
          : null;

  const toastMessage =
    backgroundError && !isLoading && !criticalError
      ? formatApiError(backgroundError)
      : null;

  const showToast =
    toastMessage != null && toastMessage !== dismissedToast;

  if (isLoading) {
    return <DashboardSkeleton />;
  }

  if (criticalError) {
    return (
      <DashboardError
        message={formatApiError(criticalError)}
        onRetry={retryAll}
      />
    );
  }

  if (!metricsRow || !signalsQuery.data) {
    return <DashboardEmpty symbol={symbol} />;
  }

  const chain = chainQuery.data ?? [];
  const chainLoading = chainQuery.isLoading;
  const chainErrorMessage = chainQuery.isError
    ? formatApiError(chainQuery.error, "Failed to load option chain.")
    : null;

  const chainSection = chainLoading ? (
    <ChartSkeleton />
  ) : chainErrorMessage ? (
    <SectionError message={chainErrorMessage} onRetry={() => chainQuery.refetch()} />
  ) : null;

  const sessionSnapshotsError = sessionSnapshotsQuery.isError
    ? formatApiError(
        sessionSnapshotsQuery.error,
        "Failed to load session snapshots.",
      )
    : null;

  return (
    <>
      {showToast ? (
        <ErrorToast
          message={toastMessage}
          onRetry={retryAll}
          onDismiss={() => setDismissedToast(toastMessage)}
        />
      ) : null}

      <div className="flex h-full min-h-0 flex-col p-3">
        <header className="shrink-0 border-b border-border pb-2">
          <KpiHeader
            metrics={metricsRow}
            dayChange={dayChange}
            variant="strip"
          />
        </header>

        <DashboardTabs value={activeTab} onChange={setActiveTab} />

        <div className="min-h-0 flex-1 overflow-hidden pt-2">
          {activeTab === "overview" ? (
            <OverviewPanel
              metricsSeries={filteredSeries}
              metricsRow={metricsRow}
              chain={chain}
              chainSection={chainSection}
              overall={signalsQuery.data.overall}
              signals={signalsQuery.data.signals}
              sessionSnapshots={sessionSnapshotsQuery.data}
              sessionSnapshotsLoading={sessionSnapshotsQuery.isLoading}
              sessionSnapshotsError={sessionSnapshotsError}
              sessionDate={effectiveSessionDate}
              onSessionDateChange={setSessionDateOverride}
            />
          ) : null}
          {activeTab === "chain" ? (
            <div className="h-full min-h-0 overflow-y-auto">
              <ChainPanel
                chain={chain}
                atmStrike={metricsRow.atm_strike}
                loading={chainLoading}
                errorMessage={chainErrorMessage}
                onRetry={() => chainQuery.refetch()}
              />
            </div>
          ) : null}
          {activeTab === "insights" ? (
            <div className="h-full min-h-0 overflow-y-auto">
              <InsightsPanel symbol={symbol} />
            </div>
          ) : null}
        </div>
      </div>
    </>
  );
}
