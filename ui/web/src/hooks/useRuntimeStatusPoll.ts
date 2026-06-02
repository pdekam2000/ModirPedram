import { useCallback, useEffect, useRef, useState } from "react";
import { fetchRuntimeStatus, RuntimeStatusResponse } from "../api/client";
import { shouldPollRuntimeStatus } from "../utils/runtimeObservability";

const POLL_INTERVAL_MS = 5000;

export type RuntimeStatusPollState = {
  status: RuntimeStatusResponse | null;
  error: string | null;
  polling: boolean;
  lastUpdatedAt: string | null;
};

const EMPTY_STATE: RuntimeStatusPollState = {
  status: null,
  error: null,
  polling: false,
  lastUpdatedAt: null,
};

export function useRuntimeStatusPoll(
  sessionId: string | null | undefined,
  enabled = true,
  refreshKey = 0,
): RuntimeStatusPollState {
  const [state, setState] = useState<RuntimeStatusPollState>(EMPTY_STATE);
  const timerRef = useRef<number | null>(null);

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  useEffect(() => {
    clearTimer();
    if (!enabled || !sessionId) {
      setState(EMPTY_STATE);
      return;
    }

    let cancelled = false;

    const schedule = (delay: number) => {
      clearTimer();
      timerRef.current = window.setTimeout(() => {
        void tick();
      }, delay);
    };

    const tick = async () => {
      try {
        const status = await fetchRuntimeStatus(sessionId);
        if (cancelled) {
          return;
        }
        const sessionState = status.state || status.runtime_state;
        const keepPolling = shouldPollRuntimeStatus(sessionState);
        setState({
          status,
          error: null,
          polling: keepPolling,
          lastUpdatedAt: new Date().toISOString(),
        });
        if (keepPolling) {
          schedule(POLL_INTERVAL_MS);
        }
      } catch (err) {
        if (cancelled) {
          return;
        }
        setState((prev) => ({
          ...prev,
          error: err instanceof Error ? err.message : "Runtime status poll failed",
          polling: true,
          lastUpdatedAt: new Date().toISOString(),
        }));
        schedule(POLL_INTERVAL_MS);
      }
    };

    void tick();

    return () => {
      cancelled = true;
      clearTimer();
    };
  }, [sessionId, enabled, refreshKey, clearTimer]);

  return state;
}

export function useRuntimeStatusPollMap(sessionIds: string[]): Record<string, RuntimeStatusPollState> {
  const [states, setStates] = useState<Record<string, RuntimeStatusPollState>>({});
  const timersRef = useRef<Record<string, number>>({});

  useEffect(() => {
    const activeIds = [...new Set(sessionIds.filter(Boolean))];
    const cancelledFlags: Record<string, boolean> = {};

    const clearTimer = (id: string) => {
      const timer = timersRef.current[id];
      if (timer) {
        window.clearTimeout(timer);
        delete timersRef.current[id];
      }
    };

    const schedule = (id: string, delay: number) => {
      clearTimer(id);
      timersRef.current[id] = window.setTimeout(() => {
        void tick(id);
      }, delay);
    };

    const tick = async (id: string) => {
      try {
        const status = await fetchRuntimeStatus(id);
        if (cancelledFlags[id]) {
          return;
        }
        const sessionState = status.state || status.runtime_state;
        const keepPolling = shouldPollRuntimeStatus(sessionState);
        setStates((prev) => ({
          ...prev,
          [id]: {
            status,
            error: null,
            polling: keepPolling,
            lastUpdatedAt: new Date().toISOString(),
          },
        }));
        if (keepPolling) {
          schedule(id, POLL_INTERVAL_MS);
        } else {
          clearTimer(id);
        }
      } catch (err) {
        if (cancelledFlags[id]) {
          return;
        }
        setStates((prev) => ({
          ...prev,
          [id]: {
            status: prev[id]?.status ?? null,
            error: err instanceof Error ? err.message : "Runtime status poll failed",
            polling: true,
            lastUpdatedAt: new Date().toISOString(),
          },
        }));
        schedule(id, POLL_INTERVAL_MS);
      }
    };

    activeIds.forEach((id) => {
      cancelledFlags[id] = false;
      void tick(id);
    });

    Object.keys(timersRef.current).forEach((id) => {
      if (!activeIds.includes(id)) {
        cancelledFlags[id] = true;
        clearTimer(id);
      }
    });

    return () => {
      activeIds.forEach((id) => {
        cancelledFlags[id] = true;
        clearTimer(id);
      });
    };
  }, [sessionIds.join("|")]);

  return states;
}
