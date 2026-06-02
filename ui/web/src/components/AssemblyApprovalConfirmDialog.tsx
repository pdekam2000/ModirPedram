import { FormEvent, useEffect, useState } from "react";
import { AssemblyRuntimeObservability } from "../utils/assemblyRuntimeObservability";
import {
  ASSEMBLY_APPROVE_SAFETY_WARNING,
  DEFAULT_ASSEMBLY_APPROVAL_TTL_MINUTES,
  formatAssemblyBlockedReasons,
} from "../utils/assemblyApprovalLabels";
import { AssemblyApprovalAction } from "../utils/assemblyApprovalEligibility";

type Props = {
  open: boolean;
  action: AssemblyApprovalAction | null;
  assembly: AssemblyRuntimeObservability;
  loading?: boolean;
  onConfirm: (payload: { reason: string; ttlMinutes?: number }) => void;
  onCancel: () => void;
};

const ACTION_TITLES: Record<AssemblyApprovalAction, string> = {
  approve: "Approve assembly?",
  reject: "Reject assembly approval?",
  expire: "Expire assembly approval?",
  reset: "Reset assembly approval?",
};

const ACTION_CONSEQUENCE: Record<AssemblyApprovalAction, string> = {
  approve: "Grant metadata-only approval for future real assembly execution on this session.",
  reject: "Block real assembly until re-approved. Does not run FFmpeg or delete upstream artifacts.",
  expire: "Immediately revoke active approval. Real assembly remains blocked until re-approved.",
  reset: "Clear approval grant fields and recalculate gate state. Does not execute assembly.",
};

export function AssemblyApprovalConfirmDialog({
  open,
  action,
  assembly,
  loading = false,
  onConfirm,
  onCancel,
}: Props) {
  const [reason, setReason] = useState("");
  const [ttlMinutes, setTtlMinutes] = useState(DEFAULT_ASSEMBLY_APPROVAL_TTL_MINUTES);

  useEffect(() => {
    if (open) {
      setReason("");
      setTtlMinutes(assembly.defaultTtlMinutes || DEFAULT_ASSEMBLY_APPROVAL_TTL_MINUTES);
    }
  }, [open, action, assembly.defaultTtlMinutes]);

  if (!open || !action) {
    return null;
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (loading) {
      return;
    }
    onConfirm({
      reason: reason.trim(),
      ttlMinutes: action === "approve" ? ttlMinutes : undefined,
    });
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onCancel}>
      <div
        className="modal-card assembly-approval-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="assembly-approval-dialog-title"
        onClick={(event) => event.stopPropagation()}
      >
        <h3 id="assembly-approval-dialog-title">{ACTION_TITLES[action]}</h3>
        <p className="muted modal-sub">Approval state: {assembly.approvalState}</p>
        <p>{ACTION_CONSEQUENCE[action]}</p>

        {action === "approve" && (
          <div className="assembly-approval-modal-estimates kv-grid kv-grid-tight">
            <div>
              <span className="kv-label">Expected output</span>
              <span>{assembly.expectedOutput}</span>
            </div>
            <div>
              <span className="kv-label">Est. runtime</span>
              <span>{assembly.estimatedRuntimeSeconds}</span>
            </div>
            <div>
              <span className="kv-label">Est. output size</span>
              <span>{assembly.estimatedOutputSize}</span>
            </div>
            <div>
              <span className="kv-label">Est. disk usage</span>
              <span>{assembly.estimatedDiskUsage}</span>
            </div>
            <div>
              <span className="kv-label">Blocked because</span>
              <span>{formatAssemblyBlockedReasons(assembly.assemblyBlockedReasons)}</span>
            </div>
          </div>
        )}

        {action === "approve" && (
          <p className="assembly-approval-safety-warning" role="alert">
            {ASSEMBLY_APPROVE_SAFETY_WARNING}
          </p>
        )}

        <p className="action-safety-note">
          Response must include real_assembly_executed=false. No FFmpeg is invoked from this control.
        </p>

        <form onSubmit={handleSubmit}>
          {action === "approve" && (
            <>
              <label className="modal-label" htmlFor="assembly-approval-ttl">
                Approval TTL (minutes)
              </label>
              <input
                id="assembly-approval-ttl"
                className="modal-input"
                type="number"
                min={15}
                max={1440}
                value={ttlMinutes}
                onChange={(event) =>
                  setTtlMinutes(Number(event.target.value) || DEFAULT_ASSEMBLY_APPROVAL_TTL_MINUTES)
                }
              />
            </>
          )}

          <label className="modal-label" htmlFor="assembly-approval-reason">
            Reason (optional)
          </label>
          <textarea
            id="assembly-approval-reason"
            className="modal-textarea"
            rows={3}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="Optional operator note"
          />

          <div className="modal-actions">
            <button type="button" onClick={onCancel} disabled={loading}>
              Back
            </button>
            <button type="submit" className={action === "reject" ? "btn-danger" : "btn-neutral"} disabled={loading}>
              {loading ? "Working…" : "Confirm"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
