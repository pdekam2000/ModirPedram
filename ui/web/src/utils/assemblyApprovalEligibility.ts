import { AssemblyRuntimeObservability } from "./assemblyRuntimeObservability";

export type AssemblyApprovalAction = "approve" | "reject" | "expire" | "reset";

export type AssemblyActionEligibility = {
  visible: boolean;
  allowed: boolean;
  reason: string;
};

export type AssemblySessionContext = {
  archived?: boolean;
  cancelRequested?: boolean;
  isLegacy?: boolean;
};

export type AssemblyApprovalEligibilityMap = Record<AssemblyApprovalAction, AssemblyActionEligibility>;

function blocked(reason: string, visible = false): AssemblyActionEligibility {
  return { visible, allowed: false, reason };
}

function allowedEntry(reason: string): AssemblyActionEligibility {
  return { visible: true, allowed: true, reason };
}

export function evaluateAssemblyApprovalEligibility(
  assembly: AssemblyRuntimeObservability,
  session: AssemblySessionContext = {},
): AssemblyApprovalEligibilityMap {
  const state = assembly.approvalStateKey;
  const hidden = (reason: string): AssemblyApprovalEligibilityMap => ({
    approve: blocked(reason),
    reject: blocked(reason),
    expire: blocked(reason),
    reset: blocked(reason),
  });

  if (session.isLegacy) {
    return hidden("Legacy session — assembly approval actions unavailable.");
  }

  if (session.archived) {
    return {
      approve: blocked("Session archived — assembly approval disabled.", true),
      reject: blocked("Session archived — assembly approval disabled.", true),
      expire: blocked("Session archived — assembly approval disabled.", true),
      reset: blocked("Session archived — assembly approval disabled.", true),
    };
  }

  if (session.cancelRequested) {
    return {
      approve: blocked("Session cancellation requested.", true),
      reject: blocked("Session cancellation requested.", true),
      expire: blocked("Session cancellation requested.", true),
      reset: blocked("Session cancellation requested.", true),
    };
  }

  if (!assembly.hasAssemblySlot) {
    return hidden("Assembly generation slot unavailable.");
  }

  if (assembly.assemblyRunning) {
    return hidden("Assembly run is active — actions unavailable.");
  }

  const planReady = assembly.validationStatusKey === "READY";
  const dryRunDone = assembly.dryRunCompleted;

  const approveBase =
    planReady &&
    dryRunDone &&
    (state === "required" || state === "not_required" || state === "rejected" || state === "expired");

  const approve = approveBase
    ? allowedEntry("Approve future real assembly execution metadata.")
    : state === "approved"
      ? blocked("Assembly is already approved.", true)
      : !dryRunDone
        ? blocked("Assembly dry-run has not completed.")
        : !planReady
          ? blocked("Assembly plan is not READY.")
          : blocked("Approve unavailable for current assembly slot state.");

  const rejectVisible = state === "required" || state === "approved";
  const reject = rejectVisible
    ? allowedEntry("Reject assembly approval.")
    : blocked("Reject available only when approval is required or approved.");

  const expireVisible = state === "approved";
  const expire = expireVisible
    ? allowedEntry("Expire active assembly approval.")
    : blocked("Expire available only when approval is approved.");

  const resetVisible = state === "rejected" || state === "expired" || state === "approved";
  const reset = resetVisible
    ? allowedEntry("Reset assembly approval metadata.")
    : blocked("Reset available for rejected, expired, or approved states.");

  return { approve, reject, expire, reset };
}
