/**
 * Mock data for Project MIRAGE dashboard.
 * All data is simulated and safe — no real credentials, payloads, or exploits.
 */

// ─── Traffic time-series ───────────────────────────────────────
export interface TrafficPoint {
  time: string;
  normal: number;
  suspicious: number;
}

export const trafficData: TrafficPoint[] = [
  { time: "00:00", normal: 120, suspicious: 8 },
  { time: "02:00", normal: 95, suspicious: 5 },
  { time: "04:00", normal: 80, suspicious: 12 },
  { time: "06:00", normal: 110, suspicious: 18 },
  { time: "08:00", normal: 210, suspicious: 34 },
  { time: "10:00", normal: 340, suspicious: 58 },
  { time: "12:00", normal: 380, suspicious: 72 },
  { time: "14:00", normal: 360, suspicious: 65 },
  { time: "16:00", normal: 310, suspicious: 48 },
  { time: "18:00", normal: 260, suspicious: 39 },
  { time: "20:00", normal: 190, suspicious: 22 },
  { time: "22:00", normal: 140, suspicious: 15 },
];

// ─── Threat activity feed (types only — data comes from API) ──
export type ThreatSeverity = "low" | "medium" | "high" | "critical";
export type ThreatStatus = "redirected" | "decoy_active" | "contained" | "alert";

// ─── Decoy environment status ──────────────────────────────────
export type DecoyState = "idle" | "routing" | "contained";

export interface DecoyEnvironment {
  id: string;
  name: string;
  state: DecoyState;
  activeSessions: number;
  uptime: string;
  lastTriggered: string;
}

export const decoyEnvironments: DecoyEnvironment[] = [
  {
    id: "decoy-01",
    name: "MIRAGE_ENV_01",
    state: "routing",
    activeSessions: 3,
    uptime: "14h 22m",
    lastTriggered: "2 min ago",
  },
  {
    id: "decoy-02",
    name: "MIRAGE_ENV_02",
    state: "contained",
    activeSessions: 1,
    uptime: "8h 05m",
    lastTriggered: "18 min ago",
  },
  {
    id: "decoy-03",
    name: "MIRAGE_ENV_03",
    state: "idle",
    activeSessions: 0,
    uptime: "—",
    lastTriggered: "3h ago",
  },
];

// ─── Alerts panel (types only — data comes from API) ────────
export type AlertSeverity = "info" | "warning" | "critical";

// ─── Risk score gauge (dashboard) ──────────────────────────────
export interface RiskScoreSnapshot {
  score: number; // 0–100
  label: string;
  color: string;
}

export const riskScoreSnapshot: RiskScoreSnapshot = {
  score: 74,
  label: "Elevated",
  color: "#f59e0b",
};

// ─── Risk score history for chart ───────────────────────────────
export interface RiskHistoryPoint {
  time: string;
  score: number;
}

export const riskHistory: RiskHistoryPoint[] = [
  { time: "14:00", score: 42 },
  { time: "14:05", score: 55 },
  { time: "14:10", score: 48 },
  { time: "14:15", score: 61 },
  { time: "14:20", score: 74 },
  { time: "14:25", score: 68 },
  { time: "14:30", score: 74 },
];
