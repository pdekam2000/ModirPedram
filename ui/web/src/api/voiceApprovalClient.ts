import { API_BASE_URL } from "./client";

export type VoiceApprovalActionResponse = {
  success: boolean;
  session_id: string;
  action: string;
  message: string;
  code?: string | null;
  reject_reasons?: string[];
  voice_slot?: Record<string, unknown> | null;
  guard_result?: Record<string, unknown> | null;
  panel_excerpt?: Record<string, unknown> | null;
  audit_event?: Record<string, unknown> | null;
  tts_executed: boolean;
  api_version?: string;
};

export class VoiceApprovalSafetyError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "VoiceApprovalSafetyError";
  }
}

export function assertVoiceApprovalSafety(response: VoiceApprovalActionResponse): void {
  if (response.tts_executed !== false) {
    throw new VoiceApprovalSafetyError(
      "Voice approval safety check failed: tts_executed was not false.",
    );
  }
}

async function postVoiceAction(
  sessionId: string,
  path: string,
  body: Record<string, unknown>,
): Promise<VoiceApprovalActionResponse> {
  const response = await fetch(`${API_BASE_URL}/sessions/${encodeURIComponent(sessionId)}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = (await response.json()) as VoiceApprovalActionResponse;
  if (!response.ok || !data.success) {
    throw new Error(JSON.stringify(data));
  }
  assertVoiceApprovalSafety(data);
  return data;
}

export function postVoiceApprove(
  sessionId: string,
  body: {
    request_live_tts: boolean;
    reason?: string;
    ttl_minutes?: number;
    approved_by?: string;
  },
): Promise<VoiceApprovalActionResponse> {
  return postVoiceAction(sessionId, "/voice/approve", {
    request_live_tts: body.request_live_tts,
    reason: body.reason ?? "",
    ttl_minutes: body.ttl_minutes,
    approved_by: body.approved_by ?? "operator",
  });
}

export function postVoiceReject(
  sessionId: string,
  body: { reason?: string; rejected_by?: string } = {},
): Promise<VoiceApprovalActionResponse> {
  return postVoiceAction(sessionId, "/voice/reject", {
    reason: body.reason ?? "",
    rejected_by: body.rejected_by ?? "operator",
  });
}

export function postVoiceExpire(
  sessionId: string,
  body: { reason?: string; expired_by?: string } = {},
): Promise<VoiceApprovalActionResponse> {
  return postVoiceAction(sessionId, "/voice/expire", {
    reason: body.reason ?? "",
    expired_by: body.expired_by ?? "operator",
  });
}

export function postVoiceResetApproval(
  sessionId: string,
  body: { reason?: string; reset_by?: string; clear_live_tts_request?: boolean } = {},
): Promise<VoiceApprovalActionResponse> {
  return postVoiceAction(sessionId, "/voice/reset-approval", {
    reason: body.reason ?? "",
    reset_by: body.reset_by ?? "operator",
    clear_live_tts_request: body.clear_live_tts_request ?? false,
  });
}

export function parseVoiceApprovalError(raw: unknown): string {
  if (raw instanceof VoiceApprovalSafetyError) {
    return raw.message;
  }
  if (raw instanceof Error) {
    try {
      const parsed = JSON.parse(raw.message) as Record<string, unknown>;
      const reasons = parsed.reject_reasons;
      if (Array.isArray(reasons) && reasons.length > 0) {
        return String(parsed.message || reasons.join(", "));
      }
      return String(parsed.message || parsed.reason || parsed.code || raw.message);
    } catch {
      return raw.message;
    }
  }
  return "Voice approval action failed";
}
