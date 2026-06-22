"use client";

import React from "react";
import { motion } from "framer-motion";
import { ArrowRight, Compass } from "lucide-react";
import Link from "next/link";

export default function HeroContent() {
  return (
    <div className="relative flex flex-col items-center text-center max-w-5xl mx-auto z-10 px-4 pt-0">
      
      {/* Eyebrow Text */}
      <motion.span
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.2 }}
        className="font-display text-[9px] sm:text-[10px] md:text-xs font-bold tracking-[0.25em] sm:tracking-[0.3em] text-[#5ed29c] uppercase mb-3"
      >
        AI-DRIVEN CYBER DECEPTION PLATFORM
      </motion.span>

      {/* Main Headline */}
      <motion.h1
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, delay: 0.3 }}
        className="font-sans font-black text-4xl sm:text-6xl md:text-8xl lg:text-[115px] text-white tracking-[-0.04em] leading-[0.9] lg:leading-[0.88] uppercase select-none mb-6"
      >
        DETECT. DECEIVE.{" "}
        <span className="bg-gradient-to-r from-white via-white to-brand-emerald bg-clip-text text-transparent">
          DEFEND
        </span>
        <span className="text-[#5ed29c] text-glow-emerald">.</span>
      </motion.h1>

      {/* Subheadline / Description */}
      <motion.p
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.4 }}
        className="text-xs sm:text-sm lg:text-[15px] leading-relaxed text-white/60 max-w-[90%] sm:max-w-[550px] lg:max-w-[640px] font-sans font-light tracking-wide mb-8"
      >
        Project MIRAGE detects suspicious API requests, redirects attackers into safe decoy
        environments, records their behavior, and helps defenders respond faster through a
        security dashboard.
      </motion.p>

      {/* CTAs */}
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.5 }}
        className="flex flex-col sm:flex-row items-center justify-center gap-3 sm:gap-4 w-full sm:w-auto px-4 sm:px-0"
      >
        {/* Primary CTA */}
        <Link
          href="/dashboard"
          className="group relative w-full sm:w-auto px-8 py-3.5 rounded-full bg-[#5ed29c] text-[#060816] font-display text-[10px] font-bold tracking-widest uppercase flex items-center justify-center space-x-2 transition-all duration-300 hover:scale-[1.02] hover:shadow-[0_0_25px_rgba(94,210,156,0.4)]"
        >
          <span>View Dashboard</span>
          <ArrowRight className="w-4 h-4 transition-transform duration-300 group-hover:translate-x-1" />
        </Link>

        {/* Secondary CTA */}
        <Link
          href="/dashboard"
          className="relative w-full sm:w-auto px-8 py-3.5 rounded-full border border-white/5 hover:border-brand-cyan/20 bg-white/[0.01] hover:bg-brand-cyan/[0.02] backdrop-blur-sm font-display text-[10px] font-bold tracking-widest text-white/60 hover:text-brand-cyan uppercase flex items-center justify-center space-x-2 transition-all duration-300 hover:shadow-[0_0_15px_rgba(0,240,255,0.1)]"
        >
          <Compass className="w-4 h-4 text-white/40" />
          <span>Explore Demo Flow</span>
        </Link>
      </motion.div>
      
    </div>
  );
}
