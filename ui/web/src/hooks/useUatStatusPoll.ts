import { useEffect, useRef, useState } from "react";
import { fetchUatStatus, UatRunResponse } from "../api/uatRuntimeClient";

const POLL_MS = 2500;

export function useUatStatusPoll(sessionId: string | null, enabled: boolean) {
  const [status, setStatus] = useState<UatRunResponse | null>(null);
  const [polling, setPolling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    if (!sessionId || !enabled) {
      setPolling(false);
      if (timerRef.current) {
        window.clearInterval(timerRef.current);
        timerRef.current = null;
      }
      return;
    }

    let cancelled = false;

    async function tick() {
      try {
        const next = await fetchUatStatus(sessionId!);
        if (cancelled) return;
        setStatus(next);
        setError(null);
        if (next.status === "completed" || next.status === "failed" || next.status === "cancelled") {
          setPolling(false);
          if (timerRef.current) {
            window.clearInterval(timerRef.current);
            timerRef.current = null;
          }
        }
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Status poll failed");
      }
    }

    setPolling(true);
    void tick();
    timerRef.current = window.setInterval(() => void tick(), POLL_MS);

    return () => {
      cancelled = true;
      if (timerRef.current) {
        window.clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [sessionId, enabled]);

  return { status, polling, error, setStatus };
}
