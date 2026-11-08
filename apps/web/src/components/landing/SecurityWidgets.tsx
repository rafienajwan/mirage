"use client";

import { motion } from "framer-motion";
import { ShieldAlert } from "lucide-react";

/**
 * Landing illustration of the risk scale. Shows the scale and band edge the
 * gateway really uses, not a live value.
 */
export function RiskScoreWidget() {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.6, delay: 0.1 }}
      className="w-full md:w-[180px] lg:w-[210px] p-3 lg:p-3.5 flex flex-col justify-between h-[145px] lg:h-[160px] relative overflow-hidden backdrop-blur-xl border border-white/3 bg-white/[0.005] shadow-2xl rounded-xl opacity-25 hover:opacity-85 hover:border-white/10 hover:bg-white/[0.015] transition-all duration-500 select-none group"
    >
      <div className="absolute top-0 right-0 w-6 h-6 opacity-5 bg-brand-cyan rounded-bl-full pointer-events-none" />
      
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="font-display text-[7.5px] lg:text-[8px] tracking-widest text-white/40 uppercase">
          Risk Scoring
        </span>
      </div>

      {/* Circle Gauge */}
      <div className="flex items-center justify-center my-1 relative">
        <svg viewBox="0 0 64 64" className="w-13 h-13 lg:w-16 lg:h-16 transform -rotate-90">
          {/* Base Track */}
          <circle
            cx="32"
            cy="32"
            r="26"
            className="stroke-white/5 fill-transparent"
            strokeWidth="4"
          />
          {/* Active Gradient Dash */}
          <circle
            cx="32"
            cy="32"
            r="26"
            className="stroke-red-500/80 fill-transparent transition-all duration-1000 ease-out"
            strokeWidth="4"
            strokeDasharray="163.36" // 2 * PI * r
            strokeDashoffset="32.67" // filled to 80, where the critical band starts
            strokeLinecap="round"
          />
        </svg>

        {/* Inner Text */}
        <div className="absolute flex flex-col items-center justify-center">
          <span className="text-xs lg:text-sm font-bold font-display leading-none text-white/90">0-100</span>
          <span className="text-[6px] lg:text-[7px] text-white/30 uppercase tracking-widest mt-0.5">Scale</span>
        </div>
      </div>

      {/* Footer Info */}
      <div className="flex justify-between items-center text-[7.5px] lg:text-[8px]">
        <span className="text-white/40 flex items-center">
          <ShieldAlert className="w-2.5 h-2.5 lg:w-3 lg:h-3 text-red-500/60 mr-1" />
          Critical from 80
        </span>
      </div>
    </motion.div>
  );
}
