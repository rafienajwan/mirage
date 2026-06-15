"use client";

import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Cpu } from "lucide-react";

export default function FloatingIntelCard() {
  const [redirectedCount, setRedirectedCount] = useState(48);

  // Animate stats counter slightly to represent live threat environment
  useEffect(() => {
    const interval = setInterval(() => {
      setRedirectedCount((prev) => {
        // Occasionally increment to simulate live threat mitigation
        if (Math.random() > 0.7) {
          return prev + 1;
        }
        return prev;
      });
    }, 4500);

    return () => clearInterval(interval);
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0, y: 0, x: 0 }}
      animate={{ 
        opacity: 1, 
        y: [0, -10, 0],
        x: 0
      }}
      transition={{
        opacity: { duration: 0.8 },
        y: { 
          duration: 8,
          repeat: Infinity,
          ease: "easeInOut",
        }
      }}
      className="relative w-[220px] h-[190px] rounded-xl overflow-hidden backdrop-blur-xl border border-white/5 bg-white/[0.01] shadow-[inset_0_1px_1px_rgba(255,255,255,0.02),0_8px_24px_rgba(0,0,0,0.4)] z-20 flex flex-col justify-between p-4.5 pointer-events-auto"
    >
      {/* Decorative top border gradient (softer neon glow) */}
      <div className="absolute top-0 inset-x-0 h-[1px] bg-gradient-to-r from-brand-cyan/40 via-brand-cyan/60 to-brand-emerald/40" />
      
      {/* Technical corner grids */}
      <div className="absolute top-0 right-0 w-1.5 h-1.5 border-t border-r border-brand-cyan/30" />
      <div className="absolute bottom-0 left-0 w-1.5 h-1.5 border-b border-l border-brand-emerald/30" />

      {/* Card Header */}
      <div className="flex items-center justify-between">
        <span className="font-display text-[8px] tracking-[0.15em] text-brand-emerald bg-brand-emerald/5 border border-brand-emerald/10 px-2 py-0.5 rounded flex items-center font-normal">
          <span className="w-1 h-1 rounded-full bg-brand-emerald mr-1.5 animate-pulse" />
          AI ACTIVE
        </span>
        <Cpu className="w-3.5 h-3.5 text-brand-cyan/60" />
      </div>

      {/* Title & Copy */}
      <div className="my-1">
        <h3 className="font-display text-[11px] font-medium text-white/90 tracking-wide">
          Autonomous Threat Hunting
        </h3>
        <p className="text-[8px] leading-relaxed text-white/50 mt-1 font-sans font-light">
          AI engine analyzes suspicious traffic, redirects attackers into decoy environments, and logs threat intelligence.
        </p>
      </div>

      {/* Stats Section */}
      <div className="grid grid-cols-3 gap-1 pt-1.5 border-t border-white/5">
        <div className="flex flex-col">
          <span className="text-[10px] font-medium text-brand-cyan/90 font-display">
            {redirectedCount}
          </span>
          <span className="text-[6.5px] text-white/30 tracking-wider uppercase font-light">
            Redirected
          </span>
        </div>
        <div className="flex flex-col">
          <span className="text-[10px] font-medium text-white/95 font-display">
            92%
          </span>
          <span className="text-[6.5px] text-white/30 tracking-wider uppercase font-light">
            Accuracy
          </span>
        </div>
        <div className="flex flex-col">
          <span className="text-[10px] font-medium text-brand-emerald/90 font-display">
            17
          </span>
          <span className="text-[6.5px] text-white/30 tracking-wider uppercase font-light">
            Protected
          </span>
        </div>
      </div>
    </motion.div>
  );
}
