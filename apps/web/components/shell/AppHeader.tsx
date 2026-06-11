"use client";

import { LogOut } from "lucide-react";

import { LiveToggle } from "@/components/dashboard/LiveToggle";
import { TimeRangeControls } from "@/components/dashboard/TimeRangeControls";
import { useDashboardHeader } from "@/components/providers/DashboardHeaderProvider";
import { InstrumentNav } from "@/components/shell/InstrumentNav";
import { SignOutButton } from "@/components/shell/SignOutButton";
import { Button } from "@/components/ui/button";

type AppHeaderProps = {
  email: string | undefined;
};

export function AppHeader({ email }: AppHeaderProps) {
  const headerControls = useDashboardHeader();

  return (
    <header className="flex h-11 shrink-0 items-center gap-2 border-b border-border px-3">
      <span className="shrink-0 text-sm font-medium">Blackridge</span>
      {headerControls ? (
        <div className="flex shrink-0 items-center gap-2 border-r border-border pr-2">
          <LiveToggle
            enabled={headerControls.liveEnabled}
            status={headerControls.liveStatus}
            onToggle={headerControls.onLiveToggle}
            variant="inline"
          />
          <TimeRangeControls
            timeRange={headerControls.timeRange}
            snapshotTimes={headerControls.snapshotTimes}
            onChange={headerControls.onTimeRangeChange}
            disabled={headerControls.timeRangeDisabled}
            variant="inline"
          />
        </div>
      ) : null}
      <InstrumentNav />
      <div className="flex shrink-0 items-center gap-1">
        <span
          className="max-w-[140px] truncate text-[10px] text-muted-foreground"
          title={email ?? undefined}
        >
          {email ?? "—"}
        </span>
        <SignOutButton
          renderTrigger={({ onClick }) => (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="size-7 shrink-0 p-0"
              onClick={onClick}
              aria-label="Sign out"
            >
              <LogOut className="size-3.5" />
            </Button>
          )}
        />
      </div>
    </header>
  );
}
