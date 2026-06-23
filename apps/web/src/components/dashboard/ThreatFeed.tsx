"use client";

import GlassPanel from "@/components/ui/GlassPanel";
import type { ThreatSeverity, ThreatStatus } from "@/lib/mock-data";
import type { AnalystLabel, FeedEvent } from "@/lib/api";
import { cn } from "@/lib/utils";
import { AlertTriangle, Inbox } from "lucide-react";

const severityStyles: Record<ThreatSeverity, string> = {
  low: "text-white/50 bg-white/5 border-white/10",
  medium: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  high: "text-orange-400 bg-orange-500/10 border-orange-500/20",
  critical: "text-red-400 bg-red-500/10 border-red-500/20",
};

const statusStyles: Record<ThreatStatus, string> = {
  allowed: "text-white/50 bg-white/5 border-white/10",
  redirected: "text-brand-cyan bg-brand-cyan/10 border-brand-cyan/20",
  decoy_active: "text-brand-emerald bg-brand-emerald/10 border-brand-emerald/20",
  contained: "text-purple-400 bg-purple-500/10 border-purple-500/20",
  alert: "text-amber-400 bg-amber-500/10 border-amber-500/20",
};

const statusLabel: Record<ThreatStatus, string> = {
  allowed: "Allowed",
  redirected: "Redirected",
  decoy_active: "Decoy Active",
  contained: "Contained",
  alert: "Alert",
};

const analystLabels: { value: AnalystLabel; label: string }[] = [
  { value: "normal", label: "Normal" },
  { value: "suspicious", label: "Suspicious" },
  { value: "false_positive", label: "False +" },
  { value: "false_negative", label: "False -" },
];

interface ThreatFeedProps {
  events: FeedEvent[];
  labelingEventId?: string | null;
  onLabel?: (eventId: string, label: AnalystLabel) => void;
}

/**
 * Recent threat activity feed/table for the dashboard.
 * Accepts events as a prop — pass live data from the API or mock data.
 */
export default function ThreatFeed({
  events,
  labelingEventId = null,
  onLabel,
}: ThreatFeedProps) {
  const showMLShadow = events.some((event) => event.mlShadow);
  const headerGridClass = showMLShadow
    ? "hidden sm:grid grid-cols-[1fr_92px_68px_76px_86px_96px] gap-2 text-[8px] text-white/30 uppercase tracking-widest pb-2 border-b border-white/5 mb-2"
    : "hidden sm:grid grid-cols-[1fr_100px_80px_80px_90px] gap-2 text-[8px] text-white/30 uppercase tracking-widest pb-2 border-b border-white/5 mb-2";
  const rowGridClass = showMLShadow
    ? "grid grid-cols-1 sm:grid-cols-[1fr_92px_68px_76px_86px_96px] gap-1 sm:gap-2 items-start sm:items-center py-2 border-b border-white/5 last:border-0"
    : "grid grid-cols-1 sm:grid-cols-[1fr_100px_80px_80px_90px] gap-1 sm:gap-2 items-start sm:items-center py-2 border-b border-white/5 last:border-0";

  return (
    <GlassPanel className="p-5">
      <div className="flex items-center justify-between mb-4">
        <span className="font-display text-[10px] tracking-widest text-white/50 uppercase">
          Recent Threat Activity
        </span>
        <div className="flex items-center gap-1.5">
          <AlertTriangle className="w-3.5 h-3.5 text-red-400/60 animate-pulse" />
          <span className="text-[9px] text-red-400/80 font-mono">LIVE</span>
        </div>
      </div>

      {events.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-10 gap-2 text-white/25">
          <Inbox className="w-6 h-6" />
          <span className="text-[10px] font-mono">
            No events yet — run a simulation to generate activity
          </span>
        </div>
      ) : (
        <>
          {/* Table header */}
          <div className={headerGridClass}>
            <span>Event</span>
            <span>Source</span>
            <span>Risk</span>
            <span>Severity</span>
            <span>Status</span>
            {showMLShadow ? <span>ML Shadow</span> : null}
          </div>

          {/* Feed items */}
          <div className="space-y-2 max-h-[320px] overflow-y-auto">
            {events.map((event) => (
              <div
                key={event.id}
                className={rowGridClass}
              >
                {/* Event info */}
                <div className="flex flex-col gap-1">
                  <span className="text-[11px] text-white/80 font-medium">{event.type}</span>
                  <span className="text-[9px] text-white/30 font-mono">{event.endpoint}</span>
                  {onLabel ? (
                    <select
                      aria-label={`Analyst label for ${event.endpoint}`}
                      value={event.analystLabel ?? ""}
                      disabled={labelingEventId === event.id}
                      onChange={(item) => {
                        if (item.target.value) {
                          onLabel(event.id, item.target.value as AnalystLabel);
                        }
                      }}
                      className="mt-1 w-fit max-w-full rounded border border-white/10 bg-white/5 px-2 py-1 text-[8px] font-mono uppercase text-white/55 outline-none transition-colors hover:border-white/20 disabled:cursor-wait disabled:opacity-40"
                    >
                      <option value="">Unlabeled</option>
                      {analystLabels.map((item) => (
                        <option key={item.value} value={item.value}>
                          {item.label}
                        </option>
                      ))}
                    </select>
                  ) : null}
                </div>

                {/* Source IP */}
                <span className="text-[10px] text-white/40 font-mono">{event.sourceIp}</span>

                {/* Risk score */}
                <span className="text-[10px] font-mono font-bold text-white/70">
                  {event.riskScore.toFixed(1)}
                </span>

                {/* Severity badge */}
                <span
                  className={cn(
                    "text-[8px] font-bold px-2 py-0.5 rounded border uppercase w-fit",
                    severityStyles[event.severity]
                  )}
                >
                  {event.severity}
                </span>

                {/* Status badge */}
                <span
                  className={cn(
                    "text-[8px] font-bold px-2 py-0.5 rounded border uppercase w-fit",
                    statusStyles[event.status]
                  )}
                >
                  {statusLabel[event.status]}
                </span>

                {showMLShadow ? (
                  event.mlShadow ? (
                    <span
                      className={cn(
                        "text-[8px] font-bold px-2 py-0.5 rounded border uppercase w-fit",
                        event.mlShadow.agreesWithDecision
                          ? "text-brand-emerald bg-brand-emerald/10 border-brand-emerald/20"
                          : "text-amber-400 bg-amber-500/10 border-amber-500/20"
                      )}
                      title={`Artifact: ${event.mlShadow.artifact}; shadow decision: ${statusLabel[event.mlShadow.shadowDecision]}`}
                    >
                      {event.mlShadow.score.toFixed(1)}
                    </span>
                  ) : (
                    <span className="text-[8px] text-white/25 font-mono uppercase">
                      No model
                    </span>
                  )
                ) : null}
              </div>
            ))}
          </div>
        </>
      )}
    </GlassPanel>
  );
}
