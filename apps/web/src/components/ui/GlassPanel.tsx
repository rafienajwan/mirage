import React from "react";
import { cn } from "@/lib/utils";

interface GlassPanelProps {
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "cyan" | "emerald";
}

/**
 * Reusable glassmorphism panel with soft borders and backdrop blur.
 * Variants control the accent tint.
 */
export default function GlassPanel({
  children,
  className,
  variant = "default",
}: GlassPanelProps) {
  const base =
    "rounded-xl backdrop-blur-xl border shadow-[inset_0_1px_1px_rgba(255,255,255,0.05),0_10px_30px_rgba(0,0,0,0.5)]";

  const variants = {
    default: "bg-white/[0.02] border-white/[0.05]",
    cyan: "bg-[rgba(0,240,255,0.015)] border-[rgba(0,240,255,0.15)]",
    emerald: "bg-[rgba(94,210,156,0.015)] border-[rgba(94,210,156,0.15)]",
  };

  return (
    <div className={cn(base, variants[variant], className)}>
      {children}
    </div>
  );
}
