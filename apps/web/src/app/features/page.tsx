"use client";

import { motion } from "framer-motion";
import Header from "@/components/layout/Header";
import VideoBackground from "@/components/landing/VideoBackground";
import { Brain, Layers, KeyRound, LineChart, Terminal } from "lucide-react";
import Link from "next/link";

export default function FeaturesPage() {
  return (
    <div className="relative min-h-screen flex flex-col bg-bg-dark-navy text-white selection:bg-brand-cyan/30 selection:text-white overflow-x-hidden">
      {/* Fullscreen cinematic HLS video background */}
      <VideoBackground />

      {/* Header */}
      <Header />

      {/* Main Container */}
      <main className="flex-1 w-full max-w-350 mx-auto px-6 relative z-10 flex flex-col gap-24 pt-28 pb-16">
        
        {/* Features Section */}
        <section id="features" className="scroll-mt-24 pt-8">
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="flex flex-col items-center text-center mb-16"
          >
            <span className="font-display text-[9px] sm:text-[10px] font-bold tracking-[0.25em] text-brand-emerald uppercase mb-2">
              DECEPTION CAPABILITIES
            </span>
            <h1 className="font-sans font-black text-3xl sm:text-5xl lg:text-6xl text-white tracking-[-0.03em] uppercase mb-4">
              ACTIVE CYBER DECEPTION LAYERS
            </h1>
            <div className="h-0.5 w-24 scan-line" />
            <p className="text-xs sm:text-sm text-white/50 max-w-xl mt-4 leading-relaxed">
              MIRAGE shifts your security posture from passive firewalls to active deception campaigns, detaining attackers inside synthetic environments.
            </p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {/* Feature 1 */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.1 }}
              whileHover={{ y: -6, scale: 1.01 }}
              className="relative p-6 rounded-xl border border-brand-cyan/10 bg-brand-cyan/1 hover:bg-brand-cyan/2 backdrop-blur-md overflow-hidden group transition-all duration-300 hover:shadow-[0_0_20px_rgba(0,240,255,0.08)]"
            >
              <div className="absolute top-0 left-0 w-2 h-0.5 bg-brand-cyan" />
              <div className="absolute top-0 left-0 w-0.5 h-2 bg-brand-cyan" />
              <div className="w-10 h-10 rounded-lg flex items-center justify-center bg-brand-cyan/5 border border-brand-cyan/20 mb-4 group-hover:scale-110 transition-transform duration-300">
                <Brain className="w-5 h-5 text-brand-cyan" />
              </div>
              <h3 className="font-display font-bold text-xs sm:text-sm text-white uppercase tracking-wider mb-2">
                AI Risk Scoring
              </h3>
              <p className="text-[11px] sm:text-xs text-white/50 leading-relaxed">
                Analyzes request headers, parameters, and body payloads in real-time. The anomaly detector instantly identifies zero-day exploit patterns.
              </p>
            </motion.div>

            {/* Feature 2 */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
              whileHover={{ y: -6, scale: 1.01 }}
              className="relative p-6 rounded-xl border border-brand-emerald/10 bg-brand-emerald/1 hover:bg-brand-emerald/2 backdrop-blur-md overflow-hidden group transition-all duration-300 hover:shadow-[0_0_20px_rgba(94,210,156,0.08)]"
            >
              <div className="absolute top-0 left-0 w-2 h-0.5 bg-brand-emerald" />
              <div className="absolute top-0 left-0 w-0.5 h-2 bg-brand-emerald" />
              <div className="w-10 h-10 rounded-lg flex items-center justify-center bg-brand-emerald/5 border border-brand-emerald/20 mb-4 group-hover:scale-110 transition-transform duration-300">
                <Layers className="w-5 h-5 text-brand-emerald" />
              </div>
              <h3 className="font-display font-bold text-xs sm:text-sm text-white uppercase tracking-wider mb-2">
                Dynamic Decoys
              </h3>
              <p className="text-[11px] sm:text-xs text-white/50 leading-relaxed">
                Automatically redirects suspicious requests to a sandbox decoy environment. Attackers spend resources on fake databases and mock APIs without knowing.
              </p>
            </motion.div>

            {/* Feature 3 */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.3 }}
              whileHover={{ y: -6, scale: 1.01 }}
              className="relative p-6 rounded-xl border border-amber-500/10 bg-amber-500/1 hover:bg-amber-500/2 backdrop-blur-md overflow-hidden group transition-all duration-300 hover:shadow-[0_0_20px_rgba(245,158,11,0.08)]"
            >
              <div className="absolute top-0 left-0 w-2 h-0.5 bg-amber-500" />
              <div className="absolute top-0 left-0 w-0.5 h-2 bg-amber-500" />
              <div className="w-10 h-10 rounded-lg flex items-center justify-center bg-amber-500/5 border border-amber-500/20 mb-4 group-hover:scale-110 transition-transform duration-300">
                <KeyRound className="w-5 h-5 text-amber-400" />
              </div>
              <h3 className="font-display font-bold text-xs sm:text-sm text-white uppercase tracking-wider mb-2">
                Canary Honeytokens
              </h3>
              <p className="text-[11px] sm:text-xs text-white/50 leading-relaxed">
                Injects mock credential files (e.g., false AWS tokens). Immediate alerts trigger the moment these honeytokens are exfiltrated and tested.
              </p>
            </motion.div>

            {/* Feature 4 */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.4 }}
              whileHover={{ y: -6, scale: 1.01 }}
              className="relative p-6 rounded-xl border border-red-500/10 bg-red-500/1 hover:bg-red-500/2 backdrop-blur-md overflow-hidden group transition-all duration-300 hover:shadow-[0_0_20px_rgba(239,68,68,0.08)]"
            >
              <div className="absolute top-0 left-0 w-2 h-0.5 bg-red-500" />
              <div className="absolute top-0 left-0 w-0.5 h-2 bg-red-500" />
              <div className="w-10 h-10 rounded-lg flex items-center justify-center bg-red-500/5 border border-red-500/20 mb-4 group-hover:scale-110 transition-transform duration-300">
                <LineChart className="w-5 h-5 text-red-400" />
              </div>
              <h3 className="font-display font-bold text-xs sm:text-sm text-white uppercase tracking-wider mb-2">
                SOC Analytics Dashboard
              </h3>
              <p className="text-[11px] sm:text-xs text-white/50 leading-relaxed">
                Real-time dashboard with comprehensive metrics, attacker fingerprints, and immediate security alerts to accelerate threat mitigation.
              </p>
            </motion.div>
          </div>
        </section>

        {/* Demo Section */}
        <section id="demo" className="scroll-mt-24 py-12 border-t border-white/5 w-full">
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
            className="flex flex-col items-center text-center mb-16"
          >
            <span className="font-display text-[9px] sm:text-[10px] font-bold tracking-[0.25em] text-brand-cyan uppercase mb-2">
              SIMULATION LOGIC
            </span>
            <h2 className="font-sans font-black text-3xl sm:text-5xl text-white tracking-[-0.03em] uppercase mb-4">
              MVP THREAT DEMONSTRATION FLOW
            </h2>
            <div className="h-0.5 w-24 scan-line" />
            <p className="text-xs sm:text-sm text-white/50 max-w-xl mt-4">
              Trigger simulated attacks directly from the control panel to observe the full cycle of threat detection, decoy containment, and forensic analysis.
            </p>
          </motion.div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 max-w-6xl mx-auto w-full">
            {/* Step 1 */}
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.4 }}
              className="relative p-5 rounded-xl border border-white/5 bg-white/1 overflow-hidden flex flex-col justify-between min-h-45"
            >
              <div>
                <span className="font-mono text-2xl font-bold text-white/10 mb-2 block">01</span>
                <h4 className="font-display font-bold text-[10px] sm:text-xs uppercase text-white mb-2">Traffic Entry</h4>
                <p className="text-[11px] text-white/40 leading-relaxed">
                  The client sends a normal API request. The AI inspects the metadata and allows it through to the production database (Low Risk).
                </p>
              </div>
              <div className="text-[9px] font-mono text-brand-emerald bg-brand-emerald/5 border border-brand-emerald/10 px-2 py-0.5 rounded self-start mt-4 uppercase">
                Decision: Allow
              </div>
            </motion.div>

            {/* Step 2 */}
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.5 }}
              className="relative p-5 rounded-xl border border-white/5 bg-white/1 overflow-hidden flex flex-col justify-between min-h-45"
            >
              <div>
                <span className="font-mono text-2xl font-bold text-white/10 mb-2 block">02</span>
                <h4 className="font-display font-bold text-[10px] sm:text-xs uppercase text-white mb-2">Anomaly Detected</h4>
                <p className="text-[11px] text-white/40 leading-relaxed">
                  A suspicious request (e.g., SQL Injection) is detected. The AI engine immediately flags the request and escalates the risk score to critical.
                </p>
              </div>
              <div className="text-[9px] font-mono text-red-400 bg-red-400/5 border border-red-400/10 px-2 py-0.5 rounded self-start mt-4 uppercase">
                Risk Score &gt;= 0.65
              </div>
            </motion.div>

            {/* Step 3 */}
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.6 }}
              className="relative p-5 rounded-xl border border-white/5 bg-white/1 overflow-hidden flex flex-col justify-between min-h-45"
            >
              <div>
                <span className="font-mono text-2xl font-bold text-white/10 mb-2 block">03</span>
                <h4 className="font-display font-bold text-[10px] sm:text-xs uppercase text-white mb-2">Active Decoy</h4>
                <p className="text-[11px] text-white/40 leading-relaxed">
                  The connection is transparently redirected to the decoy sandbox. The attacker interacts with mock endpoints, believing they bypassed security.
                </p>
              </div>
              <div className="text-[9px] font-mono text-brand-cyan bg-brand-cyan/5 border border-brand-cyan/10 px-2 py-0.5 rounded self-start mt-4 uppercase">
                Redirect Decoy
              </div>
            </motion.div>

            {/* Step 4 */}
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.7 }}
              className="relative p-5 rounded-xl border border-white/5 bg-white/1 overflow-hidden flex flex-col justify-between min-h-45"
            >
              <div>
                <span className="font-mono text-2xl font-bold text-white/10 mb-2 block">04</span>
                <h4 className="font-display font-bold text-[10px] sm:text-xs uppercase text-white mb-2">SOC Intelligence</h4>
                <p className="text-[11px] text-white/40 leading-relaxed">
                  Attacker fingerprints are stored, decoy keys are exfiltrated, and interactive SOC dashboard logs trigger real-time alerts.
                </p>
              </div>
              <div className="text-[9px] font-mono text-amber-400 bg-amber-400/5 border border-amber-400/10 px-2 py-0.5 rounded self-start mt-4 uppercase">
                Threat Logged
              </div>
            </motion.div>
          </div>

          <motion.div 
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.8 }}
            className="flex justify-center mt-12"
          >
            <Link
              href="/dashboard"
              className="px-6 py-2.5 rounded border border-brand-cyan/20 hover:border-brand-cyan/40 bg-brand-cyan/5 text-brand-cyan hover:text-white font-display text-[10px] tracking-widest uppercase transition-colors"
            >
              Start Simulation Now
            </Link>
          </motion.div>
        </section>

        {/* Footer Technical Accents */}
        <div className="mt-12 flex flex-col md:flex-row items-center justify-between text-[8px] font-mono tracking-widest text-white/20 border-t border-white/5 pt-6 gap-4 w-full">
          <div className="flex items-center space-x-2">
            <Terminal className="w-3.5 h-3.5 text-brand-cyan/60" />
            <span>PROJECT MIRAGE // AUTONOMOUS DECEPTION LAYER v2.8-BETA</span>
          </div>
          <div className="flex items-center space-x-4">
            <span className="text-brand-emerald/80">DECOY CONTAINMENT: 100% SUCCESS</span>
            <span className="w-1.5 h-1.5 rounded-full bg-brand-emerald/60 animate-pulse" />
            <span>ALL APIS SECURED</span>
          </div>
        </div>
      </main>
    </div>
  );
}
