"use client";

import React from "react";
import GlassPanel from "@/components/ui/GlassPanel";
import { decoyEnvironments } from "@/lib/mock-data";
import type { DecoyState } from "@/lib/mock-data";
import { cn } from "@/lib/utils";
import { Container, Crosshair, Pause } from "lucide-react";

const stateConfig: Record<DecoyState, { label: string; color: string; icon: typeof Container }> = {
  routing: { label: "Routing", color: "text-brand-cyan bg-brand-cyan/10 border-brand-cyan/20", icon: Crosshair },
  contained: { label: "Contained", color: "text-brand-emerald bg-brand-emerald/10 border-brand-emerald/20", icon: Container },
  idle: { label: "Idle", color: "text-white/40 bg-white/5 border-white/10", icon: Pause },
};

/**
 * Decoy environment status cards for the dashboard.
 */
export default function DecoyStatusCard() {
  return (
    <GlassPanel className="p-5">
      <div className="flex items-center justify-between mb-4">
        <span className="font-display text-[10px] tracking-widest text-white/50 uppercase">
          Decoy Environments
        </span>
        <span className="text-[9px] text-brand-emerald/80 font-mono">
          {decoyEnvironments.filter((d) => d.state !== "idle").length} Active
        </span>
      </div>

      <div className="space-y-3">
        {decoyEnvironments.map((decoy) => {
          const config = stateConfig[decoy.state];
          const Icon = config.icon;
          return (
            <div
              key={decoy.id}
              className="flex items-center justify-between py-3 border-b border-white/5 last:border-0"
            >
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center">
                  <Icon className="w-4 h-4 text-white/50" />
                </div>
                <div className="flex flex-col">
                  <span className="text-[11px] text-white/80 font-medium font-mono">
                    {decoy.name}
                  </span>
                  <span className="text-[9px] text-white/30">
                    {decoy.activeSessions} sessions · Uptime {decoy.uptime}
                  </span>
                </div>
              </div>

              <span
                className={cn(
                  "text-[8px] font-bold px-2.5 py-1 rounded border uppercase",
                  config.color
                )}
              >
                {config.label}
              </span>
            </div>
          );
        })}
      </div>
    </GlassPanel>
  );
}
