"use client";

import React, { useState } from "react";
import GlassPanel from "@/components/ui/GlassPanel";
import { simulateNormal, simulateSuspicious } from "@/lib/api";
import type { SimulationResult } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Play, Zap, Loader2, CheckCircle, XCircle } from "lucide-react";

interface SimulationPanelProps {
  /** Called after a simulation completes so the dashboard can refresh its data. */
  onRefresh?: () => void;
}

/**
 * Simulation trigger panel — lets operators generate demo events
 * directly from the dashboard.
 */
export default function SimulationPanel({ onRefresh }: SimulationPanelProps) {
  const [loading, setLoading] = useState<"normal" | "suspicious" | null>(null);
  const [lastResult, setLastResult] = useState<SimulationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSimulate(type: "normal" | "suspicious") {
    setLoading(type);
    setError(null);
    setLastResult(null);
    try {
      const result = type === "normal" ? await simulateNormal() : await simulateSuspicious();
      setLastResult(result);
      onRefresh?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Simulation failed");
    } finally {
      setLoading(null);
    }
  }

  const isRedirected = lastResult?.decision === "redirect_to_decoy";

  return (
    <GlassPanel className="p-4">
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
        {/* Label */}
        <div className="flex-1 min-w-0">
          <span className="font-display text-[10px] tracking-widest text-white/50 uppercase">
            Traffic Simulation
          </span>
          <p className="text-[10px] text-white/30 mt-0.5 font-mono">
            Generate demo events to populate the dashboard
          </p>
        </div>

        {/* Buttons */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={() => handleSimulate("normal")}
            disabled={loading !== null}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[10px] font-mono font-bold",
              "border transition-all",
              "border-brand-emerald/30 text-brand-emerald bg-brand-emerald/5",
              "hover:bg-brand-emerald/15 hover:border-brand-emerald/50",
              "disabled:opacity-40 disabled:cursor-not-allowed"
            )}
          >
            {loading === "normal" ? (
              <Loader2 className="w-3 h-3 animate-spin" />
            ) : (
              <Play className="w-3 h-3" />
            )}
            Normal Traffic
          </button>

          <button
            onClick={() => handleSimulate("suspicious")}
            disabled={loading !== null}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[10px] font-mono font-bold",
              "border transition-all",
              "border-red-500/30 text-red-400 bg-red-500/5",
              "hover:bg-red-500/15 hover:border-red-500/50",
              "disabled:opacity-40 disabled:cursor-not-allowed"
            )}
          >
            {loading === "suspicious" ? (
              <Loader2 className="w-3 h-3 animate-spin" />
            ) : (
              <Zap className="w-3 h-3" />
            )}
            Simulate Attack
          </button>
        </div>
      </div>

      {/* Last result */}
      {lastResult && (
        <div
          className={cn(
            "mt-3 flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 p-3 rounded-md border text-[10px] font-mono",
            isRedirected
              ? "border-red-500/20 bg-red-500/5 text-red-300"
              : "border-brand-emerald/20 bg-brand-emerald/5 text-brand-emerald"
          )}
        >
          <div className="flex items-center gap-1.5">
            {isRedirected ? (
              <XCircle className="w-3.5 h-3.5" />
            ) : (
              <CheckCircle className="w-3.5 h-3.5" />
            )}
            <span className="font-bold uppercase">{lastResult.decision.replace(/_/g, " ")}</span>
          </div>
          <div className="flex items-center gap-3 text-white/50">
            <span>
              Risk: <span className="text-white/80">{lastResult.riskScore.toFixed(1)}/100</span>
            </span>
            <span>
              Level: <span className="text-white/80 capitalize">{lastResult.riskLevel}</span>
            </span>
            <span>
              ID: <span className="text-white/60">{lastResult.requestId}</span>
            </span>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mt-3 p-3 rounded-md border border-amber-500/20 bg-amber-500/5 text-[10px] font-mono text-amber-400">
          {error}
          <span className="text-white/30 ml-2">
            — make sure the backend is running on port 8000
          </span>
        </div>
      )}
    </GlassPanel>
  );
}
