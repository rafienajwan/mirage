"use client";

import GlassPanel from "@/components/ui/GlassPanel";
import type { ActorProfileSummary } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Fingerprint, ShieldCheck, UsersRound } from "lucide-react";

const statusStyles: Record<ActorProfileSummary["profiles"][number]["status"], string> = {
  quiet: "border-white/10 bg-white/5 text-white/45",
  watch: "border-amber-500/20 bg-amber-500/10 text-amber-300",
  suspicious: "border-red-500/20 bg-red-500/10 text-red-300",
  confirmed_interaction: "border-brand-cyan/25 bg-brand-cyan/10 text-brand-cyan",
};

const statusLabels: Record<ActorProfileSummary["profiles"][number]["status"], string> = {
  quiet: "Quiet",
  watch: "Watch",
  suspicious: "Suspicious",
  confirmed_interaction: "Confirmed",
};

interface ActorProfilesPanelProps {
  data: ActorProfileSummary | null;
}

export default function ActorProfilesPanel({ data }: ActorProfilesPanelProps) {
  const profiles = data?.profiles ?? [];

  return (
    <GlassPanel className="p-5">
      <div className="flex items-center justify-between mb-4">
        <span className="font-display text-[10px] tracking-widest text-white/50 uppercase">
          Actor Profiles
        </span>
        <div className="flex items-center gap-1.5 text-[9px] text-brand-cyan/80 font-mono">
          <UsersRound className="w-3.5 h-3.5" />
          <span>{data?.totalActors ?? 0} tracked</span>
        </div>
      </div>

      {profiles.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-8 gap-2 text-white/25">
          <Fingerprint className="w-6 h-6" />
          <span className="text-[10px] font-mono">
            No actor profiles yet
          </span>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {profiles.slice(0, 4).map((profile) => (
            <div
              key={profile.id}
              className="rounded-lg border border-white/5 bg-white/2 p-4"
            >
              <div className="flex items-start justify-between gap-3 mb-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <Fingerprint className="w-3.5 h-3.5 shrink-0 text-brand-cyan/70" />
                    <span className="font-mono text-[10px] text-white/75 truncate">
                      {profile.id}
                    </span>
                  </div>
                  <p className="mt-1 text-[9px] font-mono text-white/30 truncate">
                    {profile.fingerprintHash.slice(0, 18)}...
                  </p>
                </div>
                <span
                  className={cn(
                    "shrink-0 rounded border px-2 py-0.5 text-[8px] font-bold uppercase",
                    statusStyles[profile.status],
                  )}
                >
                  {statusLabels[profile.status]}
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-3">
                <ProfileMetric label="Requests" value={profile.requestCount} />
                <ProfileMetric label="Risk" value={profile.maxRiskScore.toFixed(1)} />
                <ProfileMetric label="Decoys" value={profile.decoyRedirects} />
                <ProfileMetric label="Tokens" value={profile.honeytokenHits} />
              </div>

              <div className="flex items-center justify-between gap-3 text-[9px] font-mono text-white/35">
                <span className="truncate">{profile.sourceIp}</span>
                <span className="flex items-center gap-1 shrink-0">
                  <ShieldCheck className="w-3 h-3" />
                  {profile.lastDecision}
                </span>
              </div>

              <div className="mt-3 flex flex-wrap gap-1.5">
                {profile.topPaths.map((path) => (
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
    </GlassPanel>
  );
}

function ProfileMetric({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded border border-white/5 bg-black/10 px-2 py-2">
      <div className="text-[8px] uppercase tracking-widest text-white/25">{label}</div>
      <div className="mt-1 text-[11px] font-bold font-mono text-white/75">{value}</div>
    </div>
  );
}
