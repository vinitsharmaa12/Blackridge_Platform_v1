"use client";

import { Label } from "@/components/ui/label";
import { formatSnapshotTime } from "@/lib/format";
import { cn } from "@/lib/utils";

type SnapshotControlsProps = {
  at: string;
  snapshots: string[];
  onChange: (at: string) => void;
  variant?: "default" | "inline";
};

export function SnapshotControls({
  at,
  snapshots,
  onChange,
  variant = "default",
}: SnapshotControlsProps) {
  const inline = variant === "inline";

  const select = (
    <select
      id="snapshot-select"
      aria-label="Snapshot"
      className={cn(
        "rounded-md border border-input bg-background",
        inline
          ? "h-7 min-w-[140px] px-2 text-xs"
          : "h-9 min-w-[200px] px-3 text-sm",
      )}
      value={at}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="latest">Latest</option>
      {snapshots.map((time) => (
        <option key={time} value={time}>
          {formatSnapshotTime(time)}
        </option>
      ))}
    </select>
  );

  if (inline) {
    return select;
  }

  return (
    <div className="flex flex-wrap items-end gap-4">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="snapshot-select" className="text-xs text-muted-foreground">
          Snapshot
        </Label>
        {select}
      </div>
      {at !== "latest" ? (
        <p className="text-xs text-muted-foreground">
          Viewing {formatSnapshotTime(at)}
        </p>
      ) : null}
    </div>
  );
}
