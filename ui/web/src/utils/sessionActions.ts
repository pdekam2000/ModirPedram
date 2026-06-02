import { SessionActionType } from "../api/client";

export type ActionMeta = {
  label: string;
  requireReason: boolean;
  consequence: string;
  safetyNote: string;
  variant: "default" | "danger" | "neutral";
};

export const ACTION_META: Record<SessionActionType, ActionMeta> = {
  retry: {
    label: "Retry",
    requireReason: false,
    consequence: "Prepare this session for another dispatch attempt (state → DEQUEUED).",
    safetyNote: "Does not start provider execution. Dispatch remains a separate manual step.",
    variant: "default",
  },
  cancel: {
    label: "Cancel",
    requireReason: true,
    consequence: "Mark the in-flight runtime job as cancelled and clean up the job registry.",
    safetyNote:
            "Worker cooperative cancel is not implemented yet. Registry marks cancel at next checkpoint.",
    variant: "danger",
  },
  archive: {
    label: "Archive",
    requireReason: true,
    consequence: "Soft-hide this terminal session (flag only — no data deleted).",
    safetyNote: "Session JSON, artifacts, and audit history are preserved.",
    variant: "neutral",
  },
  requeue: {
    label: "Requeue",
    requireReason: true,
    consequence: "Return this session to the execution queue (state → QUEUED).",
    safetyNote: "Queued only — does not dequeue or dispatch automatically.",
    variant: "default",
  },
};

export const SESSION_ACTIONS: SessionActionType[] = ["retry", "cancel", "archive", "requeue"];

export function parseActionError(raw: unknown): string {
  if (raw instanceof Error) {
    try {
      const parsed = JSON.parse(raw.message) as Record<string, unknown>;
      return String(parsed.reason || parsed.message || parsed.code || raw.message);
    } catch {
      return raw.message;
    }
  }
  return "Action failed";
}
