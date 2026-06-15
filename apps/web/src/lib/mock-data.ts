/**
 * Mock data for Project MIRAGE dashboard.
 * All data is simulated and safe — no real credentials, payloads, or exploits.
 */

// ─── Metric cards ──────────────────────────────────────────────
export interface MetricSnapshot {
  totalRequests: number;
  suspiciousRequests: number;
  decoyRedirects: number;
  activeAlerts: number;
}

export const currentMetrics: MetricSnapshot = {
  totalRequests: 24831,
  suspiciousRequests: 1842,
  decoyRedirects: 1207,
  activeAlerts: 14,
};

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

// ─── Threat activity feed ──────────────────────────────────────
export type ThreatSeverity = "low" | "medium" | "high" | "critical";
export type ThreatStatus = "redirected" | "decoy_active" | "contained" | "alert";

export interface ThreatEvent {
  id: string;
  timestamp: string;
  type: string;
  sourceIp: string;
  endpoint: string;
  riskScore: number;
  severity: ThreatSeverity;
  status: ThreatStatus;
  description: string;
}

export const threatFeed: ThreatEvent[] = [
  {
    id: "evt-001",
    timestamp: "2026-06-11T14:32:08Z",
    type: "Suspicious Parameter Injection",
    sourceIp: "198.51.100.42",
    endpoint: "/api/v1/users",
    riskScore: 0.92,
    severity: "critical",
    status: "redirected",
    description: "Detected encoded SQL-like syntax in query parameter. Request redirected to decoy.",
  },
  {
    id: "evt-002",
    timestamp: "2026-06-11T14:28:45Z",
    type: "Credential Stuffing Attempt",
    sourceIp: "203.0.113.88",
    endpoint: "/api/v1/auth/login",
    riskScore: 0.87,
    severity: "high",
    status: "decoy_active",
    description: "High-frequency login attempts with rotating usernames. Decoy environment engaged.",
  },
  {
    id: "evt-003",
    timestamp: "2026-06-11T14:25:11Z",
    type: "Endpoint Scanning",
    sourceIp: "192.0.2.15",
    endpoint: "/api/v1/admin",
    riskScore: 0.78,
    severity: "high",
    status: "redirected",
    description: "Sequential endpoint enumeration detected. Traffic routed to fake endpoint cluster.",
  },
  {
    id: "evt-004",
    timestamp: "2026-06-11T14:21:33Z",
    type: "Environment File Access Attempt",
    sourceIp: "198.51.100.77",
    endpoint: "/.env",
    riskScore: 0.95,
    severity: "critical",
    status: "contained",
    description: "Attempted access to .env configuration file. Fake credential set served and contained.",
  },
  {
    id: "evt-005",
    timestamp: "2026-06-11T14:18:02Z",
    type: "Unusual Request Frequency",
    sourceIp: "100.24.56.10",
    endpoint: "/api/v1/products",
    riskScore: 0.62,
    severity: "medium",
    status: "alert",
    description: "Request rate 4x above baseline for this source. Monitoring for escalation.",
  },
  {
    id: "evt-006",
    timestamp: "2026-06-11T14:15:48Z",
    type: "Fake Credential Access",
    sourceIp: "203.0.113.22",
    endpoint: "/api/v1/config/db",
    riskScore: 0.89,
    severity: "high",
    status: "decoy_active",
    description: "Attacker accessed decoy database config containing honeytoken credentials.",
  },
  {
    id: "evt-007",
    timestamp: "2026-06-11T14:12:20Z",
    type: "Anomalous Header Pattern",
    sourceIp: "192.0.2.99",
    endpoint: "/api/v1/health",
    riskScore: 0.45,
    severity: "low",
    status: "alert",
    description: "Non-standard header combination detected. Low confidence — flagged for review.",
  },
  {
    id: "evt-008",
    timestamp: "2026-06-11T14:08:55Z",
    type: "Path Traversal Indicator",
    sourceIp: "198.51.100.5",
    endpoint: "/api/v1/files/../../../etc",
    riskScore: 0.91,
    severity: "critical",
    status: "contained",
    description: "Path traversal sequence detected in file endpoint. Contained and logged.",
  },
];

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

// ─── Alerts panel ──────────────────────────────────────────────
export type AlertSeverity = "info" | "warning" | "critical";

export interface Alert {
  id: string;
  message: string;
  severity: AlertSeverity;
  timestamp: string;
  acknowledged: boolean;
}

export const alerts: Alert[] = [
  {
    id: "alert-01",
    message: "3 critical risk events in the last 10 minutes",
    severity: "critical",
    timestamp: "2026-06-11T14:30:00Z",
    acknowledged: false,
  },
  {
    id: "alert-02",
    message: "Decoy MIRAGE_ENV_01 active session count above threshold",
    severity: "warning",
    timestamp: "2026-06-11T14:25:00Z",
    acknowledged: false,
  },
  {
    id: "alert-03",
    message: "Honeytoken credential accessed in MIRAGE_ENV_02",
    severity: "critical",
    timestamp: "2026-06-11T14:20:00Z",
    acknowledged: true,
  },
  {
    id: "alert-04",
    message: "New source IP flagged by anomaly detection model",
    severity: "warning",
    timestamp: "2026-06-11T14:15:00Z",
    acknowledged: false,
  },
  {
    id: "alert-05",
    message: "Scheduled decoy health check completed successfully",
    severity: "info",
    timestamp: "2026-06-11T14:00:00Z",
    acknowledged: true,
  },
  {
    id: "alert-06",
    message: "Fake .env file served to contained session",
    severity: "info",
    timestamp: "2026-06-11T13:55:00Z",
    acknowledged: true,
  },
];

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
