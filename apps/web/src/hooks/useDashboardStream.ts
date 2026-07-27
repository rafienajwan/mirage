"use client";

import { useEffect, useRef, useState } from "react";

import type { DashboardStreamMessage } from "@/lib/api";
import {
  DashboardStreamClient,
  type DashboardConnectionStatus,
} from "@/lib/dashboard-stream";

interface DashboardStreamOptions {
  onMessage: (message: DashboardStreamMessage) => void;
  onReconcile: () => void | Promise<void>;
}

export function useDashboardStream({
  onMessage,
  onReconcile,
}: DashboardStreamOptions): DashboardConnectionStatus {
  const [status, setStatus] =
    useState<DashboardConnectionStatus>("connecting");
  const onMessageRef = useRef(onMessage);
  const onReconcileRef = useRef(onReconcile);

  useEffect(() => {
    onMessageRef.current = onMessage;
    onReconcileRef.current = onReconcile;
  }, [onMessage, onReconcile]);

  useEffect(() => {
    const client = new DashboardStreamClient({
      getConnection: async () => {
        const response = await fetch("/api/dashboard-stream-ticket", {
          cache: "no-store",
        });
        if (!response.ok) {
          throw new Error(`Stream ticket error: ${response.status}`);
        }
        return response.json() as Promise<{ url: string; token: string }>;
      },
      createSocket: (target) => new WebSocket(target),
      schedule: (callback, delay) => setTimeout(callback, delay),
      cancel: (handle) => clearTimeout(handle as ReturnType<typeof setTimeout>),
      onStatus: setStatus,
      onMessage: (message) => onMessageRef.current(message),
      onReconcile: () => void onReconcileRef.current(),
    });
    client.start();
    return () => client.stop();
  }, []);

  return status;
}
