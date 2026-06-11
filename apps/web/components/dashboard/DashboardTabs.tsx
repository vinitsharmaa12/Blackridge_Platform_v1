"use client";

import { cn } from "@/lib/utils";

export type DashboardTab = "overview" | "chain" | "insights";

const TABS: { id: DashboardTab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "chain", label: "Chain" },
  { id: "insights", label: "Insights" },
];

type DashboardTabsProps = {
  value: DashboardTab;
  onChange: (tab: DashboardTab) => void;
};

export function DashboardTabs({ value, onChange }: DashboardTabsProps) {
  return (
    <div
      className="flex shrink-0 gap-1 border-b border-border"
      role="tablist"
      aria-label="Dashboard views"
    >
      {TABS.map((tab) => {
        const active = value === tab.id;
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={active}
            data-active={active ? true : undefined}
            className={cn(
              "border-b-2 border-transparent px-3 py-1.5 text-sm text-muted-foreground",
              "hover:text-foreground",
              active && "border-foreground font-medium text-foreground",
            )}
            onClick={() => onChange(tab.id)}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
