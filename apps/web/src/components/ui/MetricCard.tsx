import React from "react";
import { cn } from "@/lib/utils";
import GlassPanel from "@/components/ui/GlassPanel";
import { formatNumber } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

interface MetricCardProps {
  label: string;
  value: number;
  icon: LucideIcon;
  accentColor?: "cyan" | "emerald" | "red" | "amber";
  className?: string;
}

const accentMap = {
  cyan: { text: "text-brand-cyan", bg: "bg-brand-cyan/10", border: "border-brand-cyan/20" },
  emerald: { text: "text-brand-emerald", bg: "bg-brand-emerald/10", border: "border-brand-emerald/20" },
  red: { text: "text-red-400", bg: "bg-red-500/10", border: "border-red-500/20" },
  amber: { text: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/20" },
};

/**
 * Dashboard metric card showing a single KPI with icon and label.
 */
export default function MetricCard({
  label,
  value,
  icon: Icon,
  accentColor = "cyan",
  className,
}: MetricCardProps) {
  const accent = accentMap[accentColor];

  return (
    <GlassPanel className={cn("p-5 flex flex-col justify-between h-full", className)}>
      <div className="flex items-center justify-between mb-4">
        <span className="font-display text-[10px] tracking-widest text-white/40 uppercase">
          {label}
        </span>
        <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center", accent.bg, accent.border, "border")}>
          <Icon className={cn("w-4 h-4", accent.text)} />
        </div>
      </div>
      <span className={cn("text-2xl font-bold font-display", accent.text)}>
        {formatNumber(value)}
      </span>
    </GlassPanel>
  );
}
