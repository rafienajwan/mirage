"use client";

import React from "react";
import { motion } from "framer-motion";
import Header from "@/components/layout/Header";
import VideoBackground from "@/components/landing/VideoBackground";
import HeroContent from "@/components/landing/HeroContent";
import FloatingIntelCard from "@/components/landing/FloatingIntelCard";
import { RiskScoreWidget } from "@/components/landing/SecurityWidgets";
import { Terminal } from "lucide-react";

export default function Home() {
  return (
    <div className="relative min-h-screen flex flex-col bg-[#060816] text-white selection:bg-brand-cyan/30 selection:text-white overflow-hidden">
      {/* Fullscreen cinematic HLS video background */}
      <VideoBackground />

      {/* Header */}
      <Header />

      {/* Main Container */}
      <main className="flex-1 w-full max-w-[1400px] mx-auto px-6 relative z-10 flex flex-col justify-between pt-24 md:pt-28 pb-16 lg:pb-32">
        {/* Hero Section Container */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center lg:min-h-[calc(100vh-320px)] mt-0">
          {/* Left Column Widgets */}
          <div className="hidden md:flex lg:col-span-3 flex-col items-center lg:items-start gap-8 order-2 lg:order-1 w-full max-w-[220px] lg:max-w-none mx-auto lg:mx-0">
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.8, delay: 0.35 }}
              className="w-full flex justify-center lg:justify-start"
            >
              <FloatingIntelCard />
            </motion.div>
          </div>

          {/* Central Hero Content */}
          <div className="col-span-1 lg:col-span-6 flex flex-col items-center justify-center order-1 lg:order-2 py-6 lg:py-0">
            <HeroContent />
          </div>

          {/* Right Column Widgets */}
          <div className="hidden md:flex lg:col-span-3 flex-col items-center lg:items-end order-3 w-full max-w-[220px] lg:max-w-none mx-auto lg:mx-0">
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0, y: [0, 6, 0] }}
              transition={{
                opacity: { duration: 1, delay: 0.45 },
                x: { duration: 1, delay: 0.45 },
                y: { duration: 8, repeat: Infinity, ease: "easeInOut", delay: 1.5 },
              }}
              className="w-full flex justify-center lg:justify-end"
            >
              <RiskScoreWidget />
            </motion.div>
          </div>
        </div>

        {/* Footer Technical Accents */}
        <div className="mt-24 lg:mt-32 flex flex-col md:flex-row items-center justify-between text-[8px] font-mono tracking-widest text-white/20 border-t border-white/5 pt-6 gap-4">
          <div className="flex items-center space-x-2">
            <Terminal className="w-3.5 h-3.5 text-brand-cyan/60" />
            <span>PROJECT MIRAGE // API DECEPTION GATEWAY</span>
          </div>
        </div>
      </main>
    </div>
  );
}
