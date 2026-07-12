"use client";

import { useEffect, useRef, useState } from "react";

import type { DashboardStreamMessage } from "@/lib/api";
import {
  DashboardStreamClient,
  type DashboardConnectionStatus,
} from "@/lib/dashboard-stream";

interface DashboardStreamOptions {
  url?: string;
  token?: string;
  onMessage: (message: DashboardStreamMessage) => void;
  onReconcile: () => void | Promise<void>;
}

export function useDashboardStream({
  url,
  token,
  onMessage,
  onReconcile,
}: DashboardStreamOptions): DashboardConnectionStatus {
  const [status, setStatus] = useState<DashboardConnectionStatus>(
    url ? "connecting" : "disconnected",
  );
  const onMessageRef = useRef(onMessage);
  const onReconcileRef = useRef(onReconcile);

  useEffect(() => {
    onMessageRef.current = onMessage;
    onReconcileRef.current = onReconcile;
  }, [onMessage, onReconcile]);

  useEffect(() => {
    if (!url) return;

    const client = new DashboardStreamClient({
      url,
      token,
      createSocket: (target) => new WebSocket(target),
      schedule: (callback, delay) => setTimeout(callback, delay),
      cancel: (handle) => clearTimeout(handle as ReturnType<typeof setTimeout>),
      onStatus: setStatus,
      onMessage: (message) => onMessageRef.current(message),
      onReconcile: () => void onReconcileRef.current(),
    });
    client.start();
    return () => client.stop();
  }, [token, url]);

  return status;
}
