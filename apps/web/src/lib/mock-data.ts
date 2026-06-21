/**
 * Mock data and types for Project MIRAGE dashboard.
 * Types are shared across components. Static data below is only used
 * by the DecoyStatusCard until a live decoy status endpoint is wired.
 */

// ─── Threat activity feed types ────────────────────────────────
export type ThreatSeverity = "low" | "medium" | "high" | "critical";
export type ThreatStatus = "redirected" | "decoy_active" | "contained" | "alert";

// ─── Alerts panel types ────────────────────────────────────────
export type AlertSeverity = "info" | "warning" | "critical";

// ─── Decoy environment status (static until live decoy API) ────
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
