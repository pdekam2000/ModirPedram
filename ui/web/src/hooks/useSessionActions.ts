import { useCallback, useEffect, useState } from "react";
import {
  fetchSessionActionEligibility,
  postSessionAction,
  SessionActionEligibility,
  SessionActionResponse,
  SessionActionType,
} from "../api/client";
import { parseActionError } from "../utils/sessionActions";

export function useSessionActions(sessionId: string | null | undefined) {
  const [eligibility, setEligibility] = useState<SessionActionEligibility | null>(null);
  const [loading, setLoading] = useState(false);
  const [acting, setActing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<SessionActionResponse | null>(null);

  const reloadEligibility = useCallback(async () => {
    if (!sessionId) {
      setEligibility(null);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await fetchSessionActionEligibility(sessionId);
      setEligibility(data);
    } catch (err) {
      setEligibility(null);
      setError(parseActionError(err));
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    void reloadEligibility();
  }, [reloadEligibility]);

  const executeAction = useCallback(
    async (action: SessionActionType, reason = "") => {
      if (!sessionId) {
        return null;
      }
      setActing(true);
      setError(null);
      try {
        const result = await postSessionAction(sessionId, action, {
          reason,
          actor: "operator",
        });
        setLastResult(result);
        await reloadEligibility();
        return result;
      } catch (err) {
        const message = parseActionError(err);
        setError(message);
        try {
          const parsed = JSON.parse((err as Error).message) as SessionActionResponse;
          setLastResult(parsed);
        } catch {
          setLastResult(null);
        }
        throw err;
      } finally {
        setActing(false);
      }
    },
    [sessionId, reloadEligibility],
  );

  return {
    eligibility,
    loading,
    acting,
    error,
    lastResult,
    reloadEligibility,
    executeAction,
  };
}
