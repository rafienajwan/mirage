"use client";

import React from "react";
import GlassPanel from "@/components/ui/GlassPanel";
import { alerts } from "@/lib/mock-data";
import type { AlertSeverity } from "@/lib/mock-data";
import { cn } from "@/lib/utils";
import { Bell, Info, AlertTriangle, ShieldAlert } from "lucide-react";

const severityConfig: Record<AlertSeverity, { color: string; icon: typeof Bell }> = {
  info: { color: "text-brand-cyan border-brand-cyan/20 bg-brand-cyan/5", icon: Info },
  warning: { color: "text-amber-400 border-amber-500/20 bg-amber-500/5", icon: AlertTriangle },
  critical: { color: "text-red-400 border-red-500/20 bg-red-500/5", icon: ShieldAlert },
};

/**
 * Alert panel with severity labels for the dashboard.
 */
export default function AlertPanel() {
  const unacknowledged = alerts.filter((a) => !a.acknowledged);

  return (
    <GlassPanel className="p-5">
      <div className="flex items-center justify-between mb-4">
        <span className="font-display text-[10px] tracking-widest text-white/50 uppercase flex items-center gap-2">
          <Bell className="w-3.5 h-3.5" />
          Alerts
        </span>
        <span className="text-[9px] font-mono text-red-400/80">
          {unacknowledged.length} Unacknowledged
        </span>
      </div>

      <div className="space-y-2">
        {alerts.map((alert) => {
          const config = severityConfig[alert.severity];
          const Icon = config.icon;
          return (
            <div
              key={alert.id}
              className={cn(
                "flex items-start gap-3 p-3 rounded-lg border transition-opacity",
                alert.acknowledged ? "opacity-50" : "opacity-100",
                config.color
              )}
            >
              <Icon className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-[11px] text-white/80 leading-relaxed">
                  {alert.message}
                </p>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-[8px] text-white/30 font-mono uppercase">
                    {alert.severity}
                  </span>
                  <span className="text-[8px] text-white/20">·</span>
                  <span className="text-[8px] text-white/30">
                    {new Date(alert.timestamp).toLocaleTimeString("en-US", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </GlassPanel>
  );
}
