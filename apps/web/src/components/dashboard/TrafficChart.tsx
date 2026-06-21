"use client";

import React, { useSyncExternalStore } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import GlassPanel from "@/components/ui/GlassPanel";
import { trafficData } from "@/lib/mock-data";

// SSR-safe mount detection — no setState needed
const subscribe = () => () => {};
const getSnapshot = () => true;
const getServerSnapshot = () => false;

/**
 * Live traffic area chart for the dashboard.
 * Uses useSyncExternalStore to safely defer chart render until after mount.
 */
export default function TrafficChart() {
  const mounted = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  return (
    <GlassPanel className="p-5">
      <div className="flex items-center justify-between mb-4">
        <span className="font-display text-[10px] tracking-widest text-white/50 uppercase">
          Traffic Overview
        </span>
        <div className="flex items-center gap-3 text-[9px] text-white/40">
          <span className="flex items-center gap-1">
            <span className="w-2 h-[2px] rounded-full bg-brand-cyan" />
            Normal
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-[2px] rounded-full bg-red-400" />
            Suspicious
          </span>
        </div>
      </div>

      {/* Explicit height container for Recharts */}
      <div className="h-[240px] w-full">
        {mounted && (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={trafficData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="dashNormal" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#00f0ff" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#00f0ff" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="dashSuspicious" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f87171" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#f87171" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="time"
                stroke="rgba(255,255,255,0.1)"
                fontSize={10}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                stroke="rgba(255,255,255,0.1)"
                fontSize={10}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "rgba(6, 8, 22, 0.95)",
                  borderColor: "rgba(0, 240, 255, 0.15)",
                  fontSize: "11px",
                  borderRadius: "8px",
                  color: "#fff",
                }}
              />
              <Area
                type="monotone"
                dataKey="normal"
                stroke="#00f0ff"
                strokeWidth={1.5}
                fillOpacity={1}
                fill="url(#dashNormal)"
                name="Normal Traffic"
              />
              <Area
                type="monotone"
                dataKey="suspicious"
                stroke="#f87171"
                strokeWidth={1.5}
                fillOpacity={1}
                fill="url(#dashSuspicious)"
                name="Suspicious Traffic"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </GlassPanel>
  );
}
