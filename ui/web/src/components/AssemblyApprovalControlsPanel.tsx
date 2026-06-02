import { useState } from "react";
import {
  AssemblyApprovalActionResponse,
  AssemblyApprovalSafetyError,
  parseAssemblyApprovalError,
  postAssemblyApprove,
  postAssemblyExpire,
  postAssemblyReject,
  postAssemblyResetApproval,
} from "../api/assemblyApprovalClient";
import { AssemblyRuntimeObservability } from "../utils/assemblyRuntimeObservability";
import {
  AssemblyApprovalAction,
  AssemblySessionContext,
  evaluateAssemblyApprovalEligibility,
} from "../utils/assemblyApprovalEligibility";
import {
  ASSEMBLY_ACTION_LABELS,
  ASSEMBLY_APPROVAL_ACTIONS_BANNER,
  formatAssemblyBlockedReasons,
} from "../utils/assemblyApprovalLabels";
import { AssemblyApprovalConfirmDialog } from "./AssemblyApprovalConfirmDialog";

type Props = {
  sessionId: string | null;
  assembly: AssemblyRuntimeObservability;
  sessionContext?: AssemblySessionContext;
  onAfterAction?: () => Promise<void> | void;
};

export function AssemblyApprovalControlsPanel({
  sessionId,
  assembly,
  sessionContext = {},
  onAfterAction,
}: Props) {
  const [pendingAction, setPendingAction] = useState<AssemblyApprovalAction | null>(null);
  const [acting, setActing] = useState(false);
  const [safetyError, setSafetyError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<AssemblyApprovalActionResponse | null>(null);

  const eligibility = evaluateAssemblyApprovalEligibility(assembly, sessionContext);
  const anyVisible = (["approve", "reject", "expire", "reset"] as AssemblyApprovalAction[]).some(
    (action) => eligibility[action].visible,
  );

  async function handleConfirm(payload: { reason: string; ttlMinutes?: number }) {
    if (!sessionId || !pendingAction) {
      return;
    }
    setActing(true);
    setActionError(null);
    setSafetyError(null);
    try {
      let result: AssemblyApprovalActionResponse;
      if (pendingAction === "approve") {
        result = await postAssemblyApprove(sessionId, {
          request_real_assembly: true,
          reason: payload.reason,
          ttl_minutes: payload.ttlMinutes,
          approved_by: "operator",
        });
      } else if (pendingAction === "reject") {
        result = await postAssemblyReject(sessionId, {
          reason: payload.reason,
          rejected_by: "operator",
        });
      } else if (pendingAction === "expire") {
        result = await postAssemblyExpire(sessionId, {
          reason: payload.reason,
          expired_by: "operator",
        });
      } else {
        result = await postAssemblyResetApproval(sessionId, {
          reason: payload.reason,
          reset_by: "operator",
        });
      }
      setLastResult(result);
      setPendingAction(null);
      await onAfterAction?.();
    } catch (err) {
      if (err instanceof AssemblyApprovalSafetyError) {
        setSafetyError(err.message);
      } else {
        setActionError(parseAssemblyApprovalError(err));
      }
    } finally {
      setActing(false);
    }
  }

  if (sessionContext.isLegacy) {
    return (
      <div className="assembly-approval-actions-section">
        <h5>Assembly approval actions</h5>
        <p className="muted assembly-runtime-note">Legacy session — assembly approval actions unavailable.</p>
      </div>
    );
  }

  return (
    <div className="assembly-approval-actions-section">
      <h5>Assembly approval actions</h5>
      <p className="muted assembly-runtime-note">{ASSEMBLY_APPROVAL_ACTIONS_BANNER}</p>

      {!assembly.dryRunCompleted && assembly.hasAssemblySlot && (
        <p className="assembly-approval-state-note">Assembly dry-run has not completed — approve unavailable.</p>
      )}
      {assembly.assemblyBlockedReasons.length > 0 && (
        <p className="assembly-approval-blocked-note">
          Blocked because: {formatAssemblyBlockedReasons(assembly.assemblyBlockedReasons)}
        </p>
      )}

      {safetyError && <p className="action-error-inline">{safetyError}</p>}
      {actionError && <p className="action-error-inline">{actionError}</p>}

      {!sessionId ? (
        <p className="muted assembly-runtime-note">Session id required for assembly approval actions.</p>
      ) : anyVisible ? (
        <div className="assembly-approval-action-grid">
          {(["approve", "reject", "expire", "reset"] as AssemblyApprovalAction[]).map((action) => {
            const gate = eligibility[action];
            if (!gate.visible) {
              return null;
            }
            return (
              <article
                key={action}
                className={`action-eligibility-card ${gate.allowed ? "allowed" : "blocked"}`}
              >
                <div className="action-eligibility-head">
                  <strong>{ASSEMBLY_ACTION_LABELS[action]}</strong>
                  <span className={gate.allowed ? "action-pill-allowed" : "action-pill-blocked"}>
                    {gate.allowed ? "Available" : "Blocked"}
                  </span>
                </div>
                <p className="muted action-eligibility-reason">{gate.reason}</p>
                <button
                  type="button"
                  className={action === "reject" ? "btn-danger" : action === "approve" ? "" : "btn-neutral"}
                  disabled={!gate.allowed || acting}
                  onClick={() => setPendingAction(action)}
                >
                  {ASSEMBLY_ACTION_LABELS[action]}
                </button>
              </article>
            );
          })}
        </div>
      ) : (
        <p className="muted assembly-runtime-note">No assembly approval actions available for the current state.</p>
      )}

      {lastResult && (
        <div className="assembly-approval-last-result">
          <strong>Last action:</strong> {lastResult.action} · real_assembly_executed=
          {String(lastResult.real_assembly_executed)}
          {lastResult.message ? ` — ${lastResult.message}` : ""}
        </div>
      )}

      <AssemblyApprovalConfirmDialog
        open={pendingAction !== null}
        action={pendingAction}
        assembly={assembly}
        loading={acting}
        onConfirm={(payload) => void handleConfirm(payload)}
        onCancel={() => setPendingAction(null)}
      />
    </div>
  );
}
