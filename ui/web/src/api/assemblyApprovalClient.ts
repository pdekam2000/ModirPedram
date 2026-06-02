import { API_BASE_URL } from "./client";

export type AssemblyApprovalActionResponse = {
  success: boolean;
  session_id: string;
  action: string;
  message: string;
  code?: string | null;
  reject_reasons?: string[];
  assembly_slot?: Record<string, unknown> | null;
  guard_result?: Record<string, unknown> | null;
  panel_excerpt?: Record<string, unknown> | null;
  audit_event?: Record<string, unknown> | null;
  real_assembly_executed: boolean;
  api_version?: string;
};

export class AssemblyApprovalSafetyError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AssemblyApprovalSafetyError";
  }
}

export function assertAssemblyApprovalSafety(response: AssemblyApprovalActionResponse): void {
  if (response.real_assembly_executed !== false) {
    throw new AssemblyApprovalSafetyError(
      "Assembly approval safety check failed: real_assembly_executed was not false.",
    );
  }
}

async function postAssemblyAction(
  sessionId: string,
  path: string,
  body: Record<string, unknown>,
): Promise<AssemblyApprovalActionResponse> {
  const response = await fetch(`${API_BASE_URL}/sessions/${encodeURIComponent(sessionId)}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = (await response.json()) as AssemblyApprovalActionResponse;
  if (data.real_assembly_executed !== false) {
    throw new AssemblyApprovalSafetyError(
      "Assembly approval safety check failed: real_assembly_executed was not false.",
    );
  }
  if (!response.ok || !data.success) {
    throw new Error(JSON.stringify(data));
  }
  assertAssemblyApprovalSafety(data);
  return data;
}

export function postAssemblyApprove(
  sessionId: string,
  body: {
    request_real_assembly: boolean;
    reason?: string;
    ttl_minutes?: number;
    approved_by?: string;
  },
): Promise<AssemblyApprovalActionResponse> {
  return postAssemblyAction(sessionId, "/assembly/approve", {
    request_real_assembly: body.request_real_assembly,
    reason: body.reason ?? "",
    ttl_minutes: body.ttl_minutes,
    approved_by: body.approved_by ?? "operator",
  });
}

export function postAssemblyReject(
  sessionId: string,
  body: { reason?: string; rejected_by?: string } = {},
): Promise<AssemblyApprovalActionResponse> {
  return postAssemblyAction(sessionId, "/assembly/reject", {
    reason: body.reason ?? "",
    rejected_by: body.rejected_by ?? "operator",
  });
}

export function postAssemblyExpire(
  sessionId: string,
  body: { reason?: string; expired_by?: string } = {},
): Promise<AssemblyApprovalActionResponse> {
  return postAssemblyAction(sessionId, "/assembly/expire", {
    reason: body.reason ?? "",
    expired_by: body.expired_by ?? "operator",
  });
}

export function postAssemblyResetApproval(
  sessionId: string,
  body: { reason?: string; reset_by?: string } = {},
): Promise<AssemblyApprovalActionResponse> {
  return postAssemblyAction(sessionId, "/assembly/reset-approval", {
    reason: body.reason ?? "",
    reset_by: body.reset_by ?? "operator",
  });
}

export function parseAssemblyApprovalError(raw: unknown): string {
  if (raw instanceof AssemblyApprovalSafetyError) {
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
  return "Assembly approval action failed";
}
