"use client";

import React, { useState, useEffect, useCallback } from "react";
import dynamic from "next/dynamic";
import Header from "@/components/layout/Header";
import MetricCard from "@/components/ui/MetricCard";
import ThreatFeed from "@/components/dashboard/ThreatFeed";
import DecoyStatusCard from "@/components/dashboard/DecoyStatusCard";
import AlertPanel from "@/components/dashboard/AlertPanel";
import SimulationPanel from "@/components/dashboard/SimulationPanel";
import { fetchOverview, fetchEvents, fetchAlerts, fetchTraffic, fetchRiskHistory, fetchDecoyStatus } from "@/lib/api";
import type { OverviewMetrics, FeedEvent, FeedAlert, TrafficPoint, RiskHistoryPoint, DecoyStatusData } from "@/lib/api";
import { Globe, ShieldAlert, ArrowRightLeft, Bell, Loader2, WifiOff } from "lucide-react";

// Charts use Recharts ResponsiveContainer — must be client-only to avoid SSR dimension warnings
const TrafficChart = dynamic(() => import("@/components/dashboard/TrafficChart"), { ssr: false });
const RiskScoreWidget = dynamic(() => import("@/components/dashboard/RiskScoreWidget"), { ssr: false });

const POLL_INTERVAL = 10_000; // 10 seconds

export default function DashboardPage() {
  const [overview, setOverview] = useState<OverviewMetrics | null>(null);
  const [events, setEvents] = useState<FeedEvent[]>([]);
  const [alerts, setAlerts] = useState<FeedAlert[]>([]);
  const [traffic, setTraffic] = useState<TrafficPoint[]>([]);
  const [riskHistory, setRiskHistory] = useState<RiskHistoryPoint[]>([]);
  const [decoyStatus, setDecoyStatus] = useState<DecoyStatusData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [ov, ev, al, tr, rh, ds] = await Promise.all([
        fetchOverview(),
        fetchEvents(),
        fetchAlerts(),
        fetchTraffic(),
        fetchRiskHistory(),
        fetchDecoyStatus(),
      ]);
      setOverview(ov);
      setEvents(ev);
      setAlerts(al);
      setTraffic(tr);
      setRiskHistory(rh);
      setDecoyStatus(ds);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch data");
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch on mount + poll every POLL_INTERVAL ms
  useEffect(() => {
    async function refresh() {
      try {
        const [ov, ev, al, tr, rh, ds] = await Promise.all([
          fetchOverview(),
          fetchEvents(),
          fetchAlerts(),
          fetchTraffic(),
          fetchRiskHistory(),
          fetchDecoyStatus(),
        ]);
        setOverview(ov);
        setEvents(ev);
        setAlerts(al);
        setTraffic(tr);
        setRiskHistory(rh);
        setDecoyStatus(ds);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch data");
      } finally {
        setLoading(false);
      }
    }

    refresh();
    const interval = setInterval(refresh, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen flex flex-col bg-[#060816] text-white">
      <Header />

      <main className="flex-1 w-full max-w-[1400px] mx-auto px-6 py-8 lg:py-12">
        {/* Page title */}
        <div className="mb-8">
          <h1 className="font-display text-2xl lg:text-3xl font-bold tracking-tight text-white">
            Security Dashboard
          </h1>
          <p className="text-sm text-white/40 mt-1">
            Real-time overview of API security, decoy environments, and threat activity.
          </p>
        </div>

        {/* Error banner */}
        {error && (
          <div className="mb-6 flex items-center gap-3 p-4 rounded-lg border border-amber-500/20 bg-amber-500/5 text-[11px] font-mono text-amber-400">
            <WifiOff className="w-4 h-4 flex-shrink-0" />
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
                className="h-28 rounded-xl border border-white/5 bg-white/[0.02] flex items-center justify-center"
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
          <ThreatFeed events={events} />
        </div>

        {/* Bottom row: Decoy + Alerts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <DecoyStatusCard data={decoyStatus} />
          <AlertPanel alerts={alerts} />
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-white/5 py-6">
        <div className="max-w-[1400px] mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-2 text-[9px] text-white/20 font-mono">
          <span>PROJECT MIRAGE // SECURITY DASHBOARD v1.0</span>
          <span className="text-brand-emerald/60">ALL SYSTEMS NOMINAL</span>
        </div>
      </footer>
    </div>
  );
}
