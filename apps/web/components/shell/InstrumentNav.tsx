"use client";

import { Plus } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { useInstruments } from "@/hooks/useInstruments";
import {
  useAddWatchlist,
  useRemoveWatchlist,
  useWatchlist,
} from "@/hooks/useWatchlist";
import { cn } from "@/lib/utils";

function activeSymbol(pathname: string): string | null {
  const match = pathname.match(/^\/i\/([^/]+)/i);
  return match ? match[1].toUpperCase() : null;
}

export function InstrumentNav() {
  const pathname = usePathname();
  const current = activeSymbol(pathname ?? "") ?? "NIFTY";
  const [addSymbol, setAddSymbol] = useState("");
  const [showAdd, setShowAdd] = useState(false);

  const instrumentsQuery = useInstruments();
  const watchlistQuery = useWatchlist();
  const addMutation = useAddWatchlist();
  const removeMutation = useRemoveWatchlist();

  const watchlistSymbols = useMemo(
    () => new Set((watchlistQuery.data ?? []).map((w) => w.symbol)),
    [watchlistQuery.data],
  );

  const addable = useMemo(
    () =>
      (instrumentsQuery.data ?? []).filter(
        (inst) => !watchlistSymbols.has(inst.symbol),
      ),
    [instrumentsQuery.data, watchlistSymbols],
  );

  const navItems = watchlistQuery.data ?? [];
  const hasNifty = navItems.some((w) => w.symbol === "NIFTY");

  const symbols = [
    ...(!hasNifty ? [{ id: "nifty-fallback", symbol: "NIFTY" }] : []),
    ...navItems,
  ];

  return (
    <nav
      className="flex min-w-0 flex-1 items-center gap-2 text-xs"
      aria-label="Watchlist"
    >
      <ul className="flex min-w-0 items-center gap-0.5 overflow-x-auto">
        {symbols.map((entry) => (
          <li key={entry.id} className="group flex shrink-0 items-center">
            <Link
              href={`/i/${entry.symbol}`}
              className={cn(
                "border-b-2 border-transparent px-2 py-1 hover:text-foreground",
                current === entry.symbol
                  ? "border-foreground font-medium text-foreground"
                  : "text-muted-foreground",
              )}
            >
              {entry.symbol}
            </Link>
            {"id" in entry && entry.id !== "nifty-fallback" ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="size-5 shrink-0 p-0 text-[10px] text-muted-foreground opacity-0 group-hover:opacity-100"
                disabled={removeMutation.isPending}
                onClick={() => removeMutation.mutate(entry.symbol)}
                aria-label={`Remove ${entry.symbol} from watchlist`}
              >
                ×
              </Button>
            ) : null}
          </li>
        ))}
      </ul>

      {watchlistQuery.isLoading ? (
        <span className="shrink-0 text-[10px] text-muted-foreground">…</span>
      ) : null}

      {showAdd ? (
        <div className="flex shrink-0 items-center gap-1">
          <select
            id="add-watchlist"
            aria-label="Add symbol to watchlist"
            className="h-7 max-w-[100px] rounded-md border border-input bg-background px-1.5 text-[10px]"
            value={addSymbol}
            onChange={(e) => setAddSymbol(e.target.value)}
          >
            <option value="">Symbol…</option>
            {addable.map((inst) => (
              <option key={inst.id} value={inst.symbol}>
                {inst.symbol}
              </option>
            ))}
          </select>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-7 px-2 text-[10px]"
            disabled={!addSymbol || addMutation.isPending}
            onClick={() => {
              if (addSymbol) {
                addMutation.mutate(addSymbol);
                setAddSymbol("");
                setShowAdd(false);
              }
            }}
          >
            Add
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-[10px]"
            onClick={() => {
              setShowAdd(false);
              setAddSymbol("");
            }}
          >
            Cancel
          </Button>
        </div>
      ) : (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-7 shrink-0 gap-1 px-2 text-[10px] text-muted-foreground"
          onClick={() => setShowAdd(true)}
        >
          <Plus className="size-3" />
          Add
        </Button>
      )}
    </nav>
  );
}
