"use client";

import { Label } from "@/components/ui/label";
import { formatSnapshotTime } from "@/lib/format";
import {
  endOptionsForStart,
  type TimeRangeSelection,
  type TimeViewMode,
} from "@/lib/time-range";
import { cn } from "@/lib/utils";

type TimeRangeControlsProps = {
  timeRange: TimeRangeSelection;
  snapshotTimes: string[];
  onChange: (range: TimeRangeSelection) => void;
  disabled?: boolean;
  variant?: "default" | "inline";
};

const selectClass = (inline: boolean) =>
  cn(
    "rounded-md border border-input bg-background disabled:cursor-not-allowed disabled:opacity-50",
    inline ? "h-7 min-w-[120px] px-2 text-xs" : "h-9 min-w-[160px] px-3 text-sm",
  );

export function TimeRangeControls({
  timeRange,
  snapshotTimes,
  onChange,
  disabled = false,
  variant = "default",
}: TimeRangeControlsProps) {
  const inline = variant === "inline";
  const endOptions = endOptionsForStart(snapshotTimes, timeRange.from);

  const onModeChange = (mode: TimeViewMode) => {
    onChange({ ...timeRange, mode });
  };

  const onStartChange = (from: string) => {
    let to = timeRange.to;
    if (to && to < from) {
      to = from;
    }
    onChange({ ...timeRange, mode: "session", from, to });
  };

  const onEndChange = (to: string) => {
    onChange({ ...timeRange, mode: "session", to });
  };

  const modeSelect = (
    <select
      id="time-view-mode"
      aria-label="View mode"
      className={selectClass(inline)}
      value={timeRange.mode}
      disabled={disabled}
      onChange={(e) => onModeChange(e.target.value as TimeViewMode)}
    >
      <option value="session">Session</option>
      <option value="current">Current snapshot</option>
    </select>
  );

  const startSelect =
    timeRange.mode === "session" ? (
      <select
        id="time-range-start"
        aria-label="Start"
        className={selectClass(inline)}
        value={timeRange.from}
        disabled={disabled || snapshotTimes.length === 0}
        onChange={(e) => onStartChange(e.target.value)}
      >
        {snapshotTimes.map((time) => (
          <option key={time} value={time}>
            {formatSnapshotTime(time)}
          </option>
        ))}
      </select>
    ) : null;

  const endSelect =
    timeRange.mode === "session" ? (
      <select
        id="time-range-end"
        aria-label="End"
        className={selectClass(inline)}
        value={timeRange.to}
        disabled={disabled || endOptions.length === 0}
        onChange={(e) => onEndChange(e.target.value)}
      >
        {endOptions.map((time) => (
          <option key={time} value={time}>
            {formatSnapshotTime(time)}
          </option>
        ))}
      </select>
    ) : null;

  const rangeSummary =
    timeRange.mode === "session" &&
    timeRange.from &&
    timeRange.to &&
    !inline ? (
      <p className="text-xs text-muted-foreground">
        {formatSnapshotTime(timeRange.from)} → {formatSnapshotTime(timeRange.to)}
      </p>
    ) : null;

  if (inline) {
    return (
      <div className="flex items-center gap-1.5">
        {modeSelect}
        {startSelect}
        {endSelect}
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-end gap-4">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="time-view-mode" className="text-xs text-muted-foreground">
          View mode
        </Label>
        {modeSelect}
      </div>
      {timeRange.mode === "session" ? (
        <>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="time-range-start" className="text-xs text-muted-foreground">
              Start
            </Label>
            {startSelect}
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="time-range-end" className="text-xs text-muted-foreground">
              End
            </Label>
            {endSelect}
          </div>
        </>
      ) : null}
      {rangeSummary}
    </div>
  );
}
