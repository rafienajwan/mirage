import type { DashboardStreamMessage } from "@/lib/api";

export type DashboardConnectionStatus =
  | "connecting"
  | "connected"
  | "disconnected";

const FALLBACK_POLL_INTERVAL = 10_000;
const CONNECTED_POLL_INTERVAL = 60_000;
const MAX_RECONNECT_DELAY = 30_000;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export type DashboardSocket = Pick<
  WebSocket,
  "onopen" | "onmessage" | "onerror" | "onclose" | "close"
>;

interface DashboardStreamClientOptions {
  getConnection: () => Promise<{ url: string; token: string }>;
  createSocket: (url: string) => DashboardSocket;
  schedule: (callback: () => void, delay: number) => unknown;
  cancel: (handle: unknown) => void;
  random?: () => number;
  onStatus: (status: DashboardConnectionStatus) => void;
  onMessage: (message: DashboardStreamMessage) => void;
  onReconcile: () => void;
}

export function pollIntervalFor(status: DashboardConnectionStatus) {
  return status === "connected"
    ? CONNECTED_POLL_INTERVAL
    : FALLBACK_POLL_INTERVAL;
}

export function reconnectDelay(
  attempt: number,
  random: () => number = Math.random,
) {
  const base = Math.min(1_000 * 2 ** attempt, MAX_RECONNECT_DELAY);
  const jittered = Math.round(base * (0.8 + random() * 0.4));
  return Math.min(jittered, MAX_RECONNECT_DELAY);
}

export function parseDashboardStreamMessage(
  raw: unknown,
): DashboardStreamMessage | null {
  try {
    const value = typeof raw === "string" ? JSON.parse(raw) : raw;
    if (!isRecord(value) || !isRecord(value.payload)) return null;
    if (
      value.type === "snapshot" &&
      Array.isArray(value.payload.events) &&
      Array.isArray(value.payload.alerts) &&
      Array.isArray(value.payload.traffic) &&
      Array.isArray(value.payload.risk_history) &&
      isRecord(value.payload.metrics) &&
      isRecord(value.payload.decoy_status) &&
      isRecord(value.payload.training_summary) &&
      isRecord(value.payload.ml_shadow_status) &&
      isRecord(value.payload.ml_shadow_summary) &&
      isRecord(value.payload.ml_promotion_readiness) &&
      isRecord(value.payload.honeytokens) &&
      isRecord(value.payload.canary_assignments) &&
      isRecord(value.payload.actor_profiles) &&
      isRecord(value.payload.actor_clusters) &&
      isRecord(value.payload.actor_cases) &&
      isRecord(value.payload.actor_case_workflows)
    ) {
      return value as unknown as DashboardStreamMessage;
    }
    if (value.type === "event" && typeof value.payload.event_id === "string") {
      return value as unknown as DashboardStreamMessage;
    }
    if (value.type === "alert" && typeof value.payload.alert_id === "string") {
      return value as unknown as DashboardStreamMessage;
    }
  } catch {
    return null;
  }
  return null;
}

export class DashboardStreamClient {
  private readonly options: DashboardStreamClientOptions;
  private socket: DashboardSocket | null = null;
  private reconnectHandle: unknown = null;
  private attempt = 0;
  private stopped = true;

  constructor(options: DashboardStreamClientOptions) {
    this.options = options;
  }

  start() {
    if (!this.stopped) return;
    this.stopped = false;
    this.connect();
  }

  stop() {
    this.stopped = true;
    if (this.reconnectHandle !== null) {
      this.options.cancel(this.reconnectHandle);
      this.reconnectHandle = null;
    }
    this.socket?.close();
    this.socket = null;
  }

  private scheduleReconnect() {
    if (this.stopped || this.reconnectHandle !== null) return;
    this.options.onStatus("disconnected");
    const delay = reconnectDelay(this.attempt++, this.options.random);
    this.reconnectHandle = this.options.schedule(() => {
      this.reconnectHandle = null;
      void this.connect();
    }, delay);
  }

  private async connect() {
    if (this.stopped) return;
    this.options.onStatus("connecting");
    let connection: { url: string; token: string };
    try {
      connection = await this.options.getConnection();
    } catch {
      this.scheduleReconnect();
      return;
    }
    if (this.stopped) return;

    const target = new URL(connection.url);
    target.searchParams.set("token", connection.token);

    const socket = this.options.createSocket(target.toString());
    this.socket = socket;
    socket.onopen = () => {
      this.attempt = 0;
      this.options.onStatus("connected");
    };
    socket.onmessage = (event) => {
      const message = parseDashboardStreamMessage(event.data);
      if (message) {
        try {
          this.options.onMessage(message);
        } catch {
          this.options.onReconcile();
        }
      } else {
        this.options.onReconcile();
      }
    };
    socket.onerror = () => socket.close();
    socket.onclose = () => {
      if (this.stopped) return;
      this.scheduleReconnect();
    };
  }
}
