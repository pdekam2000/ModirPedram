import { FormEvent, useEffect, useState } from "react";
import { VoiceRuntimeObservability } from "../utils/categoryRuntimeShell";
import {
  DEFAULT_APPROVAL_TTL_MINUTES,
  formatBlockedReasons,
  VOICE_APPROVE_SAFETY_WARNING,
} from "../utils/voiceApprovalLabels";
import { VoiceApprovalAction } from "../utils/voiceApprovalEligibility";

type Props = {
  open: boolean;
  action: VoiceApprovalAction | null;
  voice: VoiceRuntimeObservability;
  loading?: boolean;
  onConfirm: (payload: { reason: string; ttlMinutes?: number; clearLiveTtsRequest?: boolean }) => void;
  onCancel: () => void;
};

const ACTION_TITLES: Record<VoiceApprovalAction, string> = {
  approve: "Approve voice generation?",
  reject: "Reject voice approval?",
  expire: "Expire voice approval?",
  reset: "Reset voice approval?",
};

const ACTION_CONSEQUENCE: Record<VoiceApprovalAction, string> = {
  approve: "Grant metadata-only approval for future ElevenLabs voice generation on this session.",
  reject: "Block live TTS until voice is re-approved. Does not generate or delete audio.",
  expire: "Immediately revoke active approval. Live TTS remains blocked until re-approved.",
  reset: "Clear approval grant fields and recalculate gate state. Does not execute TTS.",
};

export function VoiceApprovalConfirmDialog({
  open,
  action,
  voice,
  loading = false,
  onConfirm,
  onCancel,
}: Props) {
  const [reason, setReason] = useState("");
  const [ttlMinutes, setTtlMinutes] = useState(DEFAULT_APPROVAL_TTL_MINUTES);
  const [clearLiveTtsRequest, setClearLiveTtsRequest] = useState(false);

  useEffect(() => {
    if (open) {
      setReason("");
      setTtlMinutes(voice.defaultTtlMinutes || DEFAULT_APPROVAL_TTL_MINUTES);
      setClearLiveTtsRequest(false);
    }
  }, [open, action, voice.defaultTtlMinutes]);

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
      clearLiveTtsRequest: action === "reset" ? clearLiveTtsRequest : undefined,
    });
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onCancel}>
      <div
        className="modal-card voice-approval-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="voice-approval-dialog-title"
        onClick={(event) => event.stopPropagation()}
      >
        <h3 id="voice-approval-dialog-title">{ACTION_TITLES[action]}</h3>
        <p className="muted modal-sub">Approval state: {voice.approvalState}</p>
        <p>{ACTION_CONSEQUENCE[action]}</p>

        {action === "approve" && (
          <div className="voice-approval-modal-estimates kv-grid kv-grid-tight">
            <div>
              <span className="kv-label">Est. characters</span>
              <span>{voice.estimatedCharacters}</span>
            </div>
            <div>
              <span className="kv-label">Est. segments</span>
              <span>{voice.estimatedSegments}</span>
            </div>
            <div>
              <span className="kv-label">Est. voice cost</span>
              <span>{voice.estimatedVoiceCost}</span>
            </div>
            <div>
              <span className="kv-label">Blocked because</span>
              <span>{formatBlockedReasons(voice.blockedReasonCodes)}</span>
            </div>
          </div>
        )}

        {action === "approve" && (
          <p className="voice-approval-safety-warning" role="alert">
            {VOICE_APPROVE_SAFETY_WARNING}
          </p>
        )}

        <p className="action-safety-note">
          Approving does not call ElevenLabs. Response must include tts_executed=false.
        </p>

        <form onSubmit={handleSubmit}>
          {action === "approve" && (
            <>
              <label className="modal-label" htmlFor="voice-approval-ttl">
                Approval TTL (minutes)
              </label>
              <input
                id="voice-approval-ttl"
                className="modal-input"
                type="number"
                min={15}
                max={1440}
                value={ttlMinutes}
                onChange={(event) => setTtlMinutes(Number(event.target.value) || DEFAULT_APPROVAL_TTL_MINUTES)}
              />
            </>
          )}

          {action === "reset" && (
            <label className="modal-checkbox">
              <input
                type="checkbox"
                checked={clearLiveTtsRequest}
                onChange={(event) => setClearLiveTtsRequest(event.target.checked)}
              />
              Clear live TTS request
            </label>
          )}

          <label className="modal-label" htmlFor="voice-approval-reason">
            Reason (optional)
          </label>
          <textarea
            id="voice-approval-reason"
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
