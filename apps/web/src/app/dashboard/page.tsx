"use client";

import React from "react";
import Header from "@/components/layout/Header";
import MetricCard from "@/components/ui/MetricCard";
import TrafficChart from "@/components/dashboard/TrafficChart";
import RiskScoreWidget from "@/components/dashboard/RiskScoreWidget";
import ThreatFeed from "@/components/dashboard/ThreatFeed";
import DecoyStatusCard from "@/components/dashboard/DecoyStatusCard";
import AlertPanel from "@/components/dashboard/AlertPanel";
import { currentMetrics } from "@/lib/mock-data";
import {
  Globe,
  ShieldAlert,
  ArrowRightLeft,
  Bell,
} from "lucide-react";

export default function DashboardPage() {
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

        {/* Metric cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <MetricCard
            label="Total Requests"
            value={currentMetrics.totalRequests}
            icon={Globe}
            accentColor="cyan"
          />
          <MetricCard
            label="Suspicious Requests"
            value={currentMetrics.suspiciousRequests}
            icon={ShieldAlert}
            accentColor="amber"
          />
          <MetricCard
            label="Decoy Redirects"
            value={currentMetrics.decoyRedirects}
            icon={ArrowRightLeft}
            accentColor="emerald"
          />
          <MetricCard
            label="Active Alerts"
            value={currentMetrics.activeAlerts}
            icon={Bell}
            accentColor="red"
          />
        </div>

        {/* Charts row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-8">
          <div className="lg:col-span-2">
            <TrafficChart />
          </div>
          <div>
            <RiskScoreWidget />
          </div>
        </div>

        {/* Threat feed */}
        <div className="mb-8">
          <ThreatFeed />
        </div>

        {/* Bottom row: Decoy + Alerts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <DecoyStatusCard />
          <AlertPanel />
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
