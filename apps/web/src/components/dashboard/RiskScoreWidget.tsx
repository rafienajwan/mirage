"use client";

import React, { useSyncExternalStore } from "react";
import GlassPanel from "@/components/ui/GlassPanel";
import { riskScoreSnapshot, riskHistory } from "@/lib/mock-data";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { ShieldAlert } from "lucide-react";

// SSR-safe mount detection — no setState needed
const subscribe = () => () => {};
const getSnapshot = () => true;
const getServerSnapshot = () => false;

/**
 * Circular gauge + mini sparkline showing the current overall risk score.
 */
export default function RiskScoreWidget() {
  const mounted = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  const { score, label, color } = riskScoreSnapshot;
  const circumference = 2 * Math.PI * 40;
  const offset = circumference - (score / 100) * circumference;

  return (
    <GlassPanel className="p-5">
      <div className="flex items-center justify-between mb-4">
        <span className="font-display text-[10px] tracking-widest text-white/50 uppercase">
          AI Risk Score
        </span>
        <ShieldAlert className="w-4 h-4 text-amber-400/60" />
      </div>

      <div className="flex items-center gap-6">
        {/* Circular gauge */}
        <div className="relative flex-shrink-0">
          <svg viewBox="0 0 100 100" className="w-24 h-24 -rotate-90">
            <circle cx="50" cy="50" r="40" fill="transparent" stroke="rgba(255,255,255,0.05)" strokeWidth="6" />
            <circle
              cx="50"
              cy="50"
              r="40"
              fill="transparent"
              stroke={color}
              strokeWidth="6"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              className="transition-all duration-1000 ease-out"
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-xl font-bold font-display text-white">{score}</span>
            <span className="text-[8px] text-white/40 uppercase tracking-widest">Risk</span>
          </div>
        </div>

        {/* Mini sparkline */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <span
              className="text-[10px] font-bold px-2 py-0.5 rounded border"
              style={{
                color,
                borderColor: `${color}33`,
                backgroundColor: `${color}15`,
              }}
            >
              {label}
            </span>
          </div>
          <div className="h-[48px] w-full">
            {mounted && (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={riskHistory} margin={{ top: 2, right: 2, left: 2, bottom: 0 }}>
                <defs>
                  <linearGradient id="riskSparkline" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={color} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={color} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="time" hide />
                <YAxis domain={[0, 100]} hide />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "rgba(6, 8, 22, 0.95)",
                    borderColor: "rgba(245, 158, 11, 0.2)",
                    fontSize: "10px",
                    borderRadius: "6px",
                    color: "#fff",
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="score"
                  stroke={color}
                  strokeWidth={1.5}
                  fillOpacity={1}
                  fill="url(#riskSparkline)"
                />
              </AreaChart>
            </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>
    </GlassPanel>
  );
}
