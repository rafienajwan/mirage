"use client";

import React, { useEffect, useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AreaChart, Area, XAxis, YAxis, Tooltip } from "recharts";
import { ShieldAlert, RefreshCw, Zap, Container, CheckCircle, Crosshair } from "lucide-react";

// ==========================================
// 1. RISK SCORE WIDGET
// ==========================================
export function RiskScoreWidget() {
  const [pulse, setPulse] = useState(false);

  useEffect(() => {
    const interval = setInterval(() => {
      setPulse((p) => !p);
    }, 2000);
    return () => clearInterval(interval);
  }, []);

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
          Threat Rating
        </span>
        <span className="text-[7px] lg:text-[7.5px] text-red-500/80 font-bold bg-red-950/15 border border-red-500/10 px-1.5 py-0.5 rounded flex items-center">
          CRITICAL
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
            strokeDashoffset="13.07" // 92% filled (163.36 * 0.08 offset)
            strokeLinecap="round"
          />
        </svg>

        {/* Inner Text */}
        <div className="absolute flex flex-col items-center justify-center">
          <span className="text-xs lg:text-sm font-bold font-display leading-none text-white/90">92%</span>
          <span className="text-[6px] lg:text-[7px] text-white/30 uppercase tracking-widest mt-0.5">Risk</span>
        </div>
      </div>

      {/* Footer Info */}
      <div className="flex justify-between items-center text-[7.5px] lg:text-[8px]">
        <span className="text-white/40 flex items-center">
          <ShieldAlert className="w-2.5 h-2.5 lg:w-3 lg:h-3 text-red-500/60 mr-1 animate-pulse" />
          Anomalous Spikes
        </span>
        <span className="text-white/20">SYS_V4</span>
      </div>
    </motion.div>
  );
}

// ==========================================
// 2. LIVE THREAT FEED WIDGET
// ==========================================
interface AlertLog {
  id: string;
  time: string;
  type: string;
  source: string;
  status: "REDIRECTED" | "DECOY_ENV" | "CONTAINED";
}

const INITIAL_ALERTS: AlertLog[] = [
  { id: "1", time: "01:05:42", type: "SQL injection", source: "104.22.45.10", status: "REDIRECTED" },
  { id: "2", time: "01:05:12", type: "API Cred Stuffing", source: "45.18.204.3", status: "DECOY_ENV" },
  { id: "3", time: "01:04:38", type: "DDoS Flood Vector", source: "185.92.12.8", status: "CONTAINED" },
  { id: "4", time: "01:03:59", type: "XSS Infiltration", source: "88.11.199.4", status: "REDIRECTED" },
];

const THREAT_TYPES = [
  "SQL Infiltration Attempt",
  "API Credential Spraying",
  "DDoS Attack Layer 7",
  "Decoy Redirect Triggered",
  "Auth Bypass Probe",
  "RCE Shell Command Injection"
];

const THREAT_SOURCES = [
  "182.204.1.92",
  "93.100.43.108",
  "14.88.201.21",
  "192.42.116.15",
  "203.0.113.88",
  "45.9.22.103"
];

const THREAT_STATUSES: ("REDIRECTED" | "DECOY_ENV" | "CONTAINED")[] = [
  "REDIRECTED",
  "DECOY_ENV",
  "CONTAINED"
];

export function ThreatFeedWidget() {
  const [alerts, setAlerts] = useState<AlertLog[]>(INITIAL_ALERTS);

  useEffect(() => {
    const interval = setInterval(() => {
      const date = new Date();
      const timeStr = date.toTimeString().split(" ")[0];
      const newAlert: AlertLog = {
        id: Math.random().toString(),
        time: timeStr,
        type: THREAT_TYPES[Math.floor(Math.random() * THREAT_TYPES.length)],
        source: THREAT_SOURCES[Math.floor(Math.random() * THREAT_SOURCES.length)],
        status: THREAT_STATUSES[Math.floor(Math.random() * THREAT_STATUSES.length)]
      };

      setAlerts((prev) => [newAlert, ...prev.slice(0, 3)]);
    }, 4000);

    return () => clearInterval(interval);
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.6, delay: 0.2 }}
      className="glass-panel w-full md:w-[320px] p-4 h-[240px] flex flex-col justify-between pointer-events-auto"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/5 pb-2">
        <div className="flex items-center space-x-2">
          <div className="w-1.5 h-1.5 rounded-full bg-red-500 animate-ping" />
          <span className="font-display text-[9px] tracking-widest text-white/80 font-bold uppercase">
            Live Threat Logs
          </span>
        </div>
        <span className="text-[8px] text-brand-cyan/60 flex items-center">
          <RefreshCw className="w-2.5 h-2.5 mr-1 animate-spin" style={{ animationDuration: '6s' }} />
          STREAMING
        </span>
      </div>

      {/* Feed list */}
      <div className="flex-1 my-3 overflow-hidden flex flex-col space-y-2 relative">
        <AnimatePresence initial={false}>
          {alerts.map((alert) => (
            <motion.div
              key={alert.id}
              initial={{ opacity: 0, x: -10, height: 0 }}
              animate={{ opacity: 1, x: 0, height: "auto" }}
              exit={{ opacity: 0, y: 10, height: 0 }}
              transition={{ duration: 0.3 }}
              className="flex justify-between items-start text-[9px] border-b border-white/5 pb-1.5"
            >
              <div className="flex flex-col">
                <div className="flex items-center space-x-1.5 text-white/95 font-medium font-sans">
                  <span className="text-white/40 font-mono text-[8px]">{alert.time}</span>
                  <span className="text-[9px] font-bold text-white/80 max-w-[140px] truncate">{alert.type}</span>
                </div>
                <span className="text-[8px] text-white/45 font-mono mt-0.5">SRC: {alert.source}</span>
              </div>
              <div>
                <span
                  className={`text-[7.5px] font-bold px-1.5 py-0.5 rounded font-mono ${
                    alert.status === "REDIRECTED"
                      ? "bg-brand-cyan/10 border border-brand-cyan/20 text-brand-cyan"
                      : alert.status === "DECOY_ENV"
                      ? "bg-brand-emerald/10 border border-brand-emerald/20 text-brand-emerald"
                      : "bg-purple-500/10 border border-purple-500/20 text-purple-400"
                  }`}
                >
                  {alert.status}
                </span>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {/* Footer */}
      <div className="text-[8px] text-white/30 flex items-center justify-between pt-1 border-t border-white/5">
        <span>INTRUSIONS MITIGATED TODAY</span>
        <span className="text-brand-cyan font-bold">1,842</span>
      </div>
    </motion.div>
  );
}

// ==========================================
// 3. TRAFFIC ACTIVITY CHART WIDGET
// ==========================================
interface DataPoint {
  time: string;
  load: number;
  anomaly: number;
}

const generateData = (): DataPoint[] => {
  const result: DataPoint[] = [];
  const now = new Date();
  for (let i = 9; i >= 0; i--) {
    const t = new Date(now.getTime() - i * 3000);
    result.push({
      time: t.toTimeString().split(" ")[0].slice(3), // mm:ss
      load: 20 + Math.floor(Math.random() * 40),
      anomaly: Math.random() > 0.8 ? 50 + Math.floor(Math.random() * 40) : 0,
    });
  }
  return result;
};

export function TrafficChartWidget() {
  const [data, setData] = useState<DataPoint[]>([]);
  const [isMounted, setIsMounted] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

  useEffect(() => {
    setIsMounted(true);
    setData(generateData());

    const interval = setInterval(() => {
      setData((prev) => {
        if (prev.length === 0) return generateData();
        const nextTime = new Date();
        const timeStr = nextTime.toTimeString().split(" ")[0].slice(3);
        const newPoint: DataPoint = {
          time: timeStr,
          load: 20 + Math.floor(Math.random() * 40),
          anomaly: Math.random() > 0.85 ? 50 + Math.floor(Math.random() * 45) : 0,
        };
        return [...prev.slice(1), newPoint];
      });
    }, 3000);

    // Initialize ResizeObserver to track actual width and height
    const container = containerRef.current;
    if (!container) {
      return () => clearInterval(interval);
    }

    const observer = new ResizeObserver((entries) => {
      if (!entries || entries.length === 0) return;
      const { width, height } = entries[0].contentRect;
      if (width > 0 && height > 0) {
        setDimensions({ width, height });
      }
    });

    observer.observe(container);

    return () => {
      clearInterval(interval);
      observer.disconnect();
    };
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.6, delay: 0.3 }}
      className="w-full md:w-[220px] lg:w-[270px] p-3 lg:p-3.5 h-[150px] lg:h-[175px] flex flex-col justify-between backdrop-blur-xl border border-white/3 bg-white/[0.005] shadow-2xl rounded-xl opacity-25 hover:opacity-85 hover:border-white/10 hover:bg-white/[0.015] transition-all duration-500 select-none pointer-events-auto group"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/5 pb-1 lg:pb-1.5">
        <div className="flex flex-col">
          <span className="font-display text-[7.5px] lg:text-[8px] tracking-widest text-white/40 uppercase">
            Live Anomaly Score
          </span>
          <span className="text-[6px] lg:text-[6.5px] text-white/25 font-mono mt-0.5">
            Decoy Node Traffic Redirection
          </span>
        </div>
        <Zap className="w-3 h-3 lg:w-3.5 lg:h-3.5 text-brand-cyan/60 animate-pulse" />
      </div>

      {/* Chart */}
      <div ref={containerRef} className="w-full h-[65px] lg:h-[80px] my-1 select-none flex items-center justify-center overflow-hidden">
        {isMounted && dimensions.width > 0 && dimensions.height > 0 ? (
          <AreaChart width={dimensions.width} height={dimensions.height} data={data} margin={{ top: 2, right: 2, left: -32, bottom: 0 }}>
            <defs>
              <linearGradient id="loadColor" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#00f0ff" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#00f0ff" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="anomalyColor" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#5ed29c" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#5ed29c" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="time"
              stroke="rgba(255,255,255,0.15)"
              fontSize={6}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              stroke="rgba(255,255,255,0.15)"
              fontSize={6}
              tickLine={false}
              axisLine={false}
              domain={[0, 100]}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "rgba(6, 8, 22, 0.95)",
                borderColor: "rgba(0, 240, 255, 0.15)",
                fontSize: "7px",
                borderRadius: "4px",
                color: "#fff",
              }}
            />
            <Area
              type="monotone"
              dataKey="load"
              stroke="#00f0ff/60"
              strokeWidth={1}
              fillOpacity={1}
              fill="url(#loadColor)"
              name="Normal"
            />
            <Area
              type="monotone"
              dataKey="anomaly"
              stroke="#5ed29c/60"
              strokeWidth={1}
              fillOpacity={1}
              fill="url(#anomalyColor)"
              name="Decoy"
            />
          </AreaChart>
        ) : (
          <div className="text-[7.5px] lg:text-[8px] text-white/20 animate-pulse font-mono flex items-center">
            <RefreshCw className="w-2.5 h-2.5 animate-spin mr-1.5" />
            LOADING CHART...
          </div>
        )}
      </div>

      {/* Info footer */}
      <div className="flex justify-between text-[7.5px] text-white/30 pt-1 border-t border-white/5">
        <span className="flex items-center">
          <span className="w-1 h-1 rounded-full bg-brand-cyan mr-1" />
          Scans: 142/s
        </span>
        <span className="flex items-center">
          <span className="w-1.5 h-1.5 rounded-full bg-brand-emerald mr-1" />
          Decoy Load: 4.8%
        </span>
      </div>
    </motion.div>
  );
}

// ==========================================
// 4. ACTIVE DECOY ENVIRONMENT WIDGET
// ==========================================
export function DecoyStatusWidget() {
  const [status, setStatus] = useState<"IDLE" | "ROUTING" | "CONTAINED">("ROUTING");

  useEffect(() => {
    const cycle = setInterval(() => {
      setStatus((s) => {
        if (s === "ROUTING") return "CONTAINED";
        if (s === "CONTAINED") return "IDLE";
        return "ROUTING";
      });
    }, 4500);
    return () => clearInterval(cycle);
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.6, delay: 0.4 }}
      className="glass-panel w-full sm:w-[260px] p-4 h-[180px] flex flex-col justify-between pointer-events-auto"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/5 pb-2">
        <span className="font-display text-[9px] tracking-widest text-white/50 uppercase">
          Decoy Status
        </span>
        <span className="text-[9px] text-brand-emerald font-bold bg-brand-emerald/10 border border-brand-emerald/20 px-2 py-0.5 rounded flex items-center">
          <Container className="w-2.5 h-2.5 mr-1" />
          ISOLATED
        </span>
      </div>

      {/* Diagram Content */}
      <div className="flex items-center justify-between relative h-20 my-2 px-1">
        {/* Attacker node */}
        <div className="flex flex-col items-center z-10">
          <div className="w-9 h-9 rounded-lg bg-red-950/20 border border-red-500/30 flex items-center justify-center relative">
            <div className="absolute inset-0 bg-red-500/10 animate-ping rounded-lg" style={{ animationDuration: '3s' }} />
            <ShieldAlert className="w-4 h-4 text-red-500" />
          </div>
          <span className="text-[7.5px] text-white/40 uppercase mt-1 font-mono">Attacker</span>
        </div>

        {/* Splitting lines in SVG */}
        <div className="absolute inset-x-9 top-1/2 -translate-y-1/2 h-12 pointer-events-none">
          <svg className="w-full h-full" viewBox="0 0 100 48" fill="none">
            {/* Top path (Real API - Blocked) */}
            <path d="M 0 24 C 30 24, 40 8, 100 8" stroke="rgba(255, 0, 0, 0.2)" strokeWidth="1" strokeDasharray="3 3" />
            
            {/* Bottom path (Decoy - Redirected) */}
            <path d="M 0 24 C 30 24, 40 40, 100 40" stroke="var(--color-brand-cyan)" strokeWidth="1.5" />
            
            {/* Flow dots */}
            {status === "ROUTING" && (
              <motion.circle
                cx="0"
                cy="24"
                r="3"
                fill="#00f0ff"
                animate={{
                  cx: [10, 30, 60, 90],
                  cy: [24, 20, 35, 40]
                }}
                transition={{
                  duration: 1.8,
                  repeat: Infinity,
                  ease: "easeInOut"
                }}
              />
            )}
          </svg>
        </div>

        {/* Target endpoints */}
        <div className="flex flex-col justify-between h-full py-0.5 z-10 ml-auto">
          {/* Real API */}
          <div className="flex items-center space-x-1.5 opacity-40">
            <span className="text-[7.5px] text-white/60 font-mono">Prod API</span>
            <div className="w-6 h-6 rounded-md bg-white/5 border border-white/10 flex items-center justify-center">
              <CheckCircle className="w-3 h-3 text-white/40" />
            </div>
          </div>
          
          {/* Decoy */}
          <div className="flex items-center space-x-1.5">
            <span className="text-[7.5px] text-brand-emerald font-mono font-bold">MIRAGE_ENV_01</span>
            <div className="w-6 h-6 rounded-md bg-brand-cyan/10 border border-brand-cyan/30 flex items-center justify-center shadow-[0_0_8px_rgba(0,240,255,0.2)] animate-pulse">
              <Crosshair className="w-3 h-3 text-brand-cyan" />
            </div>
          </div>
        </div>
      </div>

      {/* Status label */}
      <div className="text-[8px] text-white/45 flex items-center justify-between border-t border-white/5 pt-1">
        <span>ROUTING LOGS</span>
        <span className="font-mono text-brand-cyan font-bold">
          {status === "ROUTING" && "DETOUR ACTIVE..."}
          {status === "CONTAINED" && "HOST CONTAINED"}
          {status === "IDLE" && "MONITORING..."}
        </span>
      </div>
    </motion.div>
  );
}
