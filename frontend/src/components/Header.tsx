"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Shield, Menu, X, Terminal } from "lucide-react";

const NAV_ITEMS = [
  { name: "PLATFORM", href: "#platform" },
  { name: "THREATS", href: "#threats" },
  { name: "FEATURES", href: "#features" },
  { name: "ARCHITECTURE", href: "#architecture" },
  { name: "DOCUMENTATION", href: "#docs" },
];

export default function Header() {
  const [isOpen, setIsOpen] = useState(false);
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  return (
    <header className="sticky top-0 w-full z-50 border-b border-white/5 bg-[#060816]/65 backdrop-blur-md">
      <div className="max-w-[1400px] mx-auto px-6 h-20 flex items-center justify-between">

        {/* Logo */}
        <a href="#" className="flex items-center space-x-3 group z-50">
          <div className="relative flex items-center justify-center w-10 h-10 rounded-lg border border-brand-cyan/20 bg-brand-cyan/5 overflow-hidden">
            {/* Pulsing neon center */}
            <div className="absolute inset-0 bg-brand-cyan/10 animate-pulse" />
            <Shield className="w-5 h-5 text-brand-cyan relative z-10 transition-transform duration-300 group-hover:scale-110" />
            {/* Technical corners */}
            <div className="absolute top-0 left-0 w-1.5 h-1.5 border-t border-l border-brand-cyan" />
            <div className="absolute bottom-0 right-0 w-1.5 h-1.5 border-b border-r border-brand-cyan" />
          </div>
          <span className="font-display font-bold text-lg tracking-widest text-white flex items-center">
            Project MIRAGE
            <span className="text-brand-emerald ml-0.5 animate-pulse">_</span>
          </span>
        </a>

        {/* Desktop Navigation */}
        <nav className="hidden lg:flex items-center space-x-1 lg:space-x-3">
          {NAV_ITEMS.map((item, idx) => (
            <a
              key={item.name}
              href={item.href}
              className="relative px-4 py-2 font-display text-[10px] font-normal tracking-[0.2em] text-white/50 hover:text-brand-cyan transition-colors duration-300"
              onMouseEnter={() => setHoveredIdx(idx)}
              onMouseLeave={() => setHoveredIdx(null)}
            >
              <span className="relative z-10">{item.name}</span>
              {hoveredIdx === idx && (
                <motion.span
                  layoutId="navUnderline"
                  className="absolute bottom-0 left-4 right-4 h-[1px] bg-gradient-to-r from-brand-cyan to-brand-emerald shadow-[0_0_6px_rgba(0,240,255,0.4)]"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ type: "spring", stiffness: 350, damping: 30 }}
                />
              )}
            </a>
          ))}
        </nav>

        {/* CTA Button */}
        <div className="hidden lg:flex items-center space-x-4">
          <a
            href="#terminal"
            className="flex items-center space-x-1.5 font-display text-[10px] tracking-widest text-brand-cyan hover:text-white transition-colors border border-brand-cyan/20 hover:border-brand-cyan/40 bg-brand-cyan/5 px-3 py-1.5 rounded"
          >
            <Terminal className="w-3.5 h-3.5" />
            <span>SYS_STATUS: ACTIVE</span>
          </a>
        </div>

        {/* Mobile Hamburger Button */}
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="lg:hidden p-2 text-white/80 hover:text-brand-cyan transition-colors z-50 focus:outline-none"
          aria-label="Toggle Menu"
        >
          {isOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>

      </div>

      {/* Mobile Fullscreen Navigation Overlay */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.3, ease: "easeInOut" }}
            className="fixed inset-0 bg-[#060816]/95 backdrop-blur-xl z-40 flex flex-col justify-center items-center px-8"
          >
            {/* Tech grid detail for mobile overlay background */}
            <div className="absolute inset-0 grid-lines-h opacity-20 pointer-events-none" />
            <div className="absolute inset-0 glow-spot-cyan opacity-40 pointer-events-none" />

            <div className="flex flex-col space-y-6 text-center">
              {NAV_ITEMS.map((item, idx) => (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.05 }}
                  key={item.name}
                >
                  <a
                    href={item.href}
                    onClick={() => setIsOpen(false)}
                    className="group relative block font-display text-lg tracking-widest text-white/80 hover:text-brand-cyan transition-colors py-2"
                  >
                    {item.name}
                    <span className="block max-w-0 group-hover:max-w-full transition-all duration-300 h-[2px] bg-gradient-to-r from-brand-cyan to-brand-emerald mx-auto mt-1" />
                  </a>
                </motion.div>
              ))}
            </div>

            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.3 }}
              className="mt-16 w-full max-w-xs flex flex-col space-y-4"
            >
              <div className="text-center font-display text-[10px] tracking-widest text-brand-emerald py-2 border border-brand-emerald/20 bg-brand-emerald/5 rounded">
                SECURE ACCESS LOGGED
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
