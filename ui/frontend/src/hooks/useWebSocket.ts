import { useRef, useEffect, useCallback, useState } from "react";

type WSMessage = { type: string; data: Record<string, unknown> };
type MessageHandler = (msg: WSMessage) => void;

const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000];

export function useWebSocket(url: string, onMessage: MessageHandler) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const handlerRef = useRef(onMessage);
  const retriesRef = useRef(0);
  const mountedRef = useRef(true);
  handlerRef.current = onMessage;

  const connect = useCallback(() => {
    if (!mountedRef.current) return;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      retriesRef.current = 0;
    };

    ws.onclose = () => {
      setConnected(false);
      if (!mountedRef.current) return;
      const delay = RECONNECT_DELAYS[Math.min(retriesRef.current, RECONNECT_DELAYS.length - 1)];
      retriesRef.current++;
      setTimeout(connect, delay);
    };

    ws.onerror = () => {
      setConnected(false);
    };

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data) as WSMessage;
        handlerRef.current(msg);
      } catch {}
    };
  }, [url]);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      wsRef.current?.close();
    };
  }, [connect]);

  const send = useCallback((data: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  return { send, connected };
}
