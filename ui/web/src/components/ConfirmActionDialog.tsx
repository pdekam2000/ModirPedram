import { FormEvent, useEffect, useState } from "react";
import { SessionActionType } from "../api/client";
import { ACTION_META } from "../utils/sessionActions";

type Props = {
  open: boolean;
  action: SessionActionType | null;
  currentState: string;
  loading?: boolean;
  onConfirm: (reason: string) => void;
  onCancel: () => void;
};

export function ConfirmActionDialog({
  open,
  action,
  currentState,
  loading = false,
  onConfirm,
  onCancel,
}: Props) {
  const [reason, setReason] = useState("");

  useEffect(() => {
    if (open) {
      setReason("");
    }
  }, [open, action]);

  if (!open || !action) {
    return null;
  }

  const meta = ACTION_META[action];
  const reasonValid = !meta.requireReason || reason.trim().length >= 3;

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!reasonValid || loading) {
      return;
    }
    onConfirm(reason.trim());
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onCancel}>
      <div
        className="modal-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="action-dialog-title"
        onClick={(event) => event.stopPropagation()}
      >
        <h3 id="action-dialog-title">{meta.label} session?</h3>
        <p className="muted modal-sub">
          Current state: <strong>{currentState || "—"}</strong>
        </p>
        <p>{meta.consequence}</p>
        <p className="action-safety-note">{meta.safetyNote}</p>

        <form onSubmit={handleSubmit}>
          <label className="modal-label" htmlFor="action-reason">
            Reason {meta.requireReason ? "(required)" : "(optional)"}
          </label>
          <textarea
            id="action-reason"
            className="modal-textarea"
            rows={3}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder={meta.requireReason ? "Minimum 3 characters" : "Optional note"}
          />

          <div className="modal-actions">
            <button type="button" onClick={onCancel} disabled={loading}>
              Back
            </button>
            <button
              type="submit"
              className={meta.variant === "danger" ? "btn-danger" : meta.variant === "neutral" ? "btn-neutral" : ""}
              disabled={!reasonValid || loading}
            >
              {loading ? "Working…" : `Confirm ${meta.label}`}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
