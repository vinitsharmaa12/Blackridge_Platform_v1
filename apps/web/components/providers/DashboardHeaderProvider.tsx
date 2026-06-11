"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import type { LiveConnectionStatus } from "@/hooks/useLiveMetrics";

export type DashboardHeaderControls = {
  liveEnabled: boolean;
  liveStatus: LiveConnectionStatus;
  onLiveToggle: () => void;
  at: string;
  snapshots: string[];
  onSnapshotChange: (at: string) => void;
};

type DashboardHeaderContextValue = {
  controls: DashboardHeaderControls | null;
  setControls: (controls: DashboardHeaderControls | null) => void;
};

const DashboardHeaderContext =
  createContext<DashboardHeaderContextValue | null>(null);

export function DashboardHeaderProvider({ children }: { children: ReactNode }) {
  const [controls, setControls] = useState<DashboardHeaderControls | null>(null);
  const value = useMemo(
    () => ({ controls, setControls }),
    [controls],
  );

  return (
    <DashboardHeaderContext.Provider value={value}>
      {children}
    </DashboardHeaderContext.Provider>
  );
}

export function useDashboardHeader(): DashboardHeaderControls | null {
  const ctx = useContext(DashboardHeaderContext);
  if (!ctx) {
    throw new Error(
      "useDashboardHeader must be used within DashboardHeaderProvider",
    );
  }
  return ctx.controls;
}

export function useDashboardHeaderControls(
  controls: DashboardHeaderControls,
): void {
  const ctx = useContext(DashboardHeaderContext);
  if (!ctx) {
    throw new Error(
      "useDashboardHeaderControls must be used within DashboardHeaderProvider",
    );
  }

  const {
    liveEnabled,
    liveStatus,
    onLiveToggle,
    at,
    snapshots,
    onSnapshotChange,
  } = controls;

  useEffect(() => {
    ctx.setControls(controls);
    return () => ctx.setControls(null);
  }, [
    ctx,
    controls,
    liveEnabled,
    liveStatus,
    onLiveToggle,
    at,
    snapshots,
    onSnapshotChange,
  ]);
}
