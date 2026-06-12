"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type {
  SessionPhaseSnapshot,
  SessionPhaseStatus,
  SessionSnapshotsResponse,
} from "@/lib/api-types";
import { formatNumber } from "@/lib/format";

type SessionSnapshotsPanelProps = {
  data: SessionSnapshotsResponse | undefined;
  isLoading: boolean;
  error: string | null;
  sessionDate: string | undefined;
  onSessionDateChange: (date: string | undefined) => void;
};

type PhaseKey = "morning" | "midday" | "evening";

const PHASE_LABELS: Record<PhaseKey, string> = {
  morning: "Morning",
  midday: "Midday",
  evening: "Evening",
};

const PHASE_OPEN_IST: Record<PhaseKey, string> = {
  morning: "09:21",
  midday: "12:30",
  evening: "15:00",
};

function formatDisplayDate(yyyymmdd: string): string {
  if (yyyymmdd.length !== 8) {
    return yyyymmdd;
  }
  return `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6, 8)}`;
}

function phaseSubtitle(phase: SessionPhaseSnapshot, phaseKey: PhaseKey): string {
  if (phase.status === "populated") {
    return phase.timestamp;
  }
  if (phase.status === "pending") {
    return `Opens at ${PHASE_OPEN_IST[phaseKey]} IST`;
  }
  const window = phase.window_label || "this window";
  return `No tick captured (${window})`;
}

function statusLabel(status: SessionPhaseStatus): string {
  if (status === "populated") {
    return "Live";
  }
  if (status === "pending") {
    return "Pending";
  }
  return "Missed";
}

function StrikeList({
  label,
  strikes,
  empty,
}: {
  label: string;
  strikes: Array<{ strike: string; oi: string }>;
  empty: boolean;
}) {
  return (
    <div className="space-y-1">
      <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <ul className="space-y-0.5 text-xs">
        {strikes.map((item, index) => (
          <li
            key={`${label}-${item.strike}-${index}`}
            className="flex justify-between gap-2 font-mono tabular-nums"
          >
            <span>{empty || item.strike === "N/A" ? "—" : item.strike}</span>
            <span className="text-muted-foreground">
              {empty || item.oi === "N/A"
                ? "—"
                : formatNumber(Number(item.oi))}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function phaseStrikes(phase: SessionPhaseSnapshot, side: "ce" | "pe") {
  return [1, 2, 3].map((rank) => ({
    strike: phase[`top${rank}${side}_strike` as keyof SessionPhaseSnapshot] as string,
    oi: phase[`top${rank}${side}_oi` as keyof SessionPhaseSnapshot] as string,
  }));
}

function PhaseCard({
  label,
  phaseKey,
  phase,
}: {
  label: string;
  phaseKey: PhaseKey;
  phase: SessionPhaseSnapshot;
}) {
  const populated = phase.status === "populated";

  return (
    <Card className="shadow-none">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-sm font-medium">{label}</CardTitle>
          <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
            {statusLabel(phase.status)}
          </span>
        </div>
        <p className="text-[10px] text-muted-foreground">
          {phaseSubtitle(phase, phaseKey)}
        </p>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-muted-foreground">Underlying</span>
          <span className="font-mono tabular-nums">
            {populated
              ? formatNumber(Number(phase.underlying), { decimals: 2 })
              : "—"}
          </span>
        </div>
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-muted-foreground">PCR</span>
          <span className="font-mono tabular-nums">
            {populated ? phase.pcr : "—"}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-3 border-t border-border pt-3">
          <StrikeList
            label="Top CE OI"
            strikes={phaseStrikes(phase, "ce")}
            empty={!populated}
          />
          <StrikeList
            label="Top PE OI"
            strikes={phaseStrikes(phase, "pe")}
            empty={!populated}
          />
        </div>
        <div className="grid grid-cols-2 gap-2 border-t border-border pt-3 text-[10px] text-muted-foreground">
          <div>
            <span className="block">CE OI / Vol</span>
            <span className="font-mono text-xs text-foreground tabular-nums">
              {populated
                ? `${formatNumber(Number(phase.overall_ce_oi))} / ${formatNumber(Number(phase.overall_ce_volume))}`
                : "—"}
            </span>
          </div>
          <div>
            <span className="block">PE OI / Vol</span>
            <span className="font-mono text-xs text-foreground tabular-nums">
              {populated
                ? `${formatNumber(Number(phase.overall_pe_oi))} / ${formatNumber(Number(phase.overall_pe_volume))}`
                : "—"}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function SessionSnapshotsPanel({
  data,
  isLoading,
  error,
  sessionDate,
  onSessionDateChange,
}: SessionSnapshotsPanelProps) {
  if (isLoading) {
    return (
      <div className="grid gap-2 md:grid-cols-3">
        {(["morning", "midday", "evening"] as PhaseKey[]).map((phase) => (
          <Card key={phase} className="h-48 animate-pulse shadow-none" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <p className="text-sm text-muted-foreground">
        Session snapshots unavailable: {error}
      </p>
    );
  }

  if (!data) {
    return null;
  }

  const inputValue = sessionDate
    ? formatDisplayDate(sessionDate)
    : formatDisplayDate(data.requested_date);

  return (
    <section className="space-y-2">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-sm font-medium">Session snapshots</h2>
          <p className="text-[10px] text-muted-foreground">
            IST phase windows per strategy spec
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label
            htmlFor="session-snapshot-date"
            className="text-[10px] text-muted-foreground"
          >
            Session date
          </label>
          <Input
            id="session-snapshot-date"
            type="date"
            className="h-8 w-36 text-xs"
            value={inputValue}
            onChange={(event) => {
              const raw = event.target.value.replace(/-/g, "");
              onSessionDateChange(raw || undefined);
            }}
          />
        </div>
      </div>

      {data.date_fallback ? (
        <p className="rounded-md border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
          Showing {formatDisplayDate(data.resolved_date)} — today&apos;s session
          phases are not captured yet.
        </p>
      ) : null}

      <div className="grid gap-2 md:grid-cols-3">
        {(["morning", "midday", "evening"] as PhaseKey[]).map((phase) => (
          <PhaseCard
            key={phase}
            label={PHASE_LABELS[phase]}
            phaseKey={phase}
            phase={data[phase]}
          />
        ))}
      </div>
    </section>
  );
}
