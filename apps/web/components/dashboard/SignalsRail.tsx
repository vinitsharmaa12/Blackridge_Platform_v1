"use client";

import type { SignalCard } from "@/lib/api-types";
import { cn } from "@/lib/utils";

const DIRECTION_STYLES: Record<
  SignalCard["direction"],
  { border: string; badge: string }
> = {
  bullish: {
    border: "border-l-emerald-600",
    badge: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400",
  },
  bearish: {
    border: "border-l-red-600",
    badge: "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-400",
  },
  neutral: {
    border: "border-l-border",
    badge: "bg-muted text-muted-foreground",
  },
};

function StrengthDots({ strength }: { strength: number }) {
  return (
    <span className="flex shrink-0 gap-0.5" aria-label={`Strength ${strength} of 3`}>
      {Array.from({ length: 3 }).map((_, i) => (
        <span
          key={i}
          className={cn(
            "size-1.5 rounded-full",
            i < strength ? "bg-foreground/80" : "bg-muted-foreground/30",
          )}
        />
      ))}
    </span>
  );
}

function DirectionBadge({ direction }: { direction: SignalCard["direction"] }) {
  const styles = DIRECTION_STYLES[direction];
  return (
    <span
      className={cn(
        "shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium capitalize",
        styles.badge,
      )}
    >
      {direction}
    </span>
  );
}

function SignalCardItem({
  signal,
  featured = false,
}: {
  signal: SignalCard;
  featured?: boolean;
}) {
  const styles = DIRECTION_STYLES[signal.direction];

  return (
    <article
      className={cn(
        "shrink-0 border border-border border-l-2 p-2",
        styles.border,
        featured && "bg-muted/30",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-xs font-medium leading-snug">{signal.title}</h3>
        <div className="flex shrink-0 items-center gap-1.5">
          <StrengthDots strength={signal.strength} />
          <DirectionBadge direction={signal.direction} />
        </div>
      </div>
      <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
        {signal.text}
      </p>
    </article>
  );
}

type SignalsRailProps = {
  overall: SignalCard;
  signals: SignalCard[];
};

export function SignalsRail({ overall, signals }: SignalsRailProps) {
  const rest = signals.filter((s) => s.key !== "overall_read");

  return (
    <aside
      className="flex w-56 shrink-0 flex-col gap-2 overflow-y-auto border-l border-border pl-2 lg:w-60"
      aria-label="Signals"
    >
      <p className="shrink-0 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        Signals
      </p>
      <SignalCardItem signal={overall} featured />
      {rest.map((signal) => (
        <SignalCardItem key={signal.key} signal={signal} />
      ))}
    </aside>
  );
}
