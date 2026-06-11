import { Button } from "@/components/ui/button";
import type { LiveConnectionStatus } from "@/hooks/useLiveMetrics";
import { cn } from "@/lib/utils";

const STATUS_LABEL: Record<LiveConnectionStatus, string> = {
  off: "Off",
  connecting: "Connecting…",
  live: "Live",
  reconnecting: "Reconnecting…",
  polling: "Polling fallback",
};

type LiveToggleProps = {
  enabled: boolean;
  status: LiveConnectionStatus;
  onToggle: () => void;
  variant?: "default" | "inline";
};

export function LiveToggle({
  enabled,
  status,
  onToggle,
  variant = "default",
}: LiveToggleProps) {
  const inline = variant === "inline";

  return (
    <div className={cn("flex items-center gap-2", inline && "gap-1.5")}>
      <Button
        type="button"
        variant={enabled ? "default" : "outline"}
        size="sm"
        className={cn(inline && "h-7 px-2.5 text-[0.8rem]")}
        onClick={onToggle}
        aria-pressed={enabled}
      >
        Live
      </Button>
      {enabled ? (
        <span
          className={cn(
            "text-xs text-muted-foreground",
            inline && "hidden md:inline",
          )}
        >
          {STATUS_LABEL[status]}
        </span>
      ) : null}
    </div>
  );
}
