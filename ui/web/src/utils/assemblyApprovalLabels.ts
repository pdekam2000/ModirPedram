const BLOCK_LABELS: Record<string, string> = {
  REAL_ASSEMBLY_NOT_REQUESTED:
    "Real assembly not requested — use Approve assembly to authorize future execution.",
  ASSEMBLY_PLAN_NOT_READY: "Assembly plan is not READY — complete upstream artifacts and dry-run first.",
  ASSEMBLY_DRY_RUN_NOT_COMPLETED: "Assembly dry-run has not completed — run dry-run before approving.",
  ASSEMBLY_APPROVAL_REQUIRED: "Operator approval required before real assembly can run.",
  ASSEMBLY_APPROVAL_REJECTED: "Assembly was rejected — reset or re-approve to continue.",
  ASSEMBLY_APPROVAL_EXPIRED: "Approval expired — re-approval required.",
  ASSEMBLY_REAL_EXECUTION_DISABLED: "Real assembly is globally disabled (environment flag).",
  ASSEMBLY_RUNTIME_EXECUTION_DISABLED: "Runtime execution approval flag is off.",
  ASSEMBLY_SESSION_ARCHIVED: "Session is archived — approval actions disabled.",
  ASSEMBLY_CANCELLED: "Session cancellation requested — approval actions disabled.",
  ASSEMBLY_RUN_ACTIVE: "Assembly run in progress — wait for completion.",
};

export const ASSEMBLY_APPROVE_SAFETY_WARNING =
  "This only approves future real assembly execution. It does not run FFmpeg or generate the final video yet.";

export const ASSEMBLY_APPROVAL_ACTIONS_BANNER =
  "Assembly approval actions authorize future real assembly execution metadata only. No FFmpeg runs and no final video is generated in this phase.";

export const DEFAULT_ASSEMBLY_APPROVAL_TTL_MINUTES = 30;

export const ASSEMBLY_ACTION_LABELS = {
  approve: "Approve assembly",
  reject: "Reject approval",
  expire: "Expire approval",
  reset: "Reset approval",
} as const;

export function formatAssemblyBlockedReason(code: string): string {
  const key = String(code || "").trim().toUpperCase();
  return BLOCK_LABELS[key] || key;
}

export function formatAssemblyBlockedReasons(codes: string[]): string {
  if (codes.length === 0) {
    return "—";
  }
  return codes.map(formatAssemblyBlockedReason).join(" · ");
}
