"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import dynamic from "next/dynamic";
import Header from "@/components/layout/Header";
import MetricCard from "@/components/ui/MetricCard";
import ThreatFeed from "@/components/dashboard/ThreatFeed";
import DecoyStatusCard from "@/components/dashboard/DecoyStatusCard";
import AlertPanel from "@/components/dashboard/AlertPanel";
import SimulationPanel from "@/components/dashboard/SimulationPanel";
import { fetchOverview, fetchEvents, fetchAlerts, fetchTraffic, fetchRiskHistory, fetchDecoyStatus, fetchTrainingDataSummary, labelEvent, downloadTrainingData } from "@/lib/api";
import type { AnalystLabel, OverviewMetrics, FeedEvent, FeedAlert, TrafficPoint, RiskHistoryPoint, DecoyStatusData, TrainingDataSummary } from "@/lib/api";
import { Globe, ShieldAlert, ArrowRightLeft, Bell, Database, Download, Loader2, WifiOff, Volume2, VolumeX, X } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

// Charts use Recharts ResponsiveContainer — must be client-only to avoid SSR dimension warnings
const TrafficChart = dynamic(() => import("@/components/dashboard/TrafficChart"), { ssr: false });
const RiskScoreWidget = dynamic(() => import("@/components/dashboard/RiskScoreWidget"), { ssr: false });

const POLL_INTERVAL = 10_000; // 10 seconds

interface ToastNotification {
  id: string;
  title: string;
  description: string;
  severity: FeedAlert["severity"];
  timestamp: string;
}

/**
 * Web Audio API synthesizer for low-latency cyberpunk alerts without external assets.
 */
function playAlertSound(severity: string) {
  if (typeof window === "undefined") return;
  try {
    const AudioCtx = window.AudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    
    // Create nodes
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    
    osc.connect(gain);
    gain.connect(ctx.destination);
    
    if (severity === "critical") {
      // Pulsing siren alarm
      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(800, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(350, ctx.currentTime + 0.35);
      gain.gain.setValueAtTime(0.12, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);
      
      osc.start();
      osc.stop(ctx.currentTime + 0.4);
    } else if (severity === "warning") {
      // High double chirp
      osc.type = "sine";
      osc.frequency.setValueAtTime(650, ctx.currentTime);
      gain.gain.setValueAtTime(0.08, ctx.currentTime);
      gain.gain.setValueAtTime(0.001, ctx.currentTime + 0.08);
      
      const osc2 = ctx.createOscillator();
      const gain2 = ctx.createGain();
      osc2.connect(gain2);
      gain2.connect(ctx.destination);
      osc2.type = "sine";
      osc2.frequency.setValueAtTime(650, ctx.currentTime + 0.12);
      gain2.gain.setValueAtTime(0.08, ctx.currentTime + 0.12);
      gain2.gain.setValueAtTime(0.001, ctx.currentTime + 0.2);
      
      osc.start();
      osc.stop(ctx.currentTime + 0.08);
      osc2.start(ctx.currentTime + 0.12);
      osc2.stop(ctx.currentTime + 0.2);
    } else {
      // Soft ping
      osc.type = "sine";
      osc.frequency.setValueAtTime(520, ctx.currentTime);
      gain.gain.setValueAtTime(0.04, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.15);
      
      osc.start();
      osc.stop(ctx.currentTime + 0.15);
    }
  } catch (e) {
    console.warn("Failed to play audio alert:", e);
  }
}

export default function DashboardPage() {
  const [overview, setOverview] = useState<OverviewMetrics | null>(null);
  const [events, setEvents] = useState<FeedEvent[]>([]);
  const [alerts, setAlerts] = useState<FeedAlert[]>([]);
  const [traffic, setTraffic] = useState<TrafficPoint[]>([]);
  const [riskHistory, setRiskHistory] = useState<RiskHistoryPoint[]>([]);
  const [decoyStatus, setDecoyStatus] = useState<DecoyStatusData | null>(null);
  const [trainingSummary, setTrainingSummary] = useState<TrainingDataSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [labelingEventId, setLabelingEventId] = useState<string | null>(null);
  const [exportingTrainingData, setExportingTrainingData] = useState(false);

  // Toast notifications & audio toggle
  const [toasts, setToasts] = useState<ToastNotification[]>([]);
  const [soundEnabled, setSoundEnabled] = useState(false);
  const soundEnabledRef = useRef(false);
  const alertsInitializedRef = useRef(false);
  const prevAlertIdsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    soundEnabledRef.current = soundEnabled;
  }, [soundEnabled]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const handleAlertsUpdate = useCallback((newAlerts: FeedAlert[]) => {
    // Only alert for events triggered AFTER mount
    if (alertsInitializedRef.current) {
      const newItems = newAlerts.filter((a) => !prevAlertIdsRef.current.has(a.id));
      newItems.forEach((alert) => {
        const toastId = `${alert.id}-${Date.now()}`;
        setToasts((prev) => [
          {
            id: toastId,
            title: alert.message || "Threat Event Triggered",
            description: alert.description,
            severity: alert.severity,
            timestamp: alert.timestamp,
          },
          ...prev,
        ].slice(0, 5));

        // Auto remove toast after 6s
        setTimeout(() => {
          removeToast(toastId);
        }, 6000);

        // Play synth alert sound
        if (soundEnabledRef.current && (alert.severity === "critical" || alert.severity === "warning")) {
          playAlertSound(alert.severity);
        }
      });
    }

    const ids = new Set(newAlerts.map((a) => a.id));
    prevAlertIdsRef.current = ids;
    alertsInitializedRef.current = true;
    setAlerts(newAlerts);
  }, [removeToast]);

  const handleLabelEvent = useCallback(async (eventId: string, label: AnalystLabel) => {
    setLabelingEventId(eventId);
    try {
      const updated = await labelEvent(eventId, label);
      setEvents((current) =>
        current.map((event) => (event.id === eventId ? updated : event)),
      );
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to label event");
    } finally {
      setLabelingEventId(null);
    }
  }, []);

  const handleTrainingExport = useCallback(async () => {
    setExportingTrainingData(true);
    try {
      const blob = await downloadTrainingData();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "training_events.jsonl";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to export training data");
    } finally {
      setExportingTrainingData(false);
    }
  }, []);

  const load = useCallback(async () => {
    try {
      const [ov, ev, al, tr, rh, ds, ts] = await Promise.all([
        fetchOverview(),
        fetchEvents(),
        fetchAlerts(),
        fetchTraffic(),
        fetchRiskHistory(),
        fetchDecoyStatus(),
        fetchTrainingDataSummary().catch(() => null),
      ]);
      setOverview(ov);
      setEvents(ev);
      handleAlertsUpdate(al);
      setTraffic(tr);
      setRiskHistory(rh);
      setDecoyStatus(ds);
      setTrainingSummary(ts);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch data");
    } finally {
      setLoading(false);
    }
  }, [handleAlertsUpdate]);

  // Fetch on mount + poll every POLL_INTERVAL ms.
  useEffect(() => {
    const initialLoad = setTimeout(load, 0);
    const interval = setInterval(load, POLL_INTERVAL);
    return () => {
      clearTimeout(initialLoad);
      clearInterval(interval);
    };
  }, [load]);

  const trainingRowsText = trainingSummary
    ? `${trainingSummary.exportableRows}/${trainingSummary.minimumRows} rows`
    : "checking rows";
  const trainingClassesText = trainingSummary?.hasMinimumClassRows
    ? `${trainingSummary.normalRows} normal / ${trainingSummary.suspiciousRows} suspicious`
    : `needs ${trainingSummary?.minimumRowsPerClass ?? 2}+ per class`;

  return (
    <div className="min-h-screen flex flex-col bg-bg-dark-navy text-white relative">
      <Header />

      <main className="flex-1 w-full max-w-350 mx-auto px-6 pt-28 pb-8 lg:pt-32 lg:pb-12">
        {/* Page title */}
        <div className="mb-8 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="font-display text-2xl lg:text-3xl font-bold tracking-tight text-white">
              Security Dashboard
            </h1>
            <p className="text-sm text-white/40 mt-1">
              Real-time overview of API security, decoy environments, and threat activity.
            </p>
          </div>
          
          <div className="flex flex-wrap items-center gap-2">
            <div
              title={`Training data: ${trainingRowsText}; ${trainingClassesText}`}
              className={`flex items-center gap-2 px-3 py-2 rounded border text-[10px] font-mono tracking-widest ${
                trainingSummary?.readyForTraining
                  ? "border-brand-emerald/30 bg-brand-emerald/10 text-brand-emerald"
                  : "border-amber-500/20 bg-amber-500/5 text-amber-300"
              }`}
            >
              <Database className="w-3.5 h-3.5 shrink-0" />
              <span>
                {trainingSummary?.readyForTraining ? "TRAINING READY" : "TRAINING PENDING"}
              </span>
              <span className="hidden md:inline text-white/35">
                {trainingRowsText} | {trainingClassesText}
              </span>
            </div>

            <button
              type="button"
              onClick={handleTrainingExport}
              disabled={exportingTrainingData}
              className="flex items-center gap-2 px-4 py-2 rounded border border-brand-emerald/25 bg-brand-emerald/10 text-brand-emerald text-[10px] font-mono tracking-widest transition-all duration-300 hover:scale-[1.01] hover:border-brand-emerald/40 disabled:cursor-wait disabled:opacity-50"
            >
              {exportingTrainingData ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Download className="w-3.5 h-3.5" />
              )}
              <span>EXPORT JSONL</span>
            </button>

            {/* Cyberpunk Audio Toggle */}
            <button
              type="button"
              onClick={() => setSoundEnabled(!soundEnabled)}
              aria-pressed={soundEnabled}
              className={`flex items-center gap-2 px-4 py-2 rounded border text-[10px] font-mono tracking-widest transition-all duration-300 hover:scale-[1.01] ${
                soundEnabled
                  ? "bg-brand-cyan/10 border-brand-cyan/40 text-brand-cyan shadow-[0_0_15px_rgba(0,240,255,0.2)]"
                  : "bg-white/2 border-white/5 text-white/40 hover:text-white/60 hover:border-white/10"
              }`}
            >
              {soundEnabled ? (
                <>
                  <Volume2 className="w-3.5 h-3.5 animate-pulse" />
                  <span>ALARM AUDIO: ACTIVE</span>
                </>
              ) : (
                <>
                  <VolumeX className="w-3.5 h-3.5" />
                  <span>ALARM AUDIO: MUTED</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Error banner */}
        {error && (
          <div className="mb-6 flex items-center gap-3 p-4 rounded-lg border border-amber-500/20 bg-amber-500/5 text-[11px] font-mono text-amber-400">
            <WifiOff className="w-4 h-4 shrink-0" />
            <div>
              <span className="font-bold">Backend unreachable</span>
              <span className="text-white/40 ml-2">
                — {error}. Start the gateway with{" "}
                <code className="text-white/60">uvicorn app.main:app --reload</code>
              </span>
            </div>
          </div>
        )}

        {/* Simulation panel */}
        <div className="mb-6">
          <SimulationPanel onRefresh={load} />
        </div>

        {/* Metric cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {loading && !overview ? (
            // Skeleton while first load
            Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="h-28 rounded-xl border border-white/5 bg-white/2 flex items-center justify-center"
              >
                <Loader2 className="w-4 h-4 text-white/20 animate-spin" />
              </div>
            ))
          ) : (
            <>
              <MetricCard
                label="Total Requests"
                value={overview?.totalRequests ?? 0}
                icon={Globe}
                accentColor="cyan"
              />
              <MetricCard
                label="Suspicious Requests"
                value={overview?.suspiciousRequests ?? 0}
                icon={ShieldAlert}
                accentColor="amber"
              />
              <MetricCard
                label="Decoy Redirects"
                value={overview?.decoyRedirects ?? 0}
                icon={ArrowRightLeft}
                accentColor="emerald"
              />
              <MetricCard
                label="Active Alerts"
                value={overview?.activeAlerts ?? 0}
                icon={Bell}
                accentColor="red"
              />
            </>
          )}
        </div>

        {/* Charts row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-8">
          <div className="lg:col-span-2">
            <TrafficChart data={traffic} />
          </div>
          <div>
            <RiskScoreWidget score={overview?.averageRiskScore ?? 0} history={riskHistory} />
          </div>
        </div>

        {/* Threat feed */}
        <div className="mb-8">
          <ThreatFeed
            events={events}
            labelingEventId={labelingEventId}
            onLabel={handleLabelEvent}
          />
        </div>

        {/* Bottom row: Decoy + Alerts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <DecoyStatusCard data={decoyStatus} />
          <AlertPanel alerts={alerts} />
        </div>
      </main>

      {/* Toast Notification Container */}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-3 max-w-sm w-full pointer-events-none">
        <AnimatePresence>
          {toasts.map((toast) => (
            <motion.div
              key={toast.id}
              initial={{ opacity: 0, y: 30, scale: 0.9 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, scale: 0.85, transition: { duration: 0.2 } }}
              className={`toast-panel toast-${toast.severity} pointer-events-auto w-full p-4 rounded-xl border border-white/10 bg-bg-dark-navy/95 backdrop-blur-xl flex items-start gap-3 relative overflow-hidden`}
            >
              {/* Severity Accent Bar */}
              <div className="toast-severity-bar absolute top-0 left-0 bottom-0 w-1" />
              
              <div className="shrink-0 mt-0.5">
                <Bell className="w-3.5 h-3.5 text-white/50 animate-bounce" />
              </div>
              
              <div className="flex-1 min-w-0 pl-1">
                <div className="flex items-center justify-between mb-1">
                  <span className="toast-severity-badge text-[8px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded">
                    {toast.severity} threat
                  </span>
                  <span className="text-[8px] text-white/30 font-mono">
                    {new Date(toast.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                  </span>
                </div>
                <h5 className="text-[10px] font-bold text-white mb-0.5 font-display truncate">
                  {toast.title}
                </h5>
                <p className="text-[9px] text-white/40 leading-relaxed font-mono truncate">
                  {toast.description}
                </p>
              </div>
              
              <button
                type="button"
                onClick={() => removeToast(toast.id)}
                aria-label={`Dismiss ${toast.title}`}
                title="Dismiss notification"
                className="text-white/20 hover:text-white/60 transition-colors shrink-0 p-0.5"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {/* Footer */}
      <footer className="border-t border-white/5 py-6">
        <div className="max-w-350 mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-2 text-[9px] text-white/20 font-mono">
          <span>PROJECT MIRAGE // SECURITY DASHBOARD v1.0</span>
          <span className="text-brand-emerald/60">ALL SYSTEMS NOMINAL</span>
        </div>
      </footer>
    </div>
  );
}
