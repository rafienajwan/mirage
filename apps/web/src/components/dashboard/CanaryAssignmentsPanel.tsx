"use client";

import GlassPanel from "@/components/ui/GlassPanel";
import type { CanaryAssignmentSummary } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Ban, CheckCircle2, KeyRound, Loader2, RotateCcw } from "lucide-react";

interface CanaryAssignmentsPanelProps {
  data: CanaryAssignmentSummary | null;
  workingAssignmentId: string | null;
  onRevoke: (assignmentId: string) => void;
}

const statusStyles = {
  active: "border-brand-emerald/20 bg-brand-emerald/10 text-brand-emerald",
  revoked: "border-red-500/20 bg-red-500/10 text-red-300",
};

export default function CanaryAssignmentsPanel({
  data,
  workingAssignmentId,
  onRevoke,
}: CanaryAssignmentsPanelProps) {
  const assignments = data?.assignments ?? [];
  const activeCount = assignments.filter((item) => item.status === "active").length;
  const revokedCount = assignments.filter((item) => item.status === "revoked").length;

  return (
    <GlassPanel className="p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <span className="font-display text-[10px] uppercase tracking-widest text-white/50">
          Canary Assignments
        </span>
        <div className="flex items-center gap-3 font-mono text-[9px] text-white/35">
          <span className="flex items-center gap-1">
            <CheckCircle2 className="h-3.5 w-3.5 text-brand-emerald/80" />
            {activeCount} active
          </span>
          <span className="flex items-center gap-1">
            <Ban className="h-3.5 w-3.5 text-red-300/80" />
            {revokedCount} revoked
          </span>
        </div>
      </div>

      {assignments.length === 0 ? (
        <div className="flex h-36 flex-col items-center justify-center gap-2 text-white/25">
          <KeyRound className="h-6 w-6" />
          <span className="text-[10px] font-mono">No canary assignments yet</span>
        </div>
      ) : (
        <div className="space-y-2">
          {assignments.slice(0, 5).map((assignment) => {
            const working = workingAssignmentId === assignment.id;
            return (
              <div
                key={assignment.id}
                className="rounded-lg border border-white/5 bg-white/2 p-3"
              >
                <div className="mb-2 flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-[11px] font-semibold text-white/80">
                      {assignment.tokenLabel}
                    </p>
                    <p className="mt-1 truncate font-mono text-[8px] text-white/30">
                      {assignment.actorId} | epoch {assignment.rotationEpoch}
                    </p>
                  </div>
                  <span
                    className={cn(
                      "shrink-0 rounded border px-2 py-0.5 text-[8px] font-bold uppercase",
                      statusStyles[assignment.status],
                    )}
                  >
                    {assignment.status}
                  </span>
                </div>

                <div className="mb-3 grid grid-cols-1 gap-1 font-mono text-[8px] text-white/35 sm:grid-cols-2">
                  <span className="truncate">{assignment.decoyType}</span>
                  <span className="truncate sm:text-right">{assignment.sourcePath}</span>
                  <span className="truncate">hash {assignment.tokenHash.slice(0, 12)}</span>
                  <span className="truncate sm:text-right">
                    {new Date(assignment.lastSeenAt).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>

                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-[8px] text-white/25">
                    {assignment.revokeReason || "Lifecycle record"}
                  </span>
                  <button
                    type="button"
                    onClick={() => onRevoke(assignment.id)}
                    disabled={assignment.status === "revoked" || working}
                    className="inline-flex shrink-0 items-center gap-1.5 rounded border border-red-500/20 bg-red-500/10 px-2.5 py-1 text-[8px] font-bold uppercase tracking-widest text-red-300 transition-colors hover:border-red-500/40 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {working ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <RotateCcw className="h-3 w-3" />
                    )}
                    Revoke
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </GlassPanel>
  );
}
