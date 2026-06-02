const BLOCK_LABELS: Record<string, string> = {
  NO_NARRATION: "No narration text available — voice approval unavailable.",
  CREDENTIALS_MISSING: "ElevenLabs API key missing — configure credentials before approval.",
  PREFLIGHT_NOT_READY: "Voice preflight not ready.",
  LIVE_TTS_NOT_REQUESTED: "Live TTS not requested — use Approve to authorize future generation.",
  VOICE_APPROVAL_REQUIRED: "Operator approval required before live TTS can run.",
  VOICE_APPROVAL_REJECTED: "Voice generation was rejected.",
  APPROVAL_EXPIRED: "Approval expired — re-approval required.",
  VOICE_CHARACTER_LIMIT_EXCEEDED: "Estimated character count exceeds limit.",
  VOICE_COST_LIMIT_EXCEEDED: "Estimated cost exceeds budget cap.",
  BUDGET_BLOCKED: "Session budget blocks voice spend.",
  OPERATIONS_CANCELLED: "Session cancellation requested.",
};

export const VOICE_APPROVE_SAFETY_WARNING =
  "This only approves future voice generation. It does not generate audio yet.";

export const VOICE_APPROVAL_ACTIONS_BANNER =
  "Voice approval actions authorize future ElevenLabs spend metadata only. No audio is generated in this phase.";

export const DEFAULT_APPROVAL_TTL_MINUTES = 240;

export function formatBlockedReason(code: string): string {
  const key = String(code || "").trim().toUpperCase();
  return BLOCK_LABELS[key] || key;
}

export function formatBlockedReasons(codes: string[]): string {
  if (codes.length === 0) {
    return "—";
  }
  return codes.map(formatBlockedReason).join(" · ");
}
