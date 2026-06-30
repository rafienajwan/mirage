"use client";

import GlassPanel from "@/components/ui/GlassPanel";
import type { ActorCaseSummary, ActorCaseWorkflow, ActorCaseWorkflowSummary, ActorClusterSummary } from "@/lib/api";
import { cn } from "@/lib/utils";
import { AlertTriangle, Boxes, CheckCircle2, FolderSearch, GitBranch, Inbox, KeyRound, Loader2, Play, UsersRound } from "lucide-react";

const severityStyles: Record<ActorCaseSummary["cases"][number]["severity"], string> = {
  low: "border-white/10 bg-white/5 text-white/45",
  medium: "border-amber-500/20 bg-amber-500/10 text-amber-300",
  high: "border-red-500/20 bg-red-500/10 text-red-300",
  critical: "border-brand-cyan/25 bg-brand-cyan/10 text-brand-cyan",
};

const statusLabels: Record<ActorClusterSummary["clusters"][number]["status"], string> = {
  quiet: "Quiet",
  watch: "Watch",
  suspicious: "Suspicious",
  confirmed_interaction: "Confirmed",
};

interface ActorTriagePanelProps {
  clusters: ActorClusterSummary | null;
  cases: ActorCaseSummary | null;
  workflows: ActorCaseWorkflowSummary | null;
  workingCaseId: string | null;
  onOpenCase: (caseId: string) => void;
  onUpdateCase: (caseId: string, status: ActorCaseWorkflow["status"]) => void;
}

export default function ActorTriagePanel({
  clusters,
  cases,
  workflows,
  workingCaseId,
  onOpenCase,
  onUpdateCase,
}: ActorTriagePanelProps) {
  const clusterItems = clusters?.clusters ?? [];
  const caseItems = cases?.cases ?? [];
  const workflowItems = workflows?.cases ?? [];
  const openCaseIds = new Set(workflowItems.map((item) => item.id));

  return (
    <GlassPanel className="p-5">
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <span className="font-display text-[10px] uppercase tracking-widest text-white/50">
          Actor Triage
        </span>
        <div className="flex flex-wrap items-center gap-2 text-[9px] font-mono text-white/40">
          <span className="flex items-center gap-1.5">
            <FolderSearch className="h-3.5 w-3.5 text-brand-cyan/80" />
            {cases?.totalCases ?? 0} cases
          </span>
          <span className="flex items-center gap-1.5">
            <CheckCircle2 className="h-3.5 w-3.5 text-brand-emerald/80" />
            {workflows?.totalCases ?? 0} open
          </span>
          <span className="flex items-center gap-1.5">
            <GitBranch className="h-3.5 w-3.5 text-brand-emerald/80" />
            {clusters?.totalClusters ?? 0} clusters
          </span>
        </div>
      </div>

      {caseItems.length === 0 && clusterItems.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-2 py-8 text-white/25">
          <Inbox className="h-6 w-6" />
          <span className="text-[10px] font-mono">No actor triage data yet</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.1fr_0.9fr]">
          <div>
            <div className="mb-2 flex items-center gap-2 text-[9px] font-mono uppercase tracking-widest text-white/30">
              <AlertTriangle className="h-3.5 w-3.5" />
              Recommended Cases
            </div>
            {caseItems.length === 0 ? (
              <EmptyLine label="No recommended cases" />
            ) : (
              <div className="space-y-2">
                {caseItems.slice(0, 3).map((item) => (
                  <div key={item.id} className="rounded-lg border border-white/5 bg-white/2 p-3">
                    <div className="mb-2 flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-[11px] font-semibold text-white/80">
                          {item.title}
                        </p>
                        <p className="mt-1 truncate font-mono text-[8px] text-white/30">
                          {item.id} | {item.clusterId}
                        </p>
                      </div>
                      <span
                        className={cn(
                          "shrink-0 rounded border px-2 py-0.5 text-[8px] font-bold uppercase",
                          severityStyles[item.severity],
                        )}
                      >
                        {item.severity}
                      </span>
                    </div>

                    <p className="mb-2 line-clamp-2 text-[10px] leading-relaxed text-white/45">
                      {item.recommendedAction}
                    </p>

                    <div className="flex flex-wrap gap-1.5">
                      <TriagePill icon={UsersRound} label={`${item.actorCount} actors`} />
                      {item.evidence.slice(0, 2).map((evidence) => (
                        <span
                          key={evidence}
                          className="max-w-full truncate rounded border border-white/5 bg-black/10 px-2 py-0.5 text-[8px] font-mono text-white/35"
                        >
                          {evidence}
                        </span>
                      ))}
                    </div>

                    <div className="mt-3 flex items-center justify-between gap-2">
                      <span className="truncate font-mono text-[8px] text-white/25">
                        {openCaseIds.has(item.id) ? "Workflow opened" : "Recommended only"}
                      </span>
                      <button
                        type="button"
                        onClick={() => onOpenCase(item.id)}
                        disabled={openCaseIds.has(item.id) || workingCaseId === item.id}
                        className="inline-flex shrink-0 items-center gap-1.5 rounded border border-brand-cyan/20 bg-brand-cyan/10 px-2.5 py-1 text-[8px] font-bold uppercase tracking-widest text-brand-cyan transition-colors hover:border-brand-cyan/40 disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        {workingCaseId === item.id ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <Play className="h-3 w-3" />
                        )}
                        Open Case
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div>
            <div className="mb-4">
              <div className="mb-2 flex items-center gap-2 text-[9px] font-mono uppercase tracking-widest text-white/30">
                <CheckCircle2 className="h-3.5 w-3.5" />
                Workflow Cases
              </div>
              {workflowItems.length === 0 ? (
                <EmptyLine label="No persisted cases" />
              ) : (
                <div className="space-y-2">
                  {workflowItems.slice(0, 3).map((item) => (
                    <div key={item.id} className="rounded-lg border border-white/5 bg-brand-emerald/5 p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-[10px] font-semibold text-white/75">
                            {item.title}
                          </p>
                        <p className="mt-1 truncate font-mono text-[8px] text-white/30">
                            {item.status} | {item.assignedTo || "unassigned"} | {item.id}
                        </p>
                        </div>
                        <span
                          className={cn(
                            "shrink-0 rounded border px-2 py-0.5 text-[8px] font-bold uppercase",
                            severityStyles[item.severity],
                          )}
                        >
                          {item.severity}
                        </span>
                      </div>

                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {item.status !== "investigating" ? (
                          <WorkflowButton
                            label="Investigate"
                            caseId={item.id}
                            status="investigating"
                            workingCaseId={workingCaseId}
                            onUpdateCase={onUpdateCase}
                          />
                        ) : null}
                        {item.status !== "closed" ? (
                          <WorkflowButton
                            label="Close"
                            caseId={item.id}
                            status="closed"
                            workingCaseId={workingCaseId}
                            onUpdateCase={onUpdateCase}
                          />
                        ) : null}
                        {item.status === "closed" ? (
                          <WorkflowButton
                            label="Reopen"
                            caseId={item.id}
                            status="open"
                            workingCaseId={workingCaseId}
                            onUpdateCase={onUpdateCase}
                          />
                        ) : null}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="mb-2 flex items-center gap-2 text-[9px] font-mono uppercase tracking-widest text-white/30">
              <Boxes className="h-3.5 w-3.5" />
              Cluster Signals
            </div>
            {clusterItems.length === 0 ? (
              <EmptyLine label="No clusters yet" />
            ) : (
              <div className="space-y-2">
                {clusterItems.slice(0, 4).map((cluster) => (
                  <div key={cluster.id} className="rounded-lg border border-white/5 bg-black/10 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-[10px] font-mono text-white/70">
                          {cluster.label}
                        </p>
                        <p className="mt-1 font-mono text-[8px] text-white/30">
                          {statusLabels[cluster.status]} | risk {cluster.maxRiskScore.toFixed(1)}
                        </p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2 text-[8px] font-mono text-white/40">
                        <TriagePill icon={UsersRound} label={`${cluster.actorCount}`} />
                        <TriagePill icon={KeyRound} label={`${cluster.honeytokenHits}`} />
                      </div>
                    </div>

                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {cluster.sharedPaths.map((path) => (
                        <span
                          key={path}
                          className="max-w-full truncate rounded border border-white/5 bg-white/5 px-2 py-0.5 text-[8px] font-mono text-white/35"
                        >
                          {path}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </GlassPanel>
  );
}

function TriagePill({ icon: Icon, label }: { icon: typeof UsersRound; label: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded border border-white/5 bg-white/5 px-2 py-0.5 text-[8px] font-mono text-white/40">
      <Icon className="h-3 w-3" />
      {label}
    </span>
  );
}

function WorkflowButton({
  label,
  caseId,
  status,
  workingCaseId,
  onUpdateCase,
}: {
  label: string;
  caseId: string;
  status: ActorCaseWorkflow["status"];
  workingCaseId: string | null;
  onUpdateCase: (caseId: string, status: ActorCaseWorkflow["status"]) => void;
}) {
  const working = workingCaseId === `${caseId}:${status}`;
  return (
    <button
      type="button"
      onClick={() => onUpdateCase(caseId, status)}
      disabled={working}
      className="inline-flex items-center gap-1.5 rounded border border-white/10 bg-white/5 px-2.5 py-1 text-[8px] font-bold uppercase tracking-widest text-white/45 transition-colors hover:border-white/20 hover:text-white/70 disabled:cursor-wait disabled:opacity-40"
    >
      {working ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
      {label}
    </button>
  );
}

function EmptyLine({ label }: { label: string }) {
  return (
    <div className="rounded-lg border border-white/5 bg-white/2 px-3 py-5 text-center text-[10px] font-mono text-white/25">
      {label}
    </div>
  );
}
