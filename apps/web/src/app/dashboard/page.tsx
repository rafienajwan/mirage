"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import Header from "@/components/layout/Header";
import MetricCard from "@/components/ui/MetricCard";
import ThreatFeed from "@/components/dashboard/ThreatFeed";
import ActorProfilesPanel from "@/components/dashboard/ActorProfilesPanel";
import ActorTriagePanel from "@/components/dashboard/ActorTriagePanel";
import CanaryAssignmentsPanel from "@/components/dashboard/CanaryAssignmentsPanel";
import DecoyStatusCard from "@/components/dashboard/DecoyStatusCard";
import AlertPanel from "@/components/dashboard/AlertPanel";
import SimulationPanel from "@/components/dashboard/SimulationPanel";
import { fetchOverview, fetchEvents, fetchAlerts, fetchTraffic, fetchRiskHistory, fetchDecoyStatus, fetchTrainingDataSummary, fetchMLShadowStatus, fetchMLShadowSummary, fetchMLPromotionReadiness, fetchHoneytokens, fetchCanaryAssignments, fetchActorProfiles, fetchActorClusters, fetchActorCases, fetchActorCaseWorkflows, revokeCanaryAssignment, openActorCase, updateActorCase, labelEvent, downloadTrainingData, runRetraining } from "@/lib/api";
import { mapDashboardAlert, mapDashboardEvent, mapDashboardSnapshot } from "@/lib/api-map";
import type { ActorCaseSummary, ActorCaseWorkflow, ActorCaseWorkflowSummary, ActorClusterSummary, ActorProfileSummary, AnalystLabel, OverviewMetrics, FeedEvent, FeedAlert, TrafficPoint, RiskHistoryPoint, DecoyStatusData, TrainingDataSummary, MLShadowStatusData, MLShadowSummaryData, MLPromotionReadinessData, HoneytokenSummary, CanaryAssignmentSummary, RetrainingRun, DashboardStreamMessage } from "@/lib/api-types";
import { useDashboardStream } from "@/hooks/useDashboardStream";
import { pollIntervalFor } from "@/lib/dashboard-stream";
import { selectNewAlerts } from "@/lib/alert-toasts";
import { SessionExpiredError, summarizeFailures } from "@/lib/http-failure";
import { Globe, ShieldAlert, ArrowRightLeft, Bell, BrainCircuit, Database, Download, KeyRound, Loader2, AlertTriangle, Volume2, VolumeX, X } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

// Charts use Recharts ResponsiveContainer — must be client-only to avoid SSR dimension warnings
const TrafficChart = dynamic(() => import("@/components/dashboard/TrafficChart"), { ssr: false });
const RiskScoreWidget = dynamic(() => import("@/components/dashboard/RiskScoreWidget"), { ssr: false });

interface ToastNotification {
  id: string;
  title: string;
  description: string;
  severity: FeedAlert["severity"];
  timestamp: string;
}

function formatMetric(value: number | undefined) {
  return typeof value === "number" ? value.toFixed(3) : "n/a";
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
    // One context per sound; release it once the last oscillator stops.
    const closeWhenDone = (last: OscillatorNode) => {
      last.onended = () => {
        void ctx.close();
      };
    };
    
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
      
      closeWhenDone(osc);
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
      
      closeWhenDone(osc2);
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
      
      closeWhenDone(osc);
      osc.start();
      osc.stop(ctx.currentTime + 0.15);
    }
  } catch {
    return;
  }
}

export default function DashboardPage() {
  const router = useRouter();
  const [overview, setOverview] = useState<OverviewMetrics | null>(null);
  const [events, setEvents] = useState<FeedEvent[]>([]);
  const [alerts, setAlerts] = useState<FeedAlert[]>([]);
  const [traffic, setTraffic] = useState<TrafficPoint[]>([]);
  const [riskHistory, setRiskHistory] = useState<RiskHistoryPoint[]>([]);
  const [decoyStatus, setDecoyStatus] = useState<DecoyStatusData | null>(null);
  const [trainingSummary, setTrainingSummary] = useState<TrainingDataSummary | null>(null);
  const [mlShadowStatus, setMlShadowStatus] = useState<MLShadowStatusData | null>(null);
  const [mlShadowSummary, setMlShadowSummary] = useState<MLShadowSummaryData | null>(null);
  const [mlPromotionReadiness, setMlPromotionReadiness] = useState<MLPromotionReadinessData | null>(null);
  const [honeytokens, setHoneytokens] = useState<HoneytokenSummary | null>(null);
  const [canaryAssignments, setCanaryAssignments] = useState<CanaryAssignmentSummary | null>(null);
  const [actorProfiles, setActorProfiles] = useState<ActorProfileSummary | null>(null);
  const [actorClusters, setActorClusters] = useState<ActorClusterSummary | null>(null);
  const [actorCases, setActorCases] = useState<ActorCaseSummary | null>(null);
  const [actorCaseWorkflows, setActorCaseWorkflows] = useState<ActorCaseWorkflowSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [labelingEventId, setLabelingEventId] = useState<string | null>(null);
  const [exportingTrainingData, setExportingTrainingData] = useState(false);
  const [retraining, setRetraining] = useState(false);
  const [retrainingRun, setRetrainingRun] = useState<RetrainingRun | null>(null);
  const [workingActorCaseId, setWorkingActorCaseId] = useState<string | null>(null);
  const [workingCanaryAssignmentId, setWorkingCanaryAssignmentId] = useState<string | null>(null);

  // Toast notifications & audio toggle
  const [toasts, setToasts] = useState<ToastNotification[]>([]);
  const [soundEnabled, setSoundEnabled] = useState(false);
  const soundEnabledRef = useRef(false);
  const alertWatermarkRef = useRef<number | null>(null);
  const alertsRef = useRef<FeedAlert[]>([]);

  useEffect(() => {
    soundEnabledRef.current = soundEnabled;
  }, [soundEnabled]);

  useEffect(() => {
    alertsRef.current = alerts;
  }, [alerts]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // An expired session surfaces as 401 from our own /api routes: send the
  // operator back to sign in instead of reporting the backend as down.
  const reportError = useCallback((err: unknown, fallback: string) => {
    if (err instanceof SessionExpiredError) {
      router.replace("/login?next=/dashboard");
      return;
    }
    setError(err instanceof Error ? err.message : fallback);
  }, [router]);

  const handleAlertsUpdate = useCallback((newAlerts: FeedAlert[]) => {
    const { fresh, watermark } = selectNewAlerts(newAlerts, alertWatermarkRef.current);
    alertWatermarkRef.current = watermark;
    fresh.forEach((alert) => {
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
      reportError(err, "Failed to label event");
    } finally {
      setLabelingEventId(null);
    }
  }, [reportError]);

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
      reportError(err, "Failed to export training data");
    } finally {
      setExportingTrainingData(false);
    }
  }, [reportError]);

  const handleRetraining = useCallback(async () => {
    setRetraining(true);
    try {
      const result = await runRetraining();
      setRetrainingRun(result);
      setError(null);
    } catch (err) {
      reportError(err, "Failed to run retraining");
    } finally {
      setRetraining(false);
    }
  }, [reportError]);

  const handleOpenActorCase = useCallback(async (caseId: string) => {
    setWorkingActorCaseId(caseId);
    try {
      const opened = await openActorCase(caseId, "Opened from dashboard triage", "operator");
      setActorCaseWorkflows((current) => ({
        totalCases: current?.cases.some((item) => item.id === opened.id)
          ? current.totalCases
          : (current?.totalCases ?? 0) + 1,
        cases: [
          opened,
          ...(current?.cases.filter((item) => item.id !== opened.id) ?? []),
        ],
      }));
      setError(null);
    } catch (err) {
      reportError(err, "Failed to open actor case");
    } finally {
      setWorkingActorCaseId(null);
    }
  }, [reportError]);

  const handleUpdateActorCase = useCallback(
    async (caseId: string, status: ActorCaseWorkflow["status"]) => {
      const actionId = `${caseId}:${status}`;
      setWorkingActorCaseId(actionId);
      try {
        const updated = await updateActorCase(
          caseId,
          status,
          `Marked ${status} from dashboard`,
          "operator",
        );
        setActorCaseWorkflows((current) => ({
          totalCases: current?.totalCases ?? 1,
          cases: [
            updated,
            ...(current?.cases.filter((item) => item.id !== updated.id) ?? []),
          ],
        }));
        setError(null);
      } catch (err) {
        reportError(err, "Failed to update actor case");
      } finally {
        setWorkingActorCaseId(null);
      }
    },
    [reportError],
  );

  const handleRevokeCanaryAssignment = useCallback(async (assignmentId: string) => {
    setWorkingCanaryAssignmentId(assignmentId);
    try {
      const revoked = await revokeCanaryAssignment(
        assignmentId,
        "Revoked from dashboard",
      );
      setCanaryAssignments((current) => ({
        totalAssignments: current?.totalAssignments ?? 1,
        assignments: [
          revoked,
          ...(current?.assignments.filter((item) => item.id !== revoked.id) ?? []),
        ],
      }));
      setError(null);
    } catch (err) {
      reportError(err, "Failed to revoke canary assignment");
    } finally {
      setWorkingCanaryAssignmentId(null);
    }
  }, [reportError]);

  const load = useCallback(async () => {
    // allSettled: a failed request keeps the previous value on screen and is
    // reported in the error banner, instead of rendering as empty or zero.
    const results = await Promise.allSettled([
      fetchOverview().then(setOverview),
      fetchEvents().then(setEvents),
      fetchAlerts().then(handleAlertsUpdate),
      fetchTraffic().then(setTraffic),
      fetchRiskHistory().then(setRiskHistory),
      fetchDecoyStatus().then(setDecoyStatus),
      fetchTrainingDataSummary().then(setTrainingSummary),
      fetchMLShadowStatus().then(setMlShadowStatus),
      fetchMLShadowSummary().then(setMlShadowSummary),
      fetchMLPromotionReadiness().then(setMlPromotionReadiness),
      fetchHoneytokens().then(setHoneytokens),
      fetchCanaryAssignments().then(setCanaryAssignments),
      fetchActorProfiles().then(setActorProfiles),
      fetchActorClusters().then(setActorClusters),
      fetchActorCases().then(setActorCases),
      fetchActorCaseWorkflows().then(setActorCaseWorkflows),
    ]);
    const failure = summarizeFailures(results);
    if (failure) {
      reportError(failure, "Failed to fetch data");
    } else {
      setError(null);
    }
    setLoading(false);
  }, [handleAlertsUpdate, reportError]);

  const handleStreamMessage = useCallback(
    (data: DashboardStreamMessage) => {
      if (data.type === "snapshot") {
        const snapshot = mapDashboardSnapshot(data.payload);
        setEvents(snapshot.events);
        handleAlertsUpdate(snapshot.alerts);
        setOverview(snapshot.overview);
        setTraffic(snapshot.traffic);
        setRiskHistory(snapshot.riskHistory);
        setDecoyStatus(snapshot.decoyStatus);
        setTrainingSummary(snapshot.trainingSummary);
        setMlShadowStatus(snapshot.mlShadowStatus);
        setMlShadowSummary(snapshot.mlShadowSummary);
        setMlPromotionReadiness(snapshot.mlPromotionReadiness);
        setHoneytokens(snapshot.honeytokens);
        setCanaryAssignments(snapshot.canaryAssignments);
        setActorProfiles(snapshot.actorProfiles);
        setActorClusters(snapshot.actorClusters);
        setActorCases(snapshot.actorCases);
        setActorCaseWorkflows(snapshot.actorCaseWorkflows);
        return;
      }
      if (data.type === "event") {
        const event = mapDashboardEvent(data.payload);
        setEvents((current) =>
          [event, ...current.filter((item) => item.id !== event.id)].slice(0, 50),
        );
        return;
      }
      const alert = mapDashboardAlert(data.payload);
      handleAlertsUpdate(
        [
          alert,
          ...alertsRef.current.filter((item) => item.id !== alert.id),
        ].slice(0, 20),
      );
    },
    [handleAlertsUpdate],
  );

  const connectionStatus = useDashboardStream({
    onMessage: handleStreamMessage,
    onReconcile: load,
  });

  useEffect(() => {
    const initialLoad = setTimeout(load, 0);
    const interval = setInterval(load, pollIntervalFor(connectionStatus));
    return () => {
      clearTimeout(initialLoad);
      clearInterval(interval);
    };
  }, [connectionStatus, load]);

  const trainingRowsText = trainingSummary
    ? `${trainingSummary.exportableRows}/${trainingSummary.minimumRows} rows`
    : "checking rows";
  const trainingClassesText = trainingSummary?.hasMinimumClassRows
    ? `${trainingSummary.normalRows} normal / ${trainingSummary.suspiciousRows} suspicious`
    : `needs ${trainingSummary?.minimumRowsPerClass ?? 2}+ per class`;
  const mlShadowLabel =
    mlShadowStatus?.mode === "shadow_ready"
      ? "ML SHADOW READY"
      : mlShadowStatus?.mode === "missing"
        ? "ML ARTIFACT MISSING"
        : mlShadowStatus?.mode === "invalid"
          ? "ML ARTIFACT INVALID"
          : "ML SHADOW OFF";
  const mlShadowDetail = mlShadowStatus?.artifact
    ? `${mlShadowStatus.artifact} | monitor ${mlShadowStatus.monitorThreshold} / redirect ${mlShadowStatus.redirectThreshold}`
    : "heuristic routing only";
  const mlShadowObservation = mlShadowSummary?.shadowEvents
    ? `${Math.round(mlShadowSummary.agreementRate * 100)}% agree over ${mlShadowSummary.shadowEvents} events | avg score ${mlShadowSummary.averageScore.toFixed(1)}`
    : "no shadow observations yet";
  const promotionLabel =
    mlPromotionReadiness?.status === "eligible"
      ? "PROMOTION ELIGIBLE"
      : mlPromotionReadiness?.status === "needs_observation"
        ? "OBSERVATION NEEDED"
        : mlPromotionReadiness?.status === "blocked"
          ? "PROMOTION BLOCKED"
          : "PROMOTION UNAVAILABLE";
  const promotionBlocker = mlPromotionReadiness?.gates.find((gate) => !gate.passed);
  const promotionDetail = promotionBlocker?.message ?? "all configured gates passed";
  const latestHoneytoken = honeytokens?.hits[0];
  const honeytokenLabel = !honeytokens
    ? "HONEYTOKENS N/A"
    : honeytokens.totalHits
      ? `HONEYTOKEN HITS: ${honeytokens.totalHits}`
      : "HONEYTOKENS CLEAR";
  const honeytokenDetail = !honeytokens
    ? "honeytoken data not loaded"
    : latestHoneytoken
      ? `${latestHoneytoken.tokenLabel} on ${latestHoneytoken.method} ${latestHoneytoken.path}`
      : "no decoy token use observed";

  const footerStatus = error
    ? { label: "LAST REFRESH FAILED", tone: "text-amber-400/70" }
    : connectionStatus === "connected"
      ? { label: "LIVE STREAM CONNECTED", tone: "text-brand-emerald/60" }
      : connectionStatus === "connecting"
        ? { label: "STREAM CONNECTING", tone: "text-white/40" }
        : { label: `STREAM OFFLINE, POLLING EVERY ${pollIntervalFor("disconnected") / 1000}S`, tone: "text-amber-400/70" };

  return (
    <div className="min-h-screen flex flex-col bg-bg-dark-navy text-white relative">
      <Header showLogout />

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
              title={`Honeytokens: ${honeytokenDetail}`}
              className={`flex items-center gap-2 px-3 py-2 rounded border text-[10px] font-mono tracking-widest ${
                !honeytokens
                  ? "border-white/5 bg-white/2 text-white/40"
                  : honeytokens.totalHits
                    ? "border-red-500/25 bg-red-500/5 text-red-300"
                    : "border-brand-emerald/25 bg-brand-emerald/10 text-brand-emerald"
              }`}
            >
              <KeyRound className="w-3.5 h-3.5 shrink-0" />
              <span>{honeytokenLabel}</span>
              <span className="hidden xl:inline text-white/35">
                {honeytokenDetail}
              </span>
            </div>

            <div
              title={`Model status: ${mlShadowLabel}; ${mlShadowDetail}; ${mlShadowObservation}; ${promotionLabel}: ${promotionDetail}. Live routing remains heuristic.`}
              className={`flex items-center gap-2 px-3 py-2 rounded border text-[10px] font-mono tracking-widest ${
                mlPromotionReadiness?.status === "eligible"
                  ? "border-brand-emerald/30 bg-brand-emerald/10 text-brand-emerald"
                  : mlPromotionReadiness?.status === "needs_observation"
                  ? "border-brand-cyan/30 bg-brand-cyan/10 text-brand-cyan"
                  : mlPromotionReadiness?.status === "blocked" || mlShadowStatus?.mode === "invalid" || mlShadowStatus?.mode === "missing"
                    ? "border-red-500/25 bg-red-500/5 text-red-300"
                    : "border-white/5 bg-white/2 text-white/40"
              }`}
            >
              <BrainCircuit className="w-3.5 h-3.5 shrink-0" />
              <span>{promotionLabel}</span>
              <span className="hidden xl:inline text-white/35">
                {promotionDetail}
              </span>
            </div>

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

            <button
              type="button"
              onClick={handleRetraining}
              disabled={retraining || !trainingSummary?.readyForTraining}
              title={
                trainingSummary?.readyForTraining
                  ? "Train a shadow-mode candidate artifact"
                  : "Training data is not ready"
              }
              className="flex items-center gap-2 px-4 py-2 rounded border border-brand-cyan/25 bg-brand-cyan/10 text-brand-cyan text-[10px] font-mono tracking-widest transition-all duration-300 hover:scale-[1.01] hover:border-brand-cyan/40 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {retraining ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <BrainCircuit className="w-3.5 h-3.5" />
              )}
              <span>RUN TRAINING</span>
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
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span role="alert">{error}</span>
          </div>
        )}

        {retrainingRun ? (
          <div className="mb-6 rounded-lg border border-brand-cyan/15 bg-brand-cyan/5 p-4 text-[10px] font-mono text-white/45">
            <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
              <span className="text-brand-cyan">
                Artifact: {retrainingRun.artifactPath}
              </span>
              <span
                className={
                  retrainingRun.review.shadowReady
                    ? "text-brand-emerald"
                    : "text-amber-300"
                }
              >
                {retrainingRun.review.shadowReady ? "SHADOW READY" : "REVIEW BLOCKED"}
              </span>
            </div>
            <div className="mt-2 flex flex-wrap gap-3">
              <span>F1 {formatMetric(retrainingRun.metrics.f1_score)}</span>
              <span>Precision {formatMetric(retrainingRun.metrics.precision)}</span>
              <span>Recall {formatMetric(retrainingRun.metrics.recall)}</span>
              <span>FPR {formatMetric(retrainingRun.metrics.false_positive_rate)}</span>
            </div>
          </div>
        ) : null}

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
                value={overview?.totalRequests ?? null}
                icon={Globe}
                accentColor="cyan"
              />
              <MetricCard
                label="Suspicious Requests"
                value={overview?.suspiciousRequests ?? null}
                icon={ShieldAlert}
                accentColor="amber"
              />
              <MetricCard
                label="Decoy Redirects"
                value={overview?.decoyRedirects ?? null}
                icon={ArrowRightLeft}
                accentColor="emerald"
              />
              <MetricCard
                label="Active Alerts"
                value={overview?.activeAlerts ?? null}
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
            <RiskScoreWidget score={overview?.averageRiskScore ?? null} history={riskHistory} />
          </div>
        </div>

        {/* Threat feed */}
        <div className="mb-8">
          <ActorProfilesPanel data={actorProfiles} />
        </div>

        <div className="mb-8">
          <ActorTriagePanel
            clusters={actorClusters}
            cases={actorCases}
            workflows={actorCaseWorkflows}
            workingCaseId={workingActorCaseId}
            onOpenCase={handleOpenActorCase}
            onUpdateCase={handleUpdateActorCase}
          />
        </div>

        {/* Threat feed */}
        <div className="mb-8">
          <ThreatFeed
            events={events}
            labelingEventId={labelingEventId}
            onLabel={handleLabelEvent}
            connectionStatus={connectionStatus}
          />
        </div>

        {/* Bottom row: Decoy + Alerts */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <DecoyStatusCard data={decoyStatus} />
          <CanaryAssignmentsPanel
            data={canaryAssignments}
            workingAssignmentId={workingCanaryAssignmentId}
            onRevoke={handleRevokeCanaryAssignment}
          />
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
          <span>PROJECT MIRAGE // SECURITY DASHBOARD</span>
          <span className={footerStatus.tone}>{footerStatus.label}</span>
        </div>
      </footer>
    </div>
  );
}
