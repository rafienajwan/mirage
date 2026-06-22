"use client";

import React from "react";
import GlassPanel from "@/components/ui/GlassPanel";
import type { DecoyStatusData } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Shield } from "lucide-react";

interface DecoyStatusCardProps {
  data: DecoyStatusData | null;
}

/**
 * Decoy environment status card for the dashboard.
 * Displays live data from the backend decoy status endpoint.
 */
export default function DecoyStatusCard({ data }: DecoyStatusCardProps) {
  const endpoints = data?.fakeEndpoints ?? [];
  const activeCount = data?.activeDecoys ?? 0;
  const captured = data?.capturedInteractions ?? 0;
  const lastTrigger = data?.lastDecoyTrigger
    ? new Date(data.lastDecoyTrigger).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : null;

  return (
    <GlassPanel className="p-5">
      <div className="flex items-center justify-between mb-4">
        <span className="font-display text-[10px] tracking-widest text-white/50 uppercase">
          Decoy Environments
        </span>
        <div className="flex items-center gap-3">
          <span className="text-[9px] text-brand-emerald/80 font-mono">
            {activeCount} Active
          </span>
          <span className="text-[9px] text-white/30 font-mono">
            {captured} Captured
          </span>
        </div>
      </div>

      {endpoints.length > 0 ? (
        <div className="space-y-3">
          {endpoints.map((endpoint, i) => (
            <div
              key={endpoint}
              className="flex items-center justify-between py-3 border-b border-white/5 last:border-0"
            >
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center">
                  <Shield className="w-4 h-4 text-white/50" />
                </div>
                <div className="flex flex-col">
                  <span className="text-[11px] text-white/80 font-medium font-mono">
                    {endpoint}
                  </span>
                  <span className="text-[9px] text-white/30">
                    ENV_{String(i + 1).padStart(2, "0")}
                  </span>
                </div>
              </div>

              <span
                className={cn(
                  "text-[8px] font-bold px-2.5 py-1 rounded border uppercase",
                  "text-brand-cyan bg-brand-cyan/10 border-brand-cyan/20"
                )}
              >
                Active
              </span>
            </div>
          ))}
        </div>
      ) : (
        <div className="h-32 flex items-center justify-center text-white/30 text-xs">
          No decoy endpoints configured
        </div>
      )}

      {lastTrigger && (
        <div className="mt-4 pt-3 border-t border-white/5 flex items-center justify-between">
          <span className="text-[9px] text-white/30">Last decoy trigger</span>
          <span className="text-[9px] text-white/50 font-mono">{lastTrigger}</span>
        </div>
      )}
    </GlassPanel>
  );
}
