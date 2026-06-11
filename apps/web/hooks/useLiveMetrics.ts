"use client";

import { useEffect, useRef, useState } from "react";

import { createClient } from "@/lib/supabase/client";
import { metricsWsUrl, type MetricsWsMessage } from "@/lib/ws";

const MAX_BACKOFF_MS = 30_000;
const CONNECT_TIMEOUT_MS = 8_000;
const STALE_TIMEOUT_MS = 45_000;
const HEALTH_CHECK_INTERVAL_MS = 5_000;
const PING_INTERVAL_MS = 25_000;

export type LiveConnectionStatus =
  | "off"
  | "connecting"
  | "live"
  | "reconnecting"
  | "polling";

export function useLiveMetrics(
  symbol: string,
  enabled: boolean,
  onUpdate: (message: MetricsWsMessage) => void,
) {
  const [connectionStatus, setConnectionStatus] =
    useState<LiveConnectionStatus>(enabled ? "connecting" : "off");
  const onUpdateRef = useRef(onUpdate);

  useEffect(() => {
    onUpdateRef.current = onUpdate;
  }, [onUpdate]);

  useEffect(() => {
    if (!enabled) {
      return undefined;
    }

    let ws: WebSocket | null = null;
    let pingTimer: ReturnType<typeof setInterval> | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let connectTimer: ReturnType<typeof setTimeout> | null = null;
    let healthTimer: ReturnType<typeof setInterval> | null = null;
    let attempt = 0;
    let connecting = false;
    let disposed = false;
    let lastMessageAt = Date.now();

    const clearTimers = () => {
      if (pingTimer) {
        clearInterval(pingTimer);
        pingTimer = null;
      }
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      if (connectTimer) {
        clearTimeout(connectTimer);
        connectTimer = null;
      }
      if (healthTimer) {
        clearInterval(healthTimer);
        healthTimer = null;
      }
    };

    const scheduleReconnect = () => {
      if (disposed || !enabled) {
        return;
      }
      setConnectionStatus("polling");
      const baseDelay = Math.min(1000 * 2 ** attempt, MAX_BACKOFF_MS);
      const jitter = Math.floor(Math.random() * 350);
      const delay = baseDelay + jitter;
      attempt += 1;
      reconnectTimer = setTimeout(() => {
        connect();
      }, delay);
    };

    const connect = async () => {
      if (disposed || connecting) {
        return;
      }
      connecting = true;
      setConnectionStatus(attempt > 0 ? "reconnecting" : "connecting");

      const supabase = createClient();
      const { data: sessionData } = await supabase.auth.getSession();
      const session = sessionData.session;
      let token = session?.access_token;
      if (!token) {
        const { data } = await supabase.auth.refreshSession();
        token = data.session?.access_token;
      }
      if (!token) {
        connecting = false;
        setConnectionStatus("polling");
        scheduleReconnect();
        return;
      }

      try {
        ws = new WebSocket(metricsWsUrl(symbol, token));
      } catch {
        connecting = false;
        scheduleReconnect();
        return;
      }
      connectTimer = setTimeout(() => {
        ws?.close();
      }, CONNECT_TIMEOUT_MS);

      ws.onopen = () => {
        if (disposed) {
          return;
        }
        connecting = false;
        if (connectTimer) {
          clearTimeout(connectTimer);
          connectTimer = null;
        }
        attempt = 0;
        lastMessageAt = Date.now();
        setConnectionStatus("live");
        pingTimer = setInterval(() => {
          if (ws?.readyState === WebSocket.OPEN) {
            ws.send("ping");
          }
        }, PING_INTERVAL_MS);
        healthTimer = setInterval(() => {
          if (Date.now() - lastMessageAt > STALE_TIMEOUT_MS) {
            ws?.close();
          }
        }, HEALTH_CHECK_INTERVAL_MS);
      };

      ws.onmessage = (event) => {
        lastMessageAt = Date.now();
        try {
          const payload = JSON.parse(String(event.data)) as MetricsWsMessage;
          if (!payload.initial) {
            onUpdateRef.current(payload);
          }
        } catch {
          // ignore malformed frames
        }
      };

      ws.onerror = () => {
        ws?.close();
      };

      ws.onclose = () => {
        connecting = false;
        clearTimers();
        ws = null;
        if (!disposed && enabled) {
          scheduleReconnect();
        }
      };
    };

    const handleOffline = () => {
      setConnectionStatus("polling");
      ws?.close();
    };

    const handleOnline = () => {
      if (!disposed && !ws) {
        attempt = 0;
        connect();
      }
    };

    window.addEventListener("offline", handleOffline);
    window.addEventListener("online", handleOnline);
    connect();

    return () => {
      disposed = true;
      window.removeEventListener("offline", handleOffline);
      window.removeEventListener("online", handleOnline);
      clearTimers();
      ws?.close();
    };
  }, [enabled, symbol]);

  if (!enabled) {
    return "off" as LiveConnectionStatus;
  }

  return connectionStatus;
}
